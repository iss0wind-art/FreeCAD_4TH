"""
F-1 + 어댑터 ② + 분류 + Codex 매핑 PoC — 다섯째 호미
=================================================

본영 어댑터 ② (line_pairing.py) 결합 — 벽 페어 + 격자 자동.
넷째 호미 잔여 C1 85건을 wall_segment로 강등.

[흐름]
  1) 9도엽 합본 → S30-022 도엽 (B1F)
  2) LINE + LWPOLYLINE 추출 (F-1 정렬)
  3) run_adapter_2(LINE) → wall_pairs + grid
  4) 폐합 사각형 분류 (classify_batch) — 격자 자동 입력
  5) 추가: wall zone 안 박스를 wall_segment로 강등 (이천 자력)
  6) COLUMN(conf>=1.0)만 codex 매핑
  7) 결과 박제

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_f1_adapter2_full_102.py
"""
import os, sys, json, re, math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
from core.f1_anchor_aligner import EVAnchor, F1Aligner
from core.line_pairing import LineSeg, run_adapter_2
from core.box_classifier import (
    BoxKind, CoreRegion, GridLines,
    classify_batch, BoxClassification,
)
from core.codex_instance_mapper import (
    BoxInstance, load_codex, map_instances,
)

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-021~029-102동 구조평면도.dxf"
CODEX = "output/codex_columns_unified.json"
OUT_JSON = "output/f1_adapter2_full_102_S30-022.json"
OUT_MD = "output/f1_adapter2_full_102_S30-022.md"

TARGET_SHEET = 'S30-022'
SOURCE_HINT = '101~112동'
FLOOR_HINT = -1

CORE1_SW_NORM = (73040.0, 52178.0)
CORE1_W, CORE1_H = 4307.0, 4860.0
CORE2_CX_NORM, CORE2_CY_NORM = 90049.0, 26299.0
CORE2_W, CORE2_H = 4579.0, 4839.0


def iter_all(c, d=0, m=8):
    if d > m:
        return
    for e in c:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), d + 1, m)
            except Exception:
                pass
        else:
            yield e


def extract_lines_in_sheet(msp, sx, sy, sheet_w, sheet_h, inset=0.05):
    """도엽 영역 안 LINE 추출 (F-1 정규화 좌표)."""
    ix0, iy0 = sx + sheet_w * inset, sy + sheet_h * inset
    ix1, iy1 = sx + sheet_w * (1 - inset), sy + sheet_h * (1 - inset)
    lines = []
    for e in iter_all(msp):
        if e.dxftype() != 'LINE':
            continue
        try:
            s, ed = e.dxf.start, e.dxf.end
        except Exception:
            continue
        # 양 끝점 모두 도엽 영역 안
        if not (ix0 <= s.x <= ix1 and iy0 <= s.y <= iy1):
            continue
        if not (ix0 <= ed.x <= ix1 and iy0 <= ed.y <= iy1):
            continue
        lines.append({
            'p1_abs': (s.x, s.y), 'p2_abs': (ed.x, ed.y),
            'layer': e.dxf.layer,
        })
    return lines


def extract_column_boxes(msp, sx, sy, sheet_w, sheet_h,
                         w_min=400, w_max=3000, inset=0.05):
    """폐합 사각형 추출 (정규화 좌표 dict)."""
    ix0, iy0 = sx + sheet_w * inset, sy + sheet_h * inset
    ix1, iy1 = sx + sheet_w * (1 - inset), sy + sheet_h * (1 - inset)
    boxes = []
    for e in iter_all(msp):
        if e.dxftype() != 'LWPOLYLINE':
            continue
        try:
            if not e.is_closed:
                continue
            pts = [(x, y) for x, y, *_ in e.get_points()]
            if not (4 <= len(pts) <= 6):
                continue
        except Exception:
            continue
        cx_abs = sum(p[0] for p in pts) / len(pts)
        cy_abs = sum(p[1] for p in pts) / len(pts)
        if not (ix0 <= cx_abs <= ix1 and iy0 <= cy_abs <= iy1):
            continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        w, h = xmax - xmin, ymax - ymin
        if not (w_min <= w <= w_max and w_min <= h <= w_max):
            continue
        boxes.append({
            'cx_abs': cx_abs, 'cy_abs': cy_abs,
            'w': w, 'h': h,
            'box_abs': (xmin, ymin, xmax, ymax),
        })
    return boxes


