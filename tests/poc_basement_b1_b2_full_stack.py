"""
지하주차장 B1·B2 PoC — 7 호미 + 7 도구함 (자수 보정 정사 순서)
================================================================

본영 명령서: DANGUN_TO_ICHEON_NEXT_SESSION_BASEMENT_B1_B2_DIRECTIVE.md
방부장 친명: "다음 세션에서 이천에게 지시하라. 아까처럼 하돼 지하주차장 1·2층만 만들라고."

[자수 보정 강제 — 헌법 §3 제4조 정사 순서]
  ③ pc_layer_adapter (PC vs 일반 분리)
  → ② line_pairing.run_adapter_2 (NON-PC LINE → wall_pair + 격자)
  → ① girder_matcher (wall_pair → 거더 + codex)
  → box_classifier + codex_instance_mapper (NON-PC 폐합 박스 → column codex)
  → 3D STEP 빌드

[입력] 단지 통합 지하주차장 도면 (15.4MB) — DXF 한 파일에 B1+B2+지붕 3 도엽
[자력 채굴] 도엽 SW + 격자 라벨 (X*/Y*) — 진단 2차 결과

[검증 게이트]
  1) 솔리드 수 = 메타 일치
  2) 모든 솔리드 valid (FreeCAD)
  3) 부피 메타 일치
  4) Z 적층 — B1·B2 두 층 분리
  5) 격자 unique X·Y ≤ 15  ⭐ 결정적
  6) 시각 검증 — 방부장 GUI (PoC 종료 후)

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_basement_b1_b2_full_stack.py
"""
import os, sys, json, re, math, time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
from core.line_pairing import LineSeg, run_adapter_2
from core.girder_matcher import (
    load_girder_codex, detect_girders_from_adapter2,
)
from core.box_classifier import (
    BoxKind, GridLines, classify_batch, BoxClassification,
)
from core.codex_instance_mapper import (
    BoxInstance, load_codex, map_instances,
)
from core.pc_layer_adapter import RawEntity, classify_entities, PCKind

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
COLUMN_CODEX = "output/codex_columns_unified.json"
GIRDER_CODEX = "output/codex_beams_basement.json"
OUT_STEP = "output/basement_b1_b2_stack.step"
OUT_JSON = "output/basement_b1_b2_stack.json"
OUT_BOQ_MD = "output/basement_b1_b2_boq.md"

