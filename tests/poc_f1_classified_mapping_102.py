"""
F-1 + 분류 + Codex 매핑 PoC — 넷째 호미: C1 과매칭 정밀화
=================================================

본영 골격 (core/box_classifier.py) + F-1 anchor + codex 매핑.
50점 회고 §실패 1 (데이터-모델 단절)의 정밀도 진척.

[흐름]
  1) 9도엽 합본 로드 → S30-022 도엽 박스 추출 (정규화 좌표)
  2) F-1 anchor (코어 #1) 적용 → 정렬 좌표
  3) 코어 #1·#2 영역으로 CoreRegion 2개
  4) 박스 cx·cy 클러스터링으로 GridLines (이천 자력)
  5) classify_batch → COLUMN / WALL_SEGMENT / CORE_WALL 분리
  6) COLUMN만 codex_instance_mapper로 매핑 → 정상화 검증

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_f1_classified_mapping_102.py
"""
import os, sys, json, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
from core.f1_anchor_aligner import EVAnchor, F1Aligner
from core.box_classifier import (
    BoxKind, CoreRegion, GridLines,
    classify_batch, report_classification,
)
from core.codex_instance_mapper import (
    BoxInstance, load_codex, map_instances, save_mappings,
)

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-021~029-102동 구조평면도.dxf"
CODEX = "output/codex_columns_unified.json"
OUT_JSON = "output/f1_classified_mapping_102_S30-022.json"
OUT_MD = "output/f1_classified_mapping_102_S30-022.md"

TARGET_SHEET = 'S30-022'
SOURCE_HINT = '101~112동'
FLOOR_HINT = -1


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


def extract_column_boxes(msp, sheet_id, sx, sy, sheet_w, sheet_h,
                         w_min=400, w_max=3000, inset=0.05):
    """기둥 후보 폐합 사각형 추출 (정규화 좌표 dict)."""
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