def is_in_wall_zone(cx, cy, wall_pairs, margin=200):
    """박스 중심이 벽 페어 중심선 ± (thickness/2 + margin) 안인지."""
    for p in wall_pairs:
        p1, p2 = p.centerline_p1, p.centerline_p2
        # 점-선분 거리 + 선분 안 투영 검증
        dx = p2[0] - p1[0]; dy = p2[1] - p1[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-9:
            continue
        # 투영 t (0~1 안이어야 선분 *위*)
        t = ((cx - p1[0]) * dx + (cy - p1[1]) * dy) / L2
        if not (0 <= t <= 1):
            continue
        # 수직 거리
        proj_x = p1[0] + t * dx
        proj_y = p1[1] + t * dy
        dist = math.hypot(cx - proj_x, cy - proj_y)
        if dist <= p.thickness / 2 + margin:
            return True
    return False


def main():
    print(f'[도면] {DXF}')
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()

    # 1. 도엽 표제
    sheets = {}
    for e in iter_all(msp):
        if e.dxftype() == 'TEXT':
            try:
                t = e.dxf.text.strip()
                m = re.match(r'^S30-(02[1-9])$', t)
                if m:
                    sheets[t] = (e.dxf.insert.x, e.dxf.insert.y)
            except Exception:
                pass
    sx, sy = sheets[TARGET_SHEET]
    sheet_w, sheet_h = 126000, 178200

    # 2. LINE + 폐합 사각형 추출
    lines_raw = extract_lines_in_sheet(msp, sx, sy, sheet_w, sheet_h)
    boxes = extract_column_boxes(msp, sx, sy, sheet_w, sheet_h)
    print(f'[추출] LINE {len(lines_raw)}개, 폐합 박스 {len(boxes)}개')

    # F-1 정렬 (정규화 → anchor 빼기)
    def to_aligned(pt_abs):
        nx = pt_abs[0] - sx - CORE1_SW_NORM[0]
        ny = pt_abs[1] - sy - CORE1_SW_NORM[1]
        return (nx, ny)

    # LINE → LineSeg (F-1 좌표)
    line_segs = []
    for i, ln in enumerate(lines_raw):
        p1 = to_aligned(ln['p1_abs'])
        p2 = to_aligned(ln['p2_abs'])
        line_segs.append(LineSeg(p1=p1, p2=p2, layer=ln['layer'], line_id=i))

    # 박스 → F-1 좌표
    for b in boxes:
        b['cx_aligned'], b['cy_aligned'] = to_aligned((b['cx_abs'], b['cy_abs']))

    # 3. 어댑터 ② 호출
    print(f'\n[어댑터 ② 호출] LINE {len(line_segs)}개 입력...')
    result = run_adapter_2(line_segs)
    stats = result['stats']
    print(f'  벽 페어: {stats["wall_pairs"]}개')
    print(f'  격자 X: {stats["grid_x"]}, Y: {stats["grid_y"]}')
    print(f'  paired LINE: {stats["paired_lines"]}, unused: {stats["unused_lines"]}')

    grid_obj = result['grid_lines_obj']
    if grid_obj and len(grid_obj.x_lines) <= 30:
        print(f'  X 격자: {[round(x) for x in grid_obj.x_lines]}')
    if grid_obj and len(grid_obj.y_lines) <= 30:
        print(f'  Y 격자: {[round(y) for y in grid_obj.y_lines]}')

    # 4. 코어 영역 (F-1 좌표)
    core1_sw = (0.0, 0.0)
    core1_ne = (CORE1_W, CORE1_H)
    core2_sw_norm = (CORE2_CX_NORM - CORE2_W / 2, CORE2_CY_NORM - CORE2_H / 2)
    core2_sw = (core2_sw_norm[0] - CORE1_SW_NORM[0],
                core2_sw_norm[1] - CORE1_SW_NORM[1])
    core2_ne = (core2_sw[0] + CORE2_W, core2_sw[1] + CORE2_H)
    core_regions = [
        CoreRegion(sw=core1_sw, ne=core1_ne, margin=300),
        CoreRegion(sw=core2_sw, ne=core2_ne, margin=300),
    ]

    # 5. 분류 — 본영 격자 객체 직접 사용
    batch_input = [
        (f'102_{TARGET_SHEET}_box_{i:03d}', b['cx_aligned'], b['cy_aligned'],
         b['w'], b['h'])
        for i, b in enumerate(boxes)
    ]
    classifications = classify_batch(
        batch_input, core_regions=core_regions, grid=grid_obj,
        column_max_ratio=3.0,
    )

    # 6. 추가 — wall zone 안 박스를 wall_segment로 강등 (이천 자력)
    wall_pairs = result['wall_pairs']
    walled_count = 0
    for i, c in enumerate(classifications):
        b = boxes[i]
        if c.kind == BoxKind.COLUMN:
            if is_in_wall_zone(b['cx_aligned'], b['cy_aligned'], wall_pairs):
                # 강등 — 벽 페어 영역 안이면 wall_segment
                classifications[i] = BoxClassification(
                    box_id=c.box_id, kind=BoxKind.WALL_SEGMENT,
                    aspect_ratio=c.aspect_ratio, in_core=c.in_core,
                    on_grid_intersection=c.on_grid_intersection,
                    confidence=0.85,
                    reason=f'demoted: in wall_pair zone (was {c.kind.value})',
                )
                walled_count += 1
    print(f'\n[wall zone 강등] {walled_count}건 (column → wall_segment)')

    # 분류 분포
    by_kind = {}
    for c in classifications:
        by_kind[c.kind.value] = by_kind.get(c.kind.value, 0) + 1
    print(f'\n[분류 결과]')
    for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v} ({100*v/len(classifications):.1f}%)')

    # 7. COLUMN conf>=1.0만 매핑
    column_classifications = [c for c in classifications if c.kind == BoxKind.COLUMN]
    high_conf = [c for c in column_classifications if c.confidence >= 1.0]
    print(f'\n[COLUMN 분류] 총 {len(column_classifications)}, conf=1.0 (격자 위): {len(high_conf)}')

    box_by_id = {f'102_{TARGET_SHEET}_box_{i:03d}': boxes[i] for i in range(len(boxes))}
    instances = []
    for c in high_conf:
        b = box_by_id[c.box_id]
        instances.append(BoxInstance(
            box_id=c.box_id, width=b['w'], height=b['h'],
            label=None, source_hint=SOURCE_HINT, floor_hint=FLOOR_HINT,
        ))

    codex = load_codex(CODEX)
    mappings, unmatched = map_instances(instances, codex)
    rate = 100 * len(mappings) / (len(instances) or 1)
    print(f'  매핑 성공: {len(mappings)} / 실패: {len(unmatched)} (매칭률 {rate:.1f}%)')

    # symbol 분포
    by_symbol = {}
    for m in mappings:
        by_symbol[m.matched_symbol] = by_symbol.get(m.matched_symbol, 0) + 1
    print(f'  symbol별 (top 10):')
    for k, v in sorted(by_symbol.items(), key=lambda x: -x[1])[:10]:
        print(f'    {k}: {v}')

    # 8. 박제
    os.makedirs('output', exist_ok=True)
    out = {
        'sheet_id': TARGET_SHEET,
        'dong': '102',
        'adapter_2_stats': stats,
        'wall_pairs_summary': [
            {
                'line_a_id': p.line_a_id, 'line_b_id': p.line_b_id,
                'thickness': round(p.distance, 1),
                'overlap': round(p.overlap_length, 1),
                'centerline_p1': list(p.centerline_p1),
                'centerline_p2': list(p.centerline_p2),
                'confidence': p.confidence,
            }
            for p in wall_pairs[:50]  # 미리보기 50건
        ],
        'wall_pair_total': len(wall_pairs),
        'grid_x': [round(x, 1) for x in grid_obj.x_lines] if grid_obj else [],
        'grid_y': [round(y, 1) for y in grid_obj.y_lines] if grid_obj else [],
        'classification_summary': by_kind,
        'wall_zone_demotion': walled_count,
        'mapping_summary': {
            'instances': len(instances),
            'matched': len(mappings),
            'unmatched': len(unmatched),
            'rate': round(rate, 1),
            'symbols': by_symbol,
        },
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[박제] {OUT_JSON}')

    md = [
        f'# F-1 + 어댑터 ② + 분류 + Codex 매핑 — 102동 {TARGET_SHEET}',
        '', '> 다섯째 호미: 벽 페어 자동 + 격자 자동 + 분류 정밀화', '',
        f'## 어댑터 ② 결과', '',
        f'- LINE 입력: {stats["total_lines"]}',
        f'- 벽 페어: {stats["wall_pairs"]}',
        f'- 격자 X·Y: {stats["grid_x"]}·{stats["grid_y"]}',
        f'- 사용 LINE: {stats["paired_lines"] + len(grid_obj.x_lines) + len(grid_obj.y_lines) if grid_obj else stats["paired_lines"]}',
        '', '## 분류 결과', '',
        '| 종류 | 개수 | 비율 |',
        '|------|-----:|-----:|',
    ]
    for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
        md.append(f'| {k} | {v} | {100*v/len(classifications):.1f}% |')
    md += ['', f'## 매핑 결과 (conf=1.0 COLUMN만)', '',
           f'- 매핑 대상: {len(instances)}',
           f'- 매핑 성공: **{len(mappings)} ({rate:.1f}%)**',
           '', '### Symbol 분포 (top 15)', '',
           '| Symbol | 매칭 수 |', '|--------|------:|']
    for k, v in sorted(by_symbol.items(), key=lambda x: -x[1])[:15]:
        md.append(f'| {k} | {v} |')

    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    print(f'[박제] {OUT_MD}')


if __name__ == '__main__':
    main()