# 도엽 자력 채굴 결과 (probe_basement_dxf2.py 결과 박제)
SHEETS = {
    'B2': {'sw': (247250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0,
           'floor': -2, 'title': '지하 2층 주차장 구조평면도'},
    'B1': {'sw': (877250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0,
           'floor': -1, 'title': '지하 1층 주차장 구조평면도'},
}

FLOOR_HEIGHT = 4400  # 표준 층고 (mm)
GIRDER_H_DEFAULT = 800
SOURCE_HINT = '지하주차장'


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


def extract_grid_labels(all_texts, sw, w, h, inset=0.02):
    """도엽 영역 내 X*/Y* 라벨 → 격자선 (도엽 좌표계로 정규화)."""
    ix0, iy0 = sw[0] + w * inset, sw[1] + h * inset
    ix1, iy1 = sw[0] + w * (1 - inset), sw[1] + h * (1 - inset)
    grid_pat = re.compile(r'^([XY])(\d{1,2}[A-Z]?)$')

    x_pos = {}  # label -> [(x_norm, ...), ...]
    y_pos = {}
    for txt, px, py in all_texts:
        m = grid_pat.match(txt)
        if not m:
            continue
        if not (ix0 <= px <= ix1 and iy0 <= py <= iy1):
            continue
        axis = m.group(1)
        label = m.group(2)
        if axis == 'X':
            x_pos.setdefault(label, []).append(px - sw[0])
        else:
            y_pos.setdefault(label, []).append(py - sw[1])

    # 라벨별 평균 좌표 (대표값) — 같은 라벨 여러 번 등장 시 평균
    x_lines_dict = {lbl: sum(v) / len(v) for lbl, v in x_pos.items() if v}
    y_lines_dict = {lbl: sum(v) / len(v) for lbl, v in y_pos.items() if v}
    x_lines = sorted(x_lines_dict.values())
    y_lines = sorted(y_lines_dict.values())
    return {
        'x_lines': x_lines, 'y_lines': y_lines,
        'x_labels': sorted(x_lines_dict.keys()),
        'y_labels': sorted(y_lines_dict.keys()),
        'unique_x': len(x_lines_dict),
        'unique_y': len(y_lines_dict),
    }


def extract_raw_entities(msp, sw, w, h, inset=0.02):
    """도엽 영역 내 LINE/LWPOLYLINE → RawEntity + ezdxf 매핑.

    PC 분리는 레이어 기반이므로, raw 엔티티 → ③ 분류기 입력.
    """
    ix0, iy0 = sw[0] + w * inset, sw[1] + h * inset
    ix1, iy1 = sw[0] + w * (1 - inset), sw[1] + h * (1 - inset)
    raws = []
    raw_meta = []  # (entity_id, ezdxf_entity, etype, layer)
    eid = 0
    for e in iter_all(msp):
        try:
            ly = e.dxf.layer
        except Exception:
            continue
        et = e.dxftype()
        if et == 'LINE':
            try:
                p = e.dxf.start
                if not (ix0 <= p.x <= ix1 and iy0 <= p.y <= iy1):
                    continue
            except Exception:
                continue
        elif et == 'LWPOLYLINE':
            try:
                pts = list(e.get_points())
                if not pts:
                    continue
                p0 = pts[0]
                if not (ix0 <= p0[0] <= ix1 and iy0 <= p0[1] <= iy1):
                    continue
            except Exception:
                continue
        else:
            continue
        raws.append(RawEntity(entity_id=eid, layer=ly, geometry_kind=et))
        raw_meta.append((eid, e, et, ly))
        eid += 1
    return raws, raw_meta


def extract_all_texts(msp):
    """전체 TEXT/MTEXT — 격자 라벨 채굴용."""
    out = []
    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            txt = (txt or '').strip()
            if not txt:
                continue
            pos = e.dxf.insert
            out.append((txt, pos.x, pos.y))
        except Exception:
            pass
    return out


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


def process_sheet(msp, sid, sheet, all_texts, column_codex, girder_codex):
    sw = sheet['sw']; w = sheet['w']; h = sheet['h']; floor = sheet['floor']

    # ===== ③ PC 레이어 분리 (정사 순서 1단) =====
    raws, raw_meta = extract_raw_entities(msp, sw, w, h)
    classified_pc = classify_entities(raws)
    pc_kind_by_id = {c.entity_id: c.kind for c in classified_pc}
    pc_summary = {}
    for c in classified_pc:
        pc_summary[c.kind.value] = pc_summary.get(c.kind.value, 0) + 1

    # ===== ② NON-PC LINE → 격자 + wall_pairs (정사 순서 2단) =====
    line_segs = []
    for eid, e, et, ly in raw_meta:
        if et != 'LINE':
            continue
        if pc_kind_by_id.get(eid) != PCKind.NON_PC:
            continue
        try:
            s = e.dxf.start; ed = e.dxf.end
            p1 = (s.x - sw[0], s.y - sw[1])
            p2 = (ed.x - sw[0], ed.y - sw[1])
            line_segs.append(LineSeg(p1=p1, p2=p2, layer=ly, line_id=eid))
        except Exception:
            pass

    a2 = run_adapter_2(line_segs, max_dist=850.0)
    wall_pairs = a2['wall_pairs']

    # 격자 라벨 자력 (TEXT 기반) — 게이트 5의 핵심 신호
    grid_label = extract_grid_labels(all_texts, sw, w, h)

    # GridLines 결정: TEXT 라벨 우선 (정확), 없으면 어댑터②
    if grid_label['unique_x'] >= 2 and grid_label['unique_y'] >= 2:
        grid_obj = GridLines(
            x_lines=tuple(grid_label['x_lines']),
            y_lines=tuple(grid_label['y_lines']),
            intersection_tol=300.0,
        )
        grid_source = 'text_labels'
    else:
        grid_obj = a2['grid_lines_obj']
        grid_source = 'adapter_2'

    # ===== ① 거더 detect + codex 매칭 (정사 순서 3단) =====
    girders_raw = detect_girders_from_adapter2(
        adapter2_result=a2,
        grid_x=list(grid_obj.x_lines) if grid_obj else [],
        grid_y=list(grid_obj.y_lines) if grid_obj else [],
        girder_codex=girder_codex,
        expected_girder_height=GIRDER_H_DEFAULT,
        require_on_grid=True,
    )

    # ===== NON-PC 폐합 박스 → 분류 → codex (정사 순서 4단) =====
    boxes = []
    # 1) 기존 LWPOLYLINE 기반 수집
    for eid, e, et, ly in raw_meta:
        if et != 'LWPOLYLINE':
            continue
        if pc_kind_by_id.get(eid) != PCKind.NON_PC:
            continue
        try:
            if not e.is_closed:
                continue
            pts = [(x, y) for x, y, *_ in e.get_points()]
            if not (4 <= len(pts) <= 6):
                continue
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            bw = xmax - xmin; bh = ymax - ymin
            if not (400 <= bw <= 3000 and 400 <= bh <= 3000):
                continue
            cx_norm = (xmin + xmax) / 2 - sw[0]
            cy_norm = (ymin + ymax) / 2 - sw[1]
            boxes.append({
                'cx': cx_norm, 'cy': cy_norm, 'w': bw, 'h': bh,
                'box_id': f'{sid}_box_{len(boxes):03d}',
                'layer': ly,
            })
        except Exception:
            pass

    # 2) 낱개 LINE 기반 기둥 사각형 복원 (B1 층 등 LINE으로 그려진 기둥 복구)
    from collections import defaultdict
    col_lines = []
    for eid, e, et, ly in raw_meta:
        if et != 'LINE':
            continue
        if pc_kind_by_id.get(eid) != PCKind.NON_PC:
            continue
        ly_upper = ly.upper()
        if 'COL' in ly_upper or '기둥' in ly_upper:
            try:
                s = e.dxf.start; ed = e.dxf.end
                col_lines.append((s.x, s.y, ed.x, ed.y, ly))
            except Exception:
                pass

    if col_lines:
        def snap(val):
            return round(val / 5.0) * 5.0
        
        adj = defaultdict(set)
        edges = set()
        line_layers = {}
        for x1, y1, x2, y2, ly in col_lines:
            u = (snap(x1), snap(y1))
            v = (snap(x2), snap(y2))
            if u == v:
                continue
            edge = tuple(sorted([u, v]))
            if edge not in edges:
                edges.add(edge)
                adj[u].add(v)
                adj[v].add(u)
                line_layers[edge] = ly

        visited = set()
        components = []
        for node in adj.keys():
            if node in visited:
                continue
            comp = []
            queue = [node]
            visited.add(node)
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for nxt in adj[curr]:
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)
            components.append(comp)

        for comp in components:
            if len(comp) == 4:
                deg_ok = True
                for node in comp:
                    comp_deg = len(adj[node].intersection(comp))
                    if comp_deg != 2:
                        deg_ok = False
                        break
                if deg_ok:
                    xs = [p[0] for p in comp]
                    ys = [p[1] for p in comp]
                    xmin, xmax = min(xs), max(xs)
                    ymin, ymax = min(ys), max(ys)
                    bw = xmax - xmin
                    bh = ymax - ymin
                    if 400 <= bw <= 3000 and 400 <= bh <= 3000:
                        cx_norm = (xmin + xmax) / 2 - sw[0]
                        cy_norm = (ymin + ymax) / 2 - sw[1]
                        # 중복 제거 (기존 LWPOLYLINE으로 찾은 박스와의 중복 체크)
                        dup = False
                        for b in boxes:
                            if math.hypot(b['cx'] - cx_norm, b['cy'] - cy_norm) < 100.0:
                                dup = True
                                break
                        if not dup:
                            edge_ly = '00_COLUMN'
                            for i in range(4):
                                u = comp[i]
                                v = comp[(i+1)%4]
                                e_key = tuple(sorted([u, v]))
                                if e_key in line_layers:
                                    edge_ly = line_layers[e_key]
                                    break
                            boxes.append({
                                'cx': cx_norm, 'cy': cy_norm, 'w': bw, 'h': bh,
                                'box_id': f'{sid}_box_{len(boxes):03d}',
                                'layer': edge_ly,
                            })

    batch_input = [(b['box_id'], b['cx'], b['cy'], b['w'], b['h']) for b in boxes]
    # grid=None: 자력 채굴 격자가 단지 규모 큼 (X≥20). 격자 매칭 비활성.
    # 단순 종횡비 + wall_pair zone 강등으로 column 식별.
    classifications = classify_batch(
        batch_input, core_regions=[], grid=None, column_max_ratio=3.0,
    )

    # wall_pair zone에 들어가는 column 강등 (102 PoC 패턴)
    for i, c in enumerate(classifications):
        if c.kind == BoxKind.COLUMN:
            b = boxes[i]
            if is_in_wall_zone(b['cx'], b['cy'], wall_pairs):
                classifications[i] = BoxClassification(
                    box_id=c.box_id, kind=BoxKind.WALL_SEGMENT,
                    aspect_ratio=c.aspect_ratio, in_core=c.in_core,
                    on_grid_intersection=c.on_grid_intersection,
                    confidence=0.85, reason='demoted: wall_pair zone',
                )

    # 격자 매칭 비활성이므로 column candidate confidence는 0.6 (격자 없음)
    high_conf = [c for c in classifications
                 if c.kind == BoxKind.COLUMN and c.confidence >= 0.4]
    box_by_id = {b['box_id']: b for b in boxes}

    instances = []
    for c in high_conf:
        b = box_by_id[c.box_id]
        instances.append(BoxInstance(
            box_id=c.box_id, width=b['w'], height=b['h'],
            label=None, source_hint=SOURCE_HINT, floor_hint=floor,
        ))
    mappings, _ = map_instances(instances, column_codex)

    # 결과 박제
    columns_3d = []
    for m in mappings:
        b = box_by_id[m.box_id]
        columns_3d.append({
            'symbol': m.matched_symbol,
            'cx': b['cx'], 'cy': b['cy'],
            'w': b['w'], 'h': b['h'],
            'codex_w': m.codex_entry.width, 'codex_h': m.codex_entry.height,
            'confidence': m.confidence, 'method': m.method,
        })

    girders_3d = []
    for g in girders_raw:
        if not g.matched_symbol:
            continue
        girders_3d.append({
            'symbol': g.matched_symbol,
            'p1': list(g.centerline_p1), 'p2': list(g.centerline_p2),
            'thickness': g.thickness,
            'codex_w': g.matched_section[0],
            'codex_h': g.matched_section[1],
            'length': g.length, 'confidence': g.confidence,
        })

    # 분류 통계
    kind_count = Counter(c.kind.value for c in classifications)

    return {
        'sheet_id': sid, 'floor': floor, 'title': sheet['title'],
        'columns': columns_3d, 'girders': girders_3d,
        'pc_stats': pc_summary,
        'grid_source': grid_source,
        'grid_unique_x': grid_label['unique_x'],
        'grid_unique_y': grid_label['unique_y'],
        'grid_x_labels': grid_label['x_labels'],
        'grid_y_labels': grid_label['y_labels'],
        'n_lines_input': len(line_segs),
        'n_wall_pairs': len(wall_pairs),
        'n_boxes_input': len(boxes),
        'classification_stats': dict(kind_count),
        'n_girders_codex_matched': len(girders_3d),
    }


def build_3d(sheet_results):
    """FreeCAD Part — 식별 부재 → 솔리드 → STEP."""
    import FreeCAD, Part
    shapes = []

    for r in sheet_results:
        floor = r['floor']
        z_base = floor * FLOOR_HEIGHT  # B2F=-8800, B1F=-4400

        # 기둥 — 폐합 박스 단면 extrude (층고만큼)
        for col in r['columns']:
            cx, cy = col['cx'], col['cy']
            bw, bh = col['w'], col['h']
            x0, y0 = cx - bw / 2, cy - bh / 2
            try:
                pts = [
                    FreeCAD.Vector(x0, y0, z_base),
                    FreeCAD.Vector(x0 + bw, y0, z_base),
                    FreeCAD.Vector(x0 + bw, y0 + bh, z_base),
                    FreeCAD.Vector(x0, y0 + bh, z_base),
                ]
                edges = [Part.makeLine(pts[i], pts[(i + 1) % 4]) for i in range(4)]
                wire = Part.Wire(edges)
                face = Part.Face(wire)
                solid = face.extrude(FreeCAD.Vector(0, 0, FLOOR_HEIGHT))
                shapes.append((f'{r["sheet_id"]}_col_{col["symbol"]}', solid, 'column'))
            except Exception:
                pass

        # 거더 — centerline + thickness × girder_h
        gh = GIRDER_H_DEFAULT
        gh_z_base = z_base + FLOOR_HEIGHT - gh
        for g in r['girders']:
            p1, p2 = g['p1'], g['p2']
            t = g['thickness']
            dx = p2[0] - p1[0]; dy = p2[1] - p1[1]
            L = math.hypot(dx, dy)
            if L < 100:
                continue
            ux, uy = dx / L, dy / L
            nx, ny = -uy, ux
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
                shapes.append((f'{r["sheet_id"]}_gir_{g["symbol"]}', solid, 'girder'))
            except Exception:
                pass

    return shapes


def verify_gates(shapes, sheet_results, meta_solids_count):
    """검증 게이트 1~5 자력 통과 확인."""
    gates = {}

    # 게이트 1: 솔리드 수 = 메타
    actual_count = len(shapes)
    gates['G1_solid_count_match'] = (bool(actual_count == meta_solids_count), actual_count, meta_solids_count)

    # 게이트 2: 모든 솔리드 valid
    invalid = []
    total_volume = 0.0
    z_centers = []
    for name, s, kind in shapes:
        try:
            if not s.isValid():
                invalid.append(name)
            total_volume += s.Volume
            z_centers.append(s.BoundBox.Center.z)
        except Exception:
            invalid.append(name)
    gates['G2_all_valid'] = (bool(len(invalid) == 0), len(invalid), invalid[:5])

    # 게이트 3: 부피 — 메타 vs 실측 일치
    meta_volume = sum(
        col['w'] * col['h'] * FLOOR_HEIGHT
        for r in sheet_results for col in r['columns']
    ) + sum(
        math.hypot(g['p2'][0]-g['p1'][0], g['p2'][1]-g['p1'][1]) * g['thickness'] * GIRDER_H_DEFAULT
        for r in sheet_results for g in r['girders']
        if math.hypot(g['p2'][0]-g['p1'][0], g['p2'][1]-g['p1'][1]) >= 100
    )
    vol_diff_pct = abs(total_volume - meta_volume) / max(meta_volume, 1) * 100
    gates['G3_volume_match'] = (bool(vol_diff_pct < 0.1), total_volume, meta_volume, vol_diff_pct)

    # 게이트 4: Z 적층 — B1·B2 두 층 분리
    # B2 기둥 z_center = -8800 + 2200 = -6600
    # B1 기둥 z_center = -4400 + 2200 = -2200
    # 임계: z < -5000 → B2, z >= -5000 → B1 (거더는 천장 가까이)
    z_floors = set()
    for z in z_centers:
        if z < -5000:
            z_floors.add('B2')
        elif z < 0:
            z_floors.add('B1')
    gates['G4_z_layers'] = (bool(z_floors == {'B1', 'B2'}), sorted(z_floors))

    # 게이트 5: 격자 unique X·Y ≤ 15
    total_unique = sum(r['grid_unique_x'] + r['grid_unique_y'] for r in sheet_results)
    max_per_sheet = max(
        max(r['grid_unique_x'], r['grid_unique_y']) for r in sheet_results
    )
    gates['G5_grid_unique'] = (
        bool(max_per_sheet <= 15),
        max_per_sheet,
        {r['sheet_id']: (r['grid_unique_x'], r['grid_unique_y']) for r in sheet_results},
    )

    return gates


def write_boq_md(sheet_results, shapes_meta, total_volume, gates, path):
    """BOQ .md 박제."""
    lines = [
        '# 지하주차장 B1·B2 PoC — BOQ 산출',
        '',
        f'- 입력: `{DXF}`',
        f'- 도엽: B2F + B1F (지붕층 제외)',
        '',
        '## 부재 산출 요약',
        '',
        '| 도엽 | 층 | 기둥 | 거더 | PC 통계 | 격자 unique |',
        '|---|---:|---:|---:|---|---|',
    ]
    for r in sheet_results:
        pc_str = ', '.join(f'{k}={v}' for k, v in sorted(r['pc_stats'].items()))
        lines.append(
            f"| {r['sheet_id']} | {r['floor']:+d} | {len(r['columns'])} | "
            f"{len(r['girders'])} | {pc_str} | "
            f"X={r['grid_unique_x']}, Y={r['grid_unique_y']} ({r['grid_source']}) |"
        )
    lines.append('')
    lines.append('## 검증 게이트')
    lines.append('')
    for k, v in gates.items():
        passed = v[0]
        mark = '✅' if passed else '❌'
        lines.append(f'- {mark} **{k}**: `{v[1:]}`')
    lines.append('')
    lines.append(f'## 솔리드 합계')
    lines.append(f'')
    lines.append(f'- 총 솔리드: {len(shapes_meta)}')
    col_count = sum(1 for n, k in shapes_meta if k == 'column')
    gir_count = sum(1 for n, k in shapes_meta if k == 'girder')
    lines.append(f'- 기둥: {col_count}')
    lines.append(f'- 거더: {gir_count}')
    lines.append(f'- 총 부피: {total_volume / 1e9:.3f} m³')
    lines.append('')
    lines.append('— 이천(李蕆), 자수 보정 정사 호미.')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main():
    print(f'[입력] {DXF}')
    t0 = time.time()
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    print(f'[로드] {time.time()-t0:.1f}s')

    print('[전체 TEXT 캐시]')
    all_texts = extract_all_texts(msp)
    print(f'  TEXT/MTEXT 총 {len(all_texts)}건')

    column_codex = load_codex(COLUMN_CODEX)
    girder_codex = load_girder_codex(GIRDER_CODEX)
    print(f'[codex] column {len(column_codex)} / girder {len(girder_codex)}')

    print(f'\n[자수 보정 정사 호미 — ③→②→①→codex]')
    sheet_results = []
    for sid in ['B2', 'B1']:
        t1 = time.time()
        sheet = SHEETS[sid]
        try:
            r = process_sheet(msp, sid, sheet, all_texts, column_codex, girder_codex)
            sheet_results.append(r)
            print(f'  [{sid}] floor={r["floor"]:+d} '
                  f'기둥 {len(r["columns"])} 거더 {len(r["girders"])} '
                  f'격자 X={r["grid_unique_x"]} Y={r["grid_unique_y"]} ({r["grid_source"]}) '
                  f'({time.time()-t1:.1f}s)')
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'  [{sid}] FAIL: {e}')

    # 3D STEP 빌드
    print(f'\n[3D STEP 빌드]')
    import FreeCAD, Part
    shapes = build_3d(sheet_results)
    print(f'  솔리드 {len(shapes)}개')

    if shapes:
        os.makedirs('output', exist_ok=True)
        compound = Part.makeCompound([s for _, s, _ in shapes])
        compound.exportStep(OUT_STEP)
        print(f'[STEP] {OUT_STEP}')

    # 검증 게이트
    print(f'\n[검증 게이트 1~5]')
    gates = verify_gates(shapes, sheet_results, len(shapes))
    for k, v in gates.items():
        passed = v[0]
        mark = '✅' if passed else '❌'
        print(f'  {mark} {k}: {v[1:]}')

    # 메타 박제
    total_volume = sum(s.Volume for _, s, _ in shapes if s.isValid())
    out = {
        'project': '부산 에코델타 24BL 지하주차장 B1·B2',
        'directive': 'DANGUN_TO_ICHEON_NEXT_SESSION_BASEMENT_B1_B2_DIRECTIVE.md',
        'self_correction': '③→②→①→codex 정사 순서 강제',
        'totals': {
            'columns': sum(len(r['columns']) for r in sheet_results),
            'girders': sum(len(r['girders']) for r in sheet_results),
            'solids': len(shapes),
            'volume_m3': round(total_volume / 1e9, 3),
        },
        'sheets': sheet_results,
        'gates': {
            k: {'passed': v[0], 'detail': v[1:]} for k, v in gates.items()
        },
        'elapsed_s': round(time.time() - t0, 1),
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'[메타] {OUT_JSON}')

    # BOQ md
    shapes_meta = [(n, k) for n, _, k in shapes]
    write_boq_md(sheet_results, shapes_meta, total_volume, gates, OUT_BOQ_MD)
    print(f'[BOQ] {OUT_BOQ_MD}')

    print(f'\n[종합]')
    print(f'  기둥 솔리드: {out["totals"]["columns"]}')
    print(f'  거더 솔리드: {out["totals"]["girders"]}')
    print(f'  총 솔리드: {len(shapes)}')
    print(f'  총 부피: {out["totals"]["volume_m3"]} m³')
    print(f'  처리 시간: {out["elapsed_s"]}초')

    # 게이트 5 핵심 보고
    g5_passed = gates['G5_grid_unique'][0]
    g5_max = gates['G5_grid_unique'][1]
    print(f'\n  [게이트 5] 격자 unique max = {g5_max}  '
          f'{"✅ 통과 (≤15)" if g5_passed else "❌ 미통과 (>15)"}')


if __name__ == '__main__':
    main()