def extract_grid_from_boxes(boxes_aligned, tol=300, min_members=4):
    """이천 자력 — 박스 중심 cx·cy 클러스터링으로 격자 LINE 추출.

    강화: 멤버 ≥ N개 클러스터만 격자 LINE 채택 (진짜 격자만).
    가설: 기둥 다수가 같은 X·Y에 → 4건 이상 모이면 격자 라인.
    """
    def cluster_1d(values, tol, min_members):
        if not values:
            return []
        sorted_v = sorted(values)
        clusters = []
        cur = [sorted_v[0]]
        for v in sorted_v[1:]:
            if v - cur[-1] <= tol:
                cur.append(v)
            else:
                if len(cur) >= min_members:
                    clusters.append(sum(cur) / len(cur))
                cur = [v]
        if len(cur) >= min_members:
            clusters.append(sum(cur) / len(cur))
        return clusters

    cxs = [b['cx_aligned'] for b in boxes_aligned]
    cys = [b['cy_aligned'] for b in boxes_aligned]
    return GridLines(
        x_lines=tuple(cluster_1d(cxs, tol, min_members)),
        y_lines=tuple(cluster_1d(cys, tol, min_members)),
        intersection_tol=200.0,
    )


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

    # 2. 박스 추출 + F-1 정렬
    boxes = extract_column_boxes(msp, TARGET_SHEET, sx, sy, sheet_w, sheet_h)
    print(f'[박스 추출] {len(boxes)}개')

    # F-1 anchor (둘째 호미 결과 — 정규화 좌표 SW)
    core1_sw_norm = (73040.0, 52178.0)
    core1_w, core1_h = 4307.0, 4860.0
    # 코어 #2 정규화 좌표 (둘째 호미 결과)
    core2_cx_norm, core2_cy_norm = 90049.0, 26299.0
    core2_w, core2_h = 4579.0, 4839.0
    core2_sw_norm = (core2_cx_norm - core2_w / 2, core2_cy_norm - core2_h / 2)

    # F-1 정렬 (anchor = 코어 #1 SW = 원점)
    # 정규화 좌표에서 anchor SW를 빼면 정렬 좌표
    def to_aligned_norm(pt_norm):
        return (pt_norm[0] - core1_sw_norm[0], pt_norm[1] - core1_sw_norm[1])

    for b in boxes:
        cx_norm = b['cx_abs'] - sx
        cy_norm = b['cy_abs'] - sy
        b['cx_aligned'], b['cy_aligned'] = to_aligned_norm((cx_norm, cy_norm))

    # 3. CoreRegion 2개 (정렬 좌표)
    core1_sw_aligned = to_aligned_norm(core1_sw_norm)  # = (0, 0)
    core1_ne_aligned = (core1_sw_aligned[0] + core1_w, core1_sw_aligned[1] + core1_h)
    core2_sw_aligned = to_aligned_norm(core2_sw_norm)
    core2_ne_aligned = (core2_sw_aligned[0] + core2_w, core2_sw_aligned[1] + core2_h)

    core_regions = [
        CoreRegion(sw=core1_sw_aligned, ne=core1_ne_aligned, margin=300),
        CoreRegion(sw=core2_sw_aligned, ne=core2_ne_aligned, margin=300),
    ]
    print(f'[코어 영역]')
    print(f'  #1 aligned: SW={core1_sw_aligned} NE={core1_ne_aligned}')
    print(f'  #2 aligned: SW={core2_sw_aligned} NE={core2_ne_aligned}')

    # 4. 격자 LINE 추출 (이천 자력)
    grid = extract_grid_from_boxes(boxes, tol=200)
    print(f'[격자 추출] X 라인 {len(grid.x_lines)}개, Y 라인 {len(grid.y_lines)}개')
    if len(grid.x_lines) <= 30:
        print(f'  X: {[round(x) for x in grid.x_lines]}')
    if len(grid.y_lines) <= 30:
        print(f'  Y: {[round(y) for y in grid.y_lines]}')

    # 5. 분류
    batch_input = [
        (f'102_{TARGET_SHEET}_box_{i:03d}', b['cx_aligned'], b['cy_aligned'],
         b['w'], b['h'])
        for i, b in enumerate(boxes)
    ]
    classifications = classify_batch(
        batch_input, core_regions=core_regions, grid=grid, column_max_ratio=3.0,
    )
    by_kind = {}
    for c in classifications:
        by_kind[c.kind.value] = by_kind.get(c.kind.value, 0) + 1
    print(f'\n[분류 결과]')
    for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v} ({100*v/len(classifications):.1f}%)')

    # 신뢰도별 분포
    by_conf = {}
    for c in classifications:
        bucket = round(c.confidence, 1)
        by_conf[bucket] = by_conf.get(bucket, 0) + 1
    print(f'  conf 분포: {sorted(by_conf.items(), reverse=True)}')

    # 6. COLUMN 중 conf>=1.0 (격자 위 진짜 기둥)만 codex 매핑
    column_classifications = [c for c in classifications if c.kind == BoxKind.COLUMN]
    high_conf_columns = [c for c in column_classifications if c.confidence >= 1.0]
    mid_conf_columns = [c for c in column_classifications if 0.7 <= c.confidence < 1.0]
    low_conf_columns = [c for c in column_classifications if c.confidence < 0.7]
    print(f'\n[COLUMN 분류] 총 {len(column_classifications)}')
    print(f'  conf 1.0 (격자 위 진짜 기둥): {len(high_conf_columns)}')
    print(f'  conf 0.7 (코어 안 기둥):     {len(mid_conf_columns)}')
    print(f'  conf 0.4 (격자·코어 밖):     {len(low_conf_columns)} ← 의심 (벽 segment 가능)')

    # 진짜 기둥(conf>=1.0)만 매핑
    box_by_id = {f'102_{TARGET_SHEET}_box_{i:03d}': boxes[i] for i in range(len(boxes))}
    print(f'\n[codex 매핑] conf>=1.0 박스 {len(high_conf_columns)}개')

    instances = []
    for c in high_conf_columns:
        b = box_by_id[c.box_id]
        instances.append(BoxInstance(
            box_id=c.box_id,
            width=b['w'], height=b['h'],
            label=None,
            source_hint=SOURCE_HINT,
            floor_hint=FLOOR_HINT,
        ))

    codex = load_codex(CODEX)
    mappings, unmatched = map_instances(instances, codex)
    print(f'  매핑 성공: {len(mappings)} / 실패: {len(unmatched)} '
          f'(매칭률 {100*len(mappings)/(len(instances) or 1):.1f}%)')

    # symbol 분포
    by_symbol = {}
    for m in mappings:
        by_symbol[m.matched_symbol] = by_symbol.get(m.matched_symbol, 0) + 1
    print(f'  symbol별 (top 10):')
    for k, v in sorted(by_symbol.items(), key=lambda x: -x[1])[:10]:
        print(f'    {k}: {v}')

    # 7. 박제
    os.makedirs('output', exist_ok=True)

    # 분류 결과 + 매핑 + 박스 좌표
    out = {
        'sheet_id': TARGET_SHEET,
        'dong': '102',
        'floor_hint': FLOOR_HINT,
        'anchor': {
            'core1_sw_norm': list(core1_sw_norm),
            'core1_w': core1_w, 'core1_h': core1_h,
        },
        'core_regions': [
            {'sw': list(r.sw), 'ne': list(r.ne), 'margin': r.margin}
            for r in core_regions
        ],
        'grid': {
            'x_lines': [round(x, 1) for x in grid.x_lines],
            'y_lines': [round(y, 1) for y in grid.y_lines],
            'tol': grid.intersection_tol,
        },
        'box_count': len(boxes),
        'classification_summary': by_kind,
        'classifications': [
            {
                'box_id': c.box_id,
                'kind': c.kind.value,
                'aspect_ratio': round(c.aspect_ratio, 2),
                'in_core': c.in_core,
                'on_grid_intersection': c.on_grid_intersection,
                'confidence': c.confidence,
                'reason': c.reason,
            }
            for c in classifications
        ],
        'mapping_summary': {
            'matched': len(mappings),
            'unmatched': len(unmatched),
            'symbols': by_symbol,
        },
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[박제] {OUT_JSON}')

    # MD 리포트
    md_lines = [
        f'# F-1 + 분류 + Codex 매핑 — 102동 {TARGET_SHEET} (B1F)',
        '',
        '> 넷째 호미: C1 과매칭 정밀화. β·γ·α 통합 분류.',
        '',
        f'## 분류 결과',
        '',
        f'| 종류 | 개수 | 비율 |',
        f'|------|-----:|-----:|',
    ]
    for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
        md_lines.append(f'| {k} | {v} | {100*v/len(classifications):.1f}% |')

    md_lines += [
        '',
        '## COLUMN 박스 → codex 매핑',
        '',
        f'- 분류 COLUMN: **{len(column_classifications)}**',
        f'- 매핑 성공: **{len(mappings)}** ({100*len(mappings)/(len(instances) or 1):.1f}%)',
        f'- 매핑 실패: **{len(unmatched)}**',
        '',
        '### Symbol 분포 (top 15)',
        '',
        '| Symbol | 매칭 수 |',
        '|--------|------:|',
    ]
    for k, v in sorted(by_symbol.items(), key=lambda x: -x[1])[:15]:
        md_lines.append(f'| {k} | {v} |')

    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    print(f'[박제] {OUT_MD}')


if __name__ == '__main__':
    main()
