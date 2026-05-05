"""
F-1 + 어댑터 ②+① + 분류 + Codex 매핑 — 102동 9도엽 전체 (여섯째 호미)
=================================================

본영 권고 1+2+4 동시 — 1F·9도엽·어댑터 ① 결합.

[흐름 — 도엽마다 반복]
  1) LINE + 폐합 박스 추출 (F-1 정렬)
  2) run_adapter_2(LINE) → 벽 페어 + 격자
  3) detect_girders_from_adapter2() → 거더 후보 + codex 매칭
  4) 폐합 박스 분류 (classify_batch + 격자 입력)
  5) 격자 conf=1.0 박스 → 기둥 codex 매핑
  6) 도엽별 통계 박제

[기대 결과]
  - 023(1F 필로티), 028·029(옥상): γ에서 제외 (코어 검출 도엽 아님)
  - 021·022(B2·B1): 진짜 기둥 적음, 거더 다수 예상
  - 024·025·026·027(1·2·3·4F): 진짜 기둥 다수, 거더 다수 예상

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_f1_full_stack_102_all_sheets.py
"""
import os, sys, json, re, math, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
from core.f1_anchor_aligner import EVAnchor, F1Aligner
from core.line_pairing import LineSeg, run_adapter_2
from core.girder_matcher import (
    load_girder_codex, detect_girders_from_adapter2,
)
from core.box_classifier import (
    BoxKind, CoreRegion, GridLines,
    classify_batch, BoxClassification,
)
from core.codex_instance_mapper import (
    BoxInstance, load_codex, map_instances,
)

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-021~029-102동 구조평면도.dxf"
COLUMN_CODEX = "output/codex_columns_unified.json"
GIRDER_CODEX = "output/codex_beams_basement.json"
OUT_JSON = "output/f1_full_stack_102_all_sheets.json"
OUT_MD = "output/f1_full_stack_102_all_sheets.md"

SOURCE_HINT = '101~112동'
CORE1_SW_NORM = (73040.0, 52178.0)
CORE1_W, CORE1_H = 4307.0, 4860.0
CORE2_CX_NORM, CORE2_CY_NORM = 90049.0, 26299.0
CORE2_W, CORE2_H = 4579.0, 4839.0

# 도엽 → 층 가설
SHEET_FLOOR = {
    'S30-021': -2, 'S30-022': -1, 'S30-023': 0,    # 1F 필로티
    'S30-024': 1, 'S30-025': 2, 'S30-026': 3, 'S30-027': 4,
    'S30-028': 5, 'S30-029': 6,
}

# 거더 H 가설 (도엽별)
GIRDER_H_HINT = {
    -2: 800, -1: 800, 0: 700, 1: 700, 2: 700, 3: 700, 4: 700, 5: 600, 6: 600
}


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


def extract_lines(msp, sx, sy, sheet_w, sheet_h, inset=0.05):
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
        if not (ix0 <= s.x <= ix1 and iy0 <= s.y <= iy1):
            continue
        if not (ix0 <= ed.x <= ix1 and iy0 <= ed.y <= iy1):
            continue
        lines.append({
            'p1_abs': (s.x, s.y), 'p2_abs': (ed.x, ed.y),
            'layer': e.dxf.layer,
        })
    return lines


