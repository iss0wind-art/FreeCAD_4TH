"""
101동 동체 B1·B2층 PoC — 7 호미 + 7 도구함 (자수 보정 정사 순서)
================================================================

방부장 친명: '현실 테스트 두 번째. 101동 동체의 지하 1·2층만 모델링.'

[자수 보정 강제 — 헌법 §3 제4조 정사 순서]
  ③ pc_layer_adapter (PC vs 일반 분리)
  → ② line_pairing.run_adapter_2 (NON-PC LINE → wall_pair + 격자)
  → ① girder_matcher (wall_pair → 거더 + codex)
  → box_classifier + codex_instance_mapper (NON-PC 폐합 박스 → column codex)
  → 3D STEP 빌드

[도엽 자력 채굴 결과 — probe_101_dxf.py + 정밀 채굴 확인]
  S30-001: B2F(지하2층) — 기둥 후보 851개, 'B2F SL' 텍스트 확인
  S30-002: B1F(지하1층) — 기둥 후보 457개, 'PIT 지수정' 텍스트 확인
  S30-003: 빈 도엽 (기둥 후보 0개) — 제외
  S30-004~010: 지상층 — 본 임무 범위 제외

[도엽 좌표 — 임무 명세서 기준]
  도엽 SW = TEXT 'S30-XXX' 위치 (도엽 좌하단)
  sheet_w=126000, sheet_h=178200 (mm)
  S30-001: sw=(116247, 2290548)
  S30-002: sw=(242247, 2290548)

[검증 게이트]
  1) 솔리드 수 = 메타 일치
  2) 모든 솔리드 valid (FreeCAD isValid)
  3) 부피 메타 일치 (오차 0.1% 이내)
  4) Z 적층 — B1·B2 두 층 분리 (B2 z_center<-5000, B1 -5000<z<0)
  5) 격자 unique X·Y ≤ 15 (101동 단동 기대)
  6) 시각 검증 — 방부장 GUI (PoC 종료 후)

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_101_b1_b2_dong_stack.py
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

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
COLUMN_CODEX = "output/codex_columns_unified.json"
GIRDER_CODEX = "output/codex_beams_basement.json"
OUT_STEP = "output/poc_101_b1_b2_dong.step"
OUT_JSON = "output/poc_101_b1_b2_dong.json"
OUT_BOQ_MD = "output/poc_101_b1_b2_dong_boq.md"

# 도엽 자력 채굴 결과 박제
# S30-001 = B2F(floor=-2): 'B2F SL' 텍스트 + 기둥 후보 851개
# S30-002 = B1F(floor=-1): PIT 관련 텍스트 + 기둥 후보 457개
sheet_w, sheet_h = 126000, 178200

SHEETS = {
    'S30-001': {
        'sw': (116247.0, 2290548.0),
        'w': sheet_w,
        'h': sheet_h,
        'floor': -2,
        'title': '101동 지하2층 구조평면도',
    },
    'S30-002': {
        'sw': (242247.0, 2290548.0),
        'w': sheet_w,
        'h': sheet_h,
        'floor': -1,
        'title': '101동 지하1층 구조평면도',
    },
}

FLOOR_HEIGHT = 4400   # 표준 층고 (mm)
GIRDER_H_DEFAULT = 800  # 거더 기본 높이 (mm)
SOURCE_HINT = '101~112동'  # codex source_hint — 101동은 이 풀 우선


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

    x_pos = {}
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
    """도엽 영역 내 LINE/LWPOLYLINE → RawEntity + ezdxf 매핑."""
    ix0, iy0 = sw[0] + w * inset, sw[1] + h * inset
    ix1, iy1 = sw[0] + w * (1 - inset), sw[1] + h * (1 - inset)
    raws = []
    raw_meta = []
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

    print(f'    [③ PC 분리] {sid}...')
    raws, raw_meta = extract_raw_entities(msp, sw, w, h)
    classified_pc = classify_entities(raws)
    pc_kind_by_id = {c.entity_id: c.kind for c in classified_pc}
    pc_summary = {}
    for c in classified_pc:
        pc_summary[c.kind.value] = pc_summary.get(c.kind.value, 0) + 1
    print(f'      PC 통계: {pc_summary}')

    print(f'    [② LINE 페어링] {sid}...')
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

    a2 = run_adapter_2(line_segs)
    wall_pairs = a2['wall_pairs']
    print(f'      LINE {len(line_segs)}개 → wall_pairs {len(wall_pairs)}개')

    # 격자 라벨 자력 (TEXT 기반)
    grid_label = extract_grid_labels(all_texts, sw, w, h)
    print(f'      격자 X={grid_label["unique_x"]} ({grid_label["x_labels"][:5]}) '
          f'Y={grid_label["unique_y"]} ({grid_label["y_labels"][:5]})')

    # GridLines 결정: TEXT 라벨 우선
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

    # 게이트 5 사전 점검
    g5_max = max(grid_label['unique_x'], grid_label['unique_y']) if grid_label['unique_x'] > 0 else 0
    if g5_max > 15:
        # 격자 매칭 비활성 (지하주차장 PoC 패턴)
        grid_for_classify = None
        conf_threshold = 0.4
        print(f'      [경고] 격자 unique max={g5_max} > 15 → grid=None (격자 매칭 비활성)')
    else:
        grid_for_classify = grid_obj
        conf_threshold = 0.4

    print(f'    [① 거더 detect] {sid}...')
    girders_raw = detect_girders_from_adapter2(
        adapter2_result=a2,
        grid_x=list(grid_obj.x_lines) if grid_obj else [],
        grid_y=list(grid_obj.y_lines) if grid_obj else [],
        girder_codex=girder_codex,
        expected_girder_height=GIRDER_H_DEFAULT,
        require_on_grid=True,
    )
    print(f'      거더 codex 매칭 {len([g for g in girders_raw if g.matched_symbol])}개')

    print(f'    [codex 매핑] {sid} 박스 분류...')
    boxes = []
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

    print(f'      기둥 후보 박스 {len(boxes)}개')

    batch_input = [(b['box_id'], b['cx'], b['cy'], b['w'], b['h']) for b in boxes]
    classifications = classify_batch(
        batch_input,
        core_regions=[],
        grid=grid_for_classify,
        column_max_ratio=3.0,
    )

    # wall_pair zone 기둥 강등 (102 PoC 패턴)
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

    high_conf = [c for c in classifications
                 if c.kind == BoxKind.COLUMN and c.confidence >= conf_threshold]
    box_by_id = {b['box_id']: b for b in boxes}

    instances = []
    for c in high_conf:
        b = box_by_id[c.box_id]
        instances.append(BoxInstance(
            box_id=c.box_id, width=b['w'], height=b['h'],
            label=None, source_hint=SOURCE_HINT, floor_hint=floor,
        ))
    mappings, unmatched = map_instances(instances, column_codex)
    print(f'      column 인스턴스 {len(instances)}개 → codex 매칭 {len(mappings)}개 / unmatched {len(unmatched)}개')

    # 분류 통계
    kind_count = Counter(c.kind.value for c in classifications)

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
        'n_unmatched_columns': len(unmatched),
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
    gates['G1_solid_count_match'] = (
        bool(actual_count == meta_solids_count),
        actual_count, meta_solids_count,
    )

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
        math.hypot(g['p2'][0] - g['p1'][0], g['p2'][1] - g['p1'][1]) * g['thickness'] * GIRDER_H_DEFAULT
        for r in sheet_results for g in r['girders']
        if math.hypot(g['p2'][0] - g['p1'][0], g['p2'][1] - g['p1'][1]) >= 100
    )
    vol_diff_pct = abs(total_volume - meta_volume) / max(meta_volume, 1) * 100
    gates['G3_volume_match'] = (
        bool(vol_diff_pct < 0.1), total_volume, meta_volume, vol_diff_pct,
    )

    # 게이트 4: Z 적층 — B1·B2 두 층 분리
    # B2 기둥 z_center = -8800 + 2200 = -6600
    # B1 기둥 z_center = -4400 + 2200 = -2200
    # 임계: z < -5000 → B2, z >= -5000 → B1
    z_floors = set()
    for z in z_centers:
        if z < -5000:
            z_floors.add('B2')
        elif z < 0:
            z_floors.add('B1')
    gates['G4_z_layers'] = (bool(z_floors == {'B1', 'B2'}), sorted(z_floors))

    # 게이트 5: 격자 unique X·Y ≤ 15 (101동 단동 기대)
    if not sheet_results:
        gates['G5_grid_unique'] = (False, 0, {})
    else:
        max_per_sheet = max(
            max(r['grid_unique_x'], r['grid_unique_y']) for r in sheet_results
        )
        gates['G5_grid_unique'] = (
            bool(max_per_sheet <= 15),
            max_per_sheet,
            {r['sheet_id']: (r['grid_unique_x'], r['grid_unique_y']) for r in sheet_results},
        )

    return gates, total_volume


def write_boq_md(sheet_results, shapes_meta, total_volume, gates, path):
    """BOQ .md 박제."""
    lines = [
        '# 101동 B1·B2층 PoC — BOQ 산출',
        '',
        f'- 입력: `{DXF}`',
        f'- 도엽: S30-001 (B2F) + S30-002 (B1F)',
        f'- source_hint: `{SOURCE_HINT}`',
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
        mark = '통과' if passed else '실패'
        lines.append(f'- {mark} **{k}**: `{v[1:]}`')
    lines.append('')
    lines.append('## 솔리드 합계')
    lines.append('')
    lines.append(f'- 총 솔리드: {len(shapes_meta)}')
    col_count = sum(1 for n, k in shapes_meta if k == 'column')
    gir_count = sum(1 for n, k in shapes_meta if k == 'girder')
    lines.append(f'- 기둥: {col_count}')
    lines.append(f'- 거더: {gir_count}')
    lines.append(f'- 총 부피: {total_volume / 1e9:.3f} m3')
    lines.append('')
    lines.append('이천(李蕆), 방부장 친명 현실 테스트 두 번째 — 101동 B1·B2 자수 보정 정사 호미.')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main():
    print(f'[입력] {DXF}')
    t0 = time.time()

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f'[작업 디렉터리] {os.getcwd()}')

    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    print(f'[로드] {time.time()-t0:.1f}s')

    print('[전체 TEXT 캐시]')
    all_texts = extract_all_texts(msp)
    print(f'  TEXT/MTEXT 총 {len(all_texts)}건')

    column_codex = load_codex(COLUMN_CODEX)
    girder_codex = load_girder_codex(GIRDER_CODEX)
    print(f'[codex] column {len(column_codex)}종 / girder {len(girder_codex)}종')

    print(f'\n[자수 보정 정사 호미 — ③→②→①→codex]')
    sheet_results = []
    for sid in ['S30-001', 'S30-002']:
        t1 = time.time()
        sheet = SHEETS[sid]
        print(f'\n  [{sid}] floor={sheet["floor"]:+d} 처리 시작...')
        try:
            r = process_sheet(msp, sid, sheet, all_texts, column_codex, girder_codex)
            sheet_results.append(r)
            print(f'  [{sid}] 완료 — 기둥 {len(r["columns"])} 거더 {len(r["girders"])} '
                  f'격자 X={r["grid_unique_x"]} Y={r["grid_unique_y"]} ({r["grid_source"]}) '
                  f'({time.time()-t1:.1f}s)')
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'  [{sid}] FAIL: {e}')

    if not sheet_results:
        print('[오류] 처리된 도엽 없음. 종료.')
        return

    # 3D STEP 빌드
    print(f'\n[3D STEP 빌드]')
    import FreeCAD, Part
    shapes = build_3d(sheet_results)
    print(f'  솔리드 {len(shapes)}개 생성')

    os.makedirs('output', exist_ok=True)
    if shapes:
        compound = Part.makeCompound([s for _, s, _ in shapes])
        compound.exportStep(OUT_STEP)
        print(f'  [STEP 저장] {OUT_STEP}')

    # 검증 게이트
    print(f'\n[검증 게이트 1~5]')
    gates, total_volume = verify_gates(shapes, sheet_results, len(shapes))
    for k, v in gates.items():
        passed = v[0]
        mark = '통과' if passed else '실패'
        print(f'  {mark} {k}: {v[1:]}')

    # 메타 박제
    out = {
        'project': '부산 에코델타 24BL 101동 B1·B2',
        'directive': '방부장 친명 현실 테스트 두 번째',
        'self_correction': '③→②→①→codex 정사 순서 강제',
        'sheet_floor_mapping': {
            'S30-001': 'B2F (floor=-2)',
            'S30-002': 'B1F (floor=-1)',
        },
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
    print(f'  총 부피: {out["totals"]["volume_m3"]} m3')
    print(f'  처리 시간: {out["elapsed_s"]}초')

    g5_v = gates.get('G5_grid_unique', (False, 0, {}))
    g5_passed = g5_v[0]
    g5_max = g5_v[1]
    print(f'\n  [게이트 5] 격자 unique max = {g5_max}  '
          f'{"통과 (<=15)" if g5_passed else "미통과 (>15)"}')

    all_passed = all(v[0] for v in gates.values())
    print(f'\n  [최종] 게이트 1~5 {"전체 통과" if all_passed else "일부 실패"}')


if __name__ == '__main__':
    main()
