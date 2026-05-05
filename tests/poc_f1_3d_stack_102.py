"""
F-1 3D STEP 재생성 — 일곱째 호미: 50점 회고 §3 직격
=================================================

본영 어댑터 ①·②·③ + F-1 정렬 + 식별 부재로 102동 9도엽 적층 STEP 생성.

[흐름]
  1) 9도엽 처리 (여섯째 호미 재사용)
  2) 각 도엽: 식별된 기둥(폐합 박스 conf=1.0 + codex 매핑)
              식별된 거더(어댑터 ① wall_pair + codex 매핑)
              PC 엔티티 분리 (어댑터 ③ 통계)
  3) F-1 정렬 + Z 적층 (floor × FLOOR_HEIGHT)
  4) FreeCAD Part 솔리드 빌드
  5) STEP 출력

[비교 기준]
  기존: tests/test_102_full_stack.py — 익명 슬라브·벽만, 의미 정합성 없음
  본 PoC: 식별된 기둥·거더 골조 — 의미·식별·정합 모두 포함

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_f1_3d_stack_102.py
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
from core.pc_layer_adapter import RawEntity, classify_entities, PCKind

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-021~029-102동 구조평면도.dxf"
COLUMN_CODEX = "output/codex_columns_unified.json"
GIRDER_CODEX = "output/codex_beams_basement.json"
OUT_STEP = "output/f1_3d_stack_102.step"
OUT_JSON = "output/f1_3d_stack_102.json"

SOURCE_HINT = '101~112동'
CORE1_SW_NORM = (73040.0, 52178.0)
CORE1_W, CORE1_H = 4307.0, 4860.0
CORE2_CX_NORM, CORE2_CY_NORM = 90049.0, 26299.0
CORE2_W, CORE2_H = 4579.0, 4839.0

SHEET_FLOOR = {
    'S30-021': -2, 'S30-022': -1, 'S30-023': 0,
    'S30-024': 1, 'S30-025': 2, 'S30-026': 3, 'S30-027': 4,
    'S30-028': 5, 'S30-029': 6,
}
FLOOR_HEIGHT = 4400  # 표준 층고
GIRDER_H_DEFAULT = 800


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


def extract_pc_stats(msp, sx, sy, sheet_w, sheet_h, inset=0.05):
    """어댑터 ③ — PC 레이어 통계."""
    ix0, iy0 = sx + sheet_w * inset, sy + sheet_h * inset
    ix1, iy1 = sx + sheet_w * (1 - inset), sy + sheet_h * (1 - inset)
    raw = []
    eid = 0
    for e in iter_all(msp):
        try:
            layer = e.dxf.layer
        except Exception:
            continue
        # 도엽 영역 필터 (간단 — 시작점)
        try:
            if e.dxftype() == 'LINE':
                p = e.dxf.start
                if not (ix0 <= p.x <= ix1 and iy0 <= p.y <= iy1):
                    continue
            elif e.dxftype() == 'LWPOLYLINE':
                pts = list(e.get_points())
                if not pts:
                    continue
                p = pts[0]
                if not (ix0 <= p[0] <= ix1 and iy0 <= p[1] <= iy1):
                    continue
        except Exception:
            continue
        raw.append(RawEntity(entity_id=eid, layer=layer,
                              geometry_kind=e.dxftype()))
        eid += 1

    classified = classify_entities(raw)
    summary = {}
    for c in classified:
        summary[c.kind.value] = summary.get(c.kind.value, 0) + 1
    return summary


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
    floor = SHEET_FLOOR.get(sheet_id, 0)

    def to_aligned(pt_abs):
        return (pt_abs[0] - sx - CORE1_SW_NORM[0],
                pt_abs[1] - sy - CORE1_SW_NORM[1])

    lines_raw = extract_lines(msp, sx, sy, sheet_w, sheet_h)
    boxes = extract_boxes(msp, sx, sy, sheet_w, sheet_h)
    pc_stats = extract_pc_stats(msp, sx, sy, sheet_w, sheet_h)

    line_segs = []
    for i, ln in enumerate(lines_raw):
        p1 = to_aligned(ln['p1_abs'])
        p2 = to_aligned(ln['p2_abs'])
        line_segs.append(LineSeg(p1=p1, p2=p2, layer=ln['layer'], line_id=i))

    for b in boxes:
        b['cx_aligned'], b['cy_aligned'] = to_aligned((b['cx_abs'], b['cy_abs']))

    a2 = run_adapter_2(line_segs)
    grid_obj = a2['grid_lines_obj']
    wall_pairs = a2['wall_pairs']

    girders_raw = detect_girders_from_adapter2(
        adapter2_result=a2,
        grid_x=list(grid_obj.x_lines) if grid_obj else [],
        grid_y=list(grid_obj.y_lines) if grid_obj else [],
        girder_codex=girder_codex,
        expected_girder_height=GIRDER_H_DEFAULT,
        require_on_grid=True,
    )

    batch_input = [
        (f'{sheet_id}_box_{i:03d}', b['cx_aligned'], b['cy_aligned'], b['w'], b['h'])
        for i, b in enumerate(boxes)
    ]
    classifications = classify_batch(
        batch_input, core_regions=core_regions, grid=grid_obj,
        column_max_ratio=3.0,
    )

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

    high_conf = [c for c in classifications
                 if c.kind == BoxKind.COLUMN and c.confidence >= 1.0]
    box_by_id = {f'{sheet_id}_box_{i:03d}': boxes[i] for i in range(len(boxes))}

    instances = []
    box_lookup = {}
    for c in high_conf:
        b = box_by_id[c.box_id]
        instances.append(BoxInstance(
            box_id=c.box_id, width=b['w'], height=b['h'],
            label=None, source_hint=SOURCE_HINT, floor_hint=floor,
        ))
        box_lookup[c.box_id] = b

    mappings, _ = map_instances(instances, column_codex)

    # 식별된 기둥 — F-1 정렬 좌표 + 단면 보존
    columns_3d = []
    for m in mappings:
        b = box_lookup[m.box_id]
        columns_3d.append({
            'symbol': m.matched_symbol,
            'cx': b['cx_aligned'],
            'cy': b['cy_aligned'],
            'w': b['w'], 'h': b['h'],
            'codex_w': m.codex_entry.width,
            'codex_h': m.codex_entry.height,
            'confidence': m.confidence,
            'method': m.method,
        })

    # 식별된 거더 — codex 매칭된 것만
    girders_3d = []
    for g in girders_raw:
        if not g.matched_symbol:
            continue
        girders_3d.append({
            'symbol': g.matched_symbol,
            'p1': list(g.centerline_p1),
            'p2': list(g.centerline_p2),
            'thickness': g.thickness,
            'codex_w': g.matched_section[0],
            'codex_h': g.matched_section[1],
            'length': g.length,
            'confidence': g.confidence,
        })

    return {
        'sheet_id': sheet_id,
        'floor': floor,
        'columns': columns_3d,
        'girders': girders_3d,
        'pc_stats': pc_stats,
    }


def build_3d(sheet_results):
    """FreeCAD Part로 식별 부재 → 솔리드 → STEP."""
    import FreeCAD, Part
    shapes = []

    for r in sheet_results:
        floor = r['floor']
        z_base = floor * FLOOR_HEIGHT  # B2F=-8800, B1F=-4400, 1F=0, 2F=4400 ...

        # 기둥 — 폐합 박스 정사각형 extrude
        for col in r['columns']:
            cx, cy = col['cx'], col['cy']
            w, h = col['w'], col['h']
            x0, y0 = cx - w / 2, cy - h / 2
            try:
                pts = [
                    FreeCAD.Vector(x0, y0, z_base),
                    FreeCAD.Vector(x0 + w, y0, z_base),
                    FreeCAD.Vector(x0 + w, y0 + h, z_base),
                    FreeCAD.Vector(x0, y0 + h, z_base),
                ]
                edges = [Part.makeLine(pts[i], pts[(i + 1) % 4]) for i in range(4)]
                wire = Part.Wire(edges)
                face = Part.Face(wire)
                solid = face.extrude(FreeCAD.Vector(0, 0, FLOOR_HEIGHT))
                shapes.append((f'{r["sheet_id"]}_col_{col["symbol"]}', solid))
            except Exception:
                pass

        # 거더 — centerline + thickness × girder_h
        gh = GIRDER_H_DEFAULT  # 단순화
        gh_z_base = z_base + FLOOR_HEIGHT - gh  # 슬라브 하부 (층 천장)
        for g in r['girders']:
            p1, p2 = g['p1'], g['p2']
            t = g['thickness']
            dx = p2[0] - p1[0]; dy = p2[1] - p1[1]
            L = math.hypot(dx, dy)
            if L < 100:
                continue
            ux, uy = dx / L, dy / L
            nx, ny = -uy, ux  # 수직
            half_t = t / 2
            corners = [
                (p1[0] + nx * half_t, p1[1] + ny * half_t),
                (p1[0] - nx * half_t, p1[1] - ny * half_t),
                (p2[0] - nx * half_t, p2[1] - ny * half_t),
                (p2[0] + nx * half_t, p2[1] + ny * half_t),
            ]
            try:
                pts = [FreeCAD.Vector(c[0], c[1], gh_z_base) for c in corners]
                edges = [Part.makeLine(pts[i], pts[(i + 1) % 4]) for i in range(4)]
                wire = Part.Wire(edges)
                face = Part.Face(wire)
                solid = face.extrude(FreeCAD.Vector(0, 0, gh))
                shapes.append((f'{r["sheet_id"]}_gir_{g["symbol"]}', solid))
            except Exception:
                pass

    return shapes


def main():
    print(f'[도면] {DXF}')
    t0 = time.time()
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    print(f'[로드] {time.time()-t0:.1f}s')

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

    core1_sw = (0.0, 0.0); core1_ne = (CORE1_W, CORE1_H)
    core2_sw_n = (CORE2_CX_NORM - CORE2_W / 2, CORE2_CY_NORM - CORE2_H / 2)
    core2_sw = (core2_sw_n[0] - CORE1_SW_NORM[0], core2_sw_n[1] - CORE1_SW_NORM[1])
    core2_ne = (core2_sw[0] + CORE2_W, core2_sw[1] + CORE2_H)
    core_regions = [
        CoreRegion(sw=core1_sw, ne=core1_ne, margin=300),
        CoreRegion(sw=core2_sw, ne=core2_ne, margin=300),
    ]

    column_codex = load_codex(COLUMN_CODEX)
    girder_codex = load_girder_codex(GIRDER_CODEX)

    print(f'[9도엽 처리]')
    sheet_results = []
    for sid in sorted(sheets):
        t1 = time.time()
        sx, sy = sheets[sid]
        try:
            r = process_sheet(msp, sid, sx, sy, sheet_w, sheet_h,
                              column_codex, girder_codex, core_regions)
            sheet_results.append(r)
            pc_total = sum(v for k, v in r['pc_stats'].items() if k != 'non_pc')
            print(f'  [{sid}] floor={r["floor"]:+d} 기둥 {len(r["columns"])} '
                  f'거더 {len(r["girders"])} PC {pc_total} ({time.time()-t1:.1f}s)')
        except Exception as e:
            print(f'  [{sid}] FAIL: {e}')

    # 3D 빌드
    print(f'\n[3D STEP 빌드]')
    import FreeCAD, Part
    shapes = build_3d(sheet_results)
    print(f'  솔리드 {len(shapes)}개')

    if shapes:
        os.makedirs('output', exist_ok=True)
        compound = Part.makeCompound([s for _, s in shapes])
        compound.exportStep(OUT_STEP)
        print(f'[STEP] {OUT_STEP}')

    # 메타 박제
    out = {
        'dong': '102',
        'totals': {
            'columns': sum(len(r['columns']) for r in sheet_results),
            'girders': sum(len(r['girders']) for r in sheet_results),
            'solids': len(shapes),
        },
        'pc_stats_total': {},
        'sheets': sheet_results,
        'elapsed_s': round(time.time() - t0, 1),
    }
    pc_agg = {}
    for r in sheet_results:
        for k, v in r['pc_stats'].items():
            pc_agg[k] = pc_agg.get(k, 0) + v
    out['pc_stats_total'] = pc_agg

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'[메타] {OUT_JSON}')

    print(f'\n[종합]')
    print(f'  기둥 솔리드: {out["totals"]["columns"]}')
    print(f'  거더 솔리드: {out["totals"]["girders"]}')
    print(f'  총 솔리드: {len(shapes)}')
    print(f'  PC 통계: {pc_agg}')
    print(f'  처리 시간: {out["elapsed_s"]}초')


if __name__ == '__main__':
    main()