def extract_boxes(msp, sx, sy, sheet_w, sheet_h,
                  w_min=400, w_max=3000, inset=0.05):
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
    for p in wall_pairs:
        p1, p2 = p.centerline_p1, p.centerline_p2
        dx = p2[0] - p1[0]; dy = p2[1] - p1[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-9:
            continue
        t = ((cx - p1[0]) * dx + (cy - p1[1]) * dy) / L2
        if not (0 <= t <= 1):
            continue
        proj_x = p1[0] + t * dx
        proj_y = p1[1] + t * dy
        if math.hypot(cx - proj_x, cy - proj_y) <= p.thickness / 2 + margin:
            return True
    return False


def process_sheet(msp, sheet_id, sx, sy, sheet_w, sheet_h,
                  column_codex, girder_codex, core_regions):
    """단일 도엽 처리 — 다섯째 호미 + 어댑터 ①."""
    floor = SHEET_FLOOR.get(sheet_id, 0)

    # F-1 정렬
    def to_aligned(pt_abs):
        return (pt_abs[0] - sx - CORE1_SW_NORM[0],
                pt_abs[1] - sy - CORE1_SW_NORM[1])

    # 추출
    lines_raw = extract_lines(msp, sx, sy, sheet_w, sheet_h)
    boxes = extract_boxes(msp, sx, sy, sheet_w, sheet_h)

    # LineSeg 변환
    line_segs = []
    for i, ln in enumerate(lines_raw):
        p1 = to_aligned(ln['p1_abs'])
        p2 = to_aligned(ln['p2_abs'])
        line_segs.append(LineSeg(p1=p1, p2=p2, layer=ln['layer'], line_id=i))

    # 박스 정렬
    for b in boxes:
        b['cx_aligned'], b['cy_aligned'] = to_aligned((b['cx_abs'], b['cy_abs']))

    # 어댑터 ②
    a2 = run_adapter_2(line_segs)
    grid_obj = a2['grid_lines_obj']
    wall_pairs = a2['wall_pairs']

    # 어댑터 ①
    girders = detect_girders_from_adapter2(
        adapter2_result=a2,
        grid_x=list(grid_obj.x_lines) if grid_obj else [],
        grid_y=list(grid_obj.y_lines) if grid_obj else [],
        girder_codex=girder_codex,
        expected_girder_height=GIRDER_H_HINT.get(floor, 800),
        require_on_grid=True,
    )

    # 분류
    batch_input = [
        (f'{sheet_id}_box_{i:03d}', b['cx_aligned'], b['cy_aligned'], b['w'], b['h'])
        for i, b in enumerate(boxes)
    ]
    classifications = classify_batch(
        batch_input, core_regions=core_regions, grid=grid_obj,
        column_max_ratio=3.0,
    )

    # wall zone 강등
    walled = 0
    for i, c in enumerate(classifications):
        if c.kind == BoxKind.COLUMN:
            b = boxes[i]
            if is_in_wall_zone(b['cx_aligned'], b['cy_aligned'], wall_pairs):
                classifications[i] = BoxClassification(
                    box_id=c.box_id, kind=BoxKind.WALL_SEGMENT,
                    aspect_ratio=c.aspect_ratio, in_core=c.in_core,
                    on_grid_intersection=c.on_grid_intersection,
                    confidence=0.85, reason='demoted: wall_pair zone',
                )
                walled += 1

    # COLUMN conf=1.0 매핑
    high_conf = [c for c in classifications
                 if c.kind == BoxKind.COLUMN and c.confidence >= 1.0]
    box_by_id = {f'{sheet_id}_box_{i:03d}': boxes[i] for i in range(len(boxes))}
    instances = []
    for c in high_conf:
        b = box_by_id[c.box_id]
        instances.append(BoxInstance(
            box_id=c.box_id, width=b['w'], height=b['h'],
            label=None, source_hint=SOURCE_HINT, floor_hint=floor,
        ))
    mappings, unmatched = map_instances(instances, column_codex)

    # 분류 통계
    by_kind = {}
    for c in classifications:
        by_kind[c.kind.value] = by_kind.get(c.kind.value, 0) + 1

    # 거더 매칭 통계
    girder_matched = sum(1 for g in girders if g.matched_symbol)

    return {
        'sheet_id': sheet_id,
        'floor_hint': floor,
        'lines': len(line_segs),
        'boxes': len(boxes),
        'wall_pairs': len(wall_pairs),
        'grid_x': len(grid_obj.x_lines) if grid_obj else 0,
        'grid_y': len(grid_obj.y_lines) if grid_obj else 0,
        'classification': by_kind,
        'wall_zone_demoted': walled,
        'column_high_conf': len(high_conf),
        'column_mapped': len(mappings),
        'column_symbols': {m.matched_symbol: 1 + sum(1 for x in mappings
                            if x.matched_symbol == m.matched_symbol) - 1
                            for m in mappings},  # symbol count
        'girder_candidates': len(girders),
        'girder_matched': girder_matched,
        'girder_symbols': {g.matched_symbol: 1 for g in girders if g.matched_symbol},
    }


def main():
    print(f'[도면] {DXF}')
    t0 = time.time()
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    print(f'[로드] {time.time()-t0:.1f}s')

    # 도엽 표제
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
    sheet_w, sheet_h = 126000, 178200

    # 코어 영역 (F-1 좌표)
    core1_sw = (0.0, 0.0); core1_ne = (CORE1_W, CORE1_H)
    core2_sw_n = (CORE2_CX_NORM - CORE2_W / 2, CORE2_CY_NORM - CORE2_H / 2)
    core2_sw = (core2_sw_n[0] - CORE1_SW_NORM[0], core2_sw_n[1] - CORE1_SW_NORM[1])
    core2_ne = (core2_sw[0] + CORE2_W, core2_sw[1] + CORE2_H)
    core_regions = [
        CoreRegion(sw=core1_sw, ne=core1_ne, margin=300),
        CoreRegion(sw=core2_sw, ne=core2_ne, margin=300),
    ]

    # codex 로드
    column_codex = load_codex(COLUMN_CODEX)
    girder_codex = load_girder_codex(GIRDER_CODEX)
    print(f'[codex] 기둥 {len(column_codex)}종, 거더 {len(girder_codex)}종')

    # 9도엽 처리
    results = []
    for sid in sorted(sheets):
        t1 = time.time()
        sx, sy = sheets[sid]
        try:
            r = process_sheet(msp, sid, sx, sy, sheet_w, sheet_h,
                              column_codex, girder_codex, core_regions)
            r['elapsed_s'] = round(time.time() - t1, 1)
            results.append(r)
            print(f'  [{sid}] floor={r["floor_hint"]:+d} '
                  f'LINE {r["lines"]} 박스 {r["boxes"]} '
                  f'벽페어 {r["wall_pairs"]} 격자 {r["grid_x"]}×{r["grid_y"]} '
                  f'기둥 {r["column_mapped"]}/{r["column_high_conf"]} '
                  f'거더 {r["girder_matched"]}/{r["girder_candidates"]} '
                  f'({r["elapsed_s"]}s)')
        except Exception as e:
            print(f'  [{sid}] FAIL: {e}')
            results.append({'sheet_id': sid, 'error': str(e)})

    # 종합 통계
    print(f'\n[종합 통계 — 102동 9도엽]')
    total_columns = sum(r.get('column_mapped', 0) for r in results)
    total_girders = sum(r.get('girder_matched', 0) for r in results)
    total_boxes = sum(r.get('boxes', 0) for r in results)
    total_lines = sum(r.get('lines', 0) for r in results)
    total_wall_pairs = sum(r.get('wall_pairs', 0) for r in results)
    print(f'  LINE 총수: {total_lines}')
    print(f'  박스 총수: {total_boxes}')
    print(f'  벽 페어 총수: {total_wall_pairs}')
    print(f'  기둥 매핑 (conf=1.0 + codex): {total_columns}')
    print(f'  거더 매핑 (격자 위 + codex): {total_girders}')

    # 박제
    os.makedirs('output', exist_ok=True)
    out = {
        'dong': '102',
        'sheet_count': len(results),
        'totals': {
            'lines': total_lines,
            'boxes': total_boxes,
            'wall_pairs': total_wall_pairs,
            'columns_mapped': total_columns,
            'girders_mapped': total_girders,
        },
        'sheets': results,
        'elapsed_total_s': round(time.time() - t0, 1),
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[박제] {OUT_JSON}')

    # MD
    md = [
        '# 102동 9도엽 전체 — F-1 풀스택 (여섯째 호미)',
        '',
        '> 본영 어댑터 ②+① + 분류 + 매핑 통합. 9도엽 모두 처리.',
        '',
        '## 도엽별 결과',
        '',
        '| 도엽 | floor | LINE | 박스 | 벽페어 | 격자 | 기둥(매핑) | 거더(매핑) | 시간 |',
        '|------|:----:|----:|----:|------:|:----:|----------:|----------:|----:|',
    ]
    for r in results:
        if 'error' in r:
            md.append(f'| {r["sheet_id"]} | - | - | - | - | - | ERROR | ERROR | - |')
            continue
        md.append(
            f'| {r["sheet_id"]} | {r["floor_hint"]:+d} | {r["lines"]} | {r["boxes"]} '
            f'| {r["wall_pairs"]} | {r["grid_x"]}×{r["grid_y"]} '
            f'| {r["column_mapped"]} | {r["girder_matched"]} | {r["elapsed_s"]}s |'
        )
    md += ['',
           f'## 종합',
           '',
           f'- 기둥 매핑 총: **{total_columns}건**',
           f'- 거더 매핑 총: **{total_girders}건**',
           f'- 벽 페어 총: {total_wall_pairs}건',
           f'- 처리 시간: {round(time.time()-t0, 1)}초']
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    print(f'[박제] {OUT_MD}')


if __name__ == '__main__':
    main()
