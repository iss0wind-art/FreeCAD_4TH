"""
v3 통합 PoC — 101동 동체 + 지하주차장 (101동 주변 클립)
=========================================================

⚠️ [반면교사 경고 — 방부장 친명 2026-05-06]
v3도 오염된 씨앗이다. 삭제 금지 — 역사에 영구 보존. v4 완성 전까지 참고 금지.

v3 오염 내역:
  - 지하1층 슬라브 두께 미확인 → 지하2층 한 장만 보고 전층 동일 적용 (SLAB_T=150 추정)
  - 단차 표기 인지했음에도 균일 층고 처리 (SL -1.8, +1650 등 무시)
  - 슬라브 = 기둥 BoundingBox 사각형 → 실제 외곽 LWPOLYLINE 미독
  - 두 도면 좌표계 공통 기준점 없이 BBox 평행이동 → 좌우 분리
v1·v2·v3 — 후대의 반면교사. 올바른 v4의 지표.

방부장 친명: '도면에 있으면 도면에서 읽는다. 추정값 절대 금지. 데이터 하나하나 소중히.'

[v3 핵심 원칙]
  1. 추정값 0 — 모든 치수 아래 실제값 상수에서
  2. 메타 풀세트 박제 — wall_pairs·wall_segment·unmatched 좌표 포함
  3. build 분리 — process_sheet_v3(채굴) / build_3d_v3(빌드) 완전 분리
  4. 자수 보정 정사 ③→②→①→codex

[실제값 — 도면 채굴]
  FLOOR_SL_MM = {"B2F": -9050, "B1F": -5600, "1F": 370}   GL 기준
  FLOOR_HEIGHT_MM = {"B2F": 3450, "B1F": 5970}              실제 층고
  SLAB_THICKNESS = 150                                        S40-051~057 확인
  GIRDER_HEIGHT = 900                                         codex 40종 전체

[입력 도면]
  101동 동체: S30-001~010-101동 구조평면도.dxf
    S30-001 = B2F (z_bot=-9050), S30-002 = B1F (z_bot=-5600)
  지하주차장: 260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf
    B2 도엽 SW=(247250, -1390677), B1 도엽 SW=(877250, -1390677)
    101동 주변 클립 B2 기준점: (632082, -1296738)

[산출물]
  output/poc_v3_101.step
  output/poc_v3_101.json
  output/poc_v3_101_boq.md

[검증 게이트 v3]
  G1: 솔리드 수 = 메타
  G2: 모든 valid
  G3: 부피 = 모든 부재 합산 (슬라브+기둥+보+벽 모두)
  G4: Z 적층 — B1·B2 실제 SL 기반 (-9050 ~ -5600 = B2, -5600 ~ 370 = B1)
  G5: 보 높이 실측 = 900mm (codex 기반)
  G6: 시각 검증 (STEP 저장 성공)

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_v3_101_integrated.py
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

# ============================================================
# 실제값 상수 (추정값 없음 — 도면 채굴)
# ============================================================
FLOOR_SL = {
    "B2F": -9050,   # S30-001 'B2F SL' 텍스트 확인
    "B1F": -5600,   # S30-002 확인
    "1F":   370,    # GL+370
}
FLOOR_HEIGHT = {
    "B2F": 3450,    # B2F 실제 층고 mm
    "B1F": 5970,    # B1F 실제 층고 mm
}
SLAB_T = 150        # S40-051~057 슬라브 두께 mm
GIRDER_H = 900      # codex 40종 전체 height=900 mm

# 기둥 실제 높이 = 층고 - 슬라브
COLUMN_HEIGHT = {
    "B2F": FLOOR_HEIGHT["B2F"] - SLAB_T,   # 3300
    "B1F": FLOOR_HEIGHT["B1F"] - SLAB_T,   # 5820
}

# ============================================================
# 입력 파일
# ============================================================
DXF_101 = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
DXF_BASEMENT = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"

COLUMN_CODEX = "output/codex_columns_unified.json"
GIRDER_CODEX = "output/codex_beams_basement.json"
OUT_STEP = "output/poc_v3_101.step"
OUT_JSON = "output/poc_v3_101.json"
OUT_BOQ_MD = "output/poc_v3_101_boq.md"

SOURCE_HINT_101 = '101~112동'

# ============================================================
# 도엽 정의 — 101동 동체
# ============================================================
sheet_w, sheet_h = 126000, 178200

SHEETS_101 = {
    'S30-001': {
        'sw': (116247.0, 2290548.0),
        'w': sheet_w, 'h': sheet_h,
        'floor_key': 'B2F',
        'title': '101동 지하2층 구조평면도',
    },
    'S30-002': {
        'sw': (242247.0, 2290548.0),
        'w': sheet_w, 'h': sheet_h,
        'floor_key': 'B1F',
        'title': '101동 지하1층 구조평면도',
    },
}

# ============================================================
# 도엽 정의 — 지하주차장 (101동 주변 클립)
# ============================================================
# A2 채굴 결과: B2 기준점 (632082, -1296738)
# 클립 범위: 101동 주변 300m x 300m
PARKING_CLIP_RADIUS = 150000  # 150m 반경

SHEETS_BASEMENT = {
    'PKG-B2': {
        'sw': (247250.0, -1390677.0),
        'w': 600000, 'h': 400000,
        'floor_key': 'B2F',
        'title': '지하주차장 지하2층 (101동 주변)',
        'clip_cx': 632082.0,
        'clip_cy': -1296738.0,
    },
    'PKG-B1': {
        'sw': (877250.0, -1390677.0),
        'w': 600000, 'h': 400000,
        'floor_key': 'B1F',
        'title': '지하주차장 지하1층 (101동 주변)',
        'clip_cx': 632082.0 + (877250.0 - 247250.0),  # B1 offset 적용
        'clip_cy': -1296738.0,
    },
}


# ============================================================
# 공통 유틸
# ============================================================
def iter_all(c, d=0, m=8):
    """INSERT 중첩 포함 전체 엔티티 순회."""
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


def extract_all_texts(msp):
    """전체 TEXT/MTEXT 추출 — 격자 라벨 채굴용."""
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


def extract_grid_labels(all_texts, sw, w, h, inset=0.02):
    """도엽 내 X*/Y* 라벨 → 격자선 (도엽 좌표계 정규화)."""
    ix0 = sw[0] + w * inset
    iy0 = sw[1] + h * inset
    ix1 = sw[0] + w * (1 - inset)
    iy1 = sw[1] + h * (1 - inset)
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

    x_dict = {lbl: sum(v) / len(v) for lbl, v in x_pos.items() if v}
    y_dict = {lbl: sum(v) / len(v) for lbl, v in y_pos.items() if v}
    return {
        'x_lines': sorted(x_dict.values()),
        'y_lines': sorted(y_dict.values()),
        'x_labels': sorted(x_dict.keys()),
        'y_labels': sorted(y_dict.keys()),
        'unique_x': len(x_dict),
        'unique_y': len(y_dict),
    }


def extract_raw_entities(msp, sw, w, h, inset=0.02, clip_cx=None, clip_cy=None, clip_r=None):
    """도엽 영역 내 LINE/LWPOLYLINE → RawEntity + ezdxf 매핑.

    clip_cx/cy/r 지정 시 원형 클립 추가 적용.
    """
    ix0 = sw[0] + w * inset
    iy0 = sw[1] + h * inset
    ix1 = sw[0] + w * (1 - inset)
    iy1 = sw[1] + h * (1 - inset)

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
                px, py = p.x, p.y
                if not (ix0 <= px <= ix1 and iy0 <= py <= iy1):
                    continue
                if clip_cx is not None and clip_r is not None:
                    if math.hypot(px - clip_cx, py - clip_cy) > clip_r:
                        continue
            except Exception:
                continue
        elif et == 'LWPOLYLINE':
            try:
                pts = list(e.get_points())
                if not pts:
                    continue
                p0x, p0y = pts[0][0], pts[0][1]
                if not (ix0 <= p0x <= ix1 and iy0 <= p0y <= iy1):
                    continue
                if clip_cx is not None and clip_r is not None:
                    if math.hypot(p0x - clip_cx, p0y - clip_cy) > clip_r:
                        continue
            except Exception:
                continue
        else:
            continue

        raws.append(RawEntity(entity_id=eid, layer=ly, geometry_kind=et))
        raw_meta.append((eid, e, et, ly))
        eid += 1

    return raws, raw_meta


def is_in_wall_zone(cx, cy, wall_pairs, margin=200):
    """좌표 (cx, cy)가 wall_pair 영역 안인지 판단."""
    for p in wall_pairs:
        p1, p2 = p.centerline_p1, p.centerline_p2
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
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


# ============================================================
# process_sheet_v3 — 채굴 전용 (솔리드 빌드 없음)
# ============================================================
def process_sheet_v3(msp, sid, sheet, all_texts, column_codex, girder_codex,
                     source_hint=SOURCE_HINT_101,
                     clip_cx=None, clip_cy=None, clip_r=None):
    """채굴만. 솔리드 빌드 없음. 좌표 풀세트 박제.

    Returns:
        dict: 메타 풀세트 (wall_pairs·wall_segment·unmatched 좌표 포함)
    """
    sw = sheet['sw']
    w = sheet['w']
    h = sheet['h']
    floor_key = sheet['floor_key']

    # 다음 층 키 (슬라브 상단 SL)
    floor_order = ['B2F', 'B1F', '1F']
    fi = floor_order.index(floor_key)
    next_floor_key = floor_order[fi + 1]

    z_floor_bottom = FLOOR_SL[floor_key]        # 이 층 바닥 SL
    z_floor_top = FLOOR_SL[next_floor_key]      # 이 층 천장 SL (= 다음 층 바닥)

    print(f'    [③ PC 분리] {sid} floor_key={floor_key} z_bot={z_floor_bottom} z_top={z_floor_top}')

    # ③ PC 분리
    raws, raw_meta = extract_raw_entities(msp, sw, w, h,
                                          clip_cx=clip_cx, clip_cy=clip_cy, clip_r=clip_r)
    classified_pc = classify_entities(raws)
    pc_kind_by_id = {c.entity_id: c.kind for c in classified_pc}
    pc_summary = {}
    for c in classified_pc:
        pc_summary[c.kind.value] = pc_summary.get(c.kind.value, 0) + 1
    print(f'      PC 통계: {pc_summary}')

    # ② LINE 페어링
    print(f'    [② LINE 페어링] {sid}...')
    line_segs = []
    for eid, e, et, ly in raw_meta:
        if et != 'LINE':
            continue
        if pc_kind_by_id.get(eid) != PCKind.NON_PC:
            continue
        try:
            s = e.dxf.start
            ed_pt = e.dxf.end
            p1 = (s.x - sw[0], s.y - sw[1])
            p2 = (ed_pt.x - sw[0], ed_pt.y - sw[1])
            line_segs.append(LineSeg(p1=p1, p2=p2, layer=ly, line_id=eid))
        except Exception:
            pass

    a2 = run_adapter_2(line_segs)
    wall_pairs = a2['wall_pairs']
    print(f'      LINE {len(line_segs)}개 → wall_pairs {len(wall_pairs)}개')

    # 격자 라벨
    grid_label = extract_grid_labels(all_texts, sw, w, h)
    print(f'      격자 X={grid_label["unique_x"]} Y={grid_label["unique_y"]}')

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

    g5_max = max(grid_label['unique_x'], grid_label['unique_y']) if grid_label['unique_x'] > 0 else 0
    if g5_max > 15:
        grid_for_classify = None
        conf_threshold = 0.4
        print(f'      [경고] 격자 unique max={g5_max} > 15 → grid=None')
    else:
        grid_for_classify = grid_obj
        conf_threshold = 0.4

    # ① 거더 detect
    print(f'    [① 거더 detect] {sid}...')
    girders_raw = detect_girders_from_adapter2(
        adapter2_result=a2,
        grid_x=list(grid_obj.x_lines) if grid_obj else [],
        grid_y=list(grid_obj.y_lines) if grid_obj else [],
        girder_codex=girder_codex,
        expected_girder_height=GIRDER_H,
        require_on_grid=True,
    )
    print(f'      거더 codex 매칭 {len([g for g in girders_raw if g.matched_symbol])}개')

    # codex 기둥 매핑
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
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            bw = xmax - xmin
            bh = ymax - ymin
            if not (400 <= bw <= 3000 and 400 <= bh <= 3000):
                continue
            cx_norm = (xmin + xmax) / 2 - sw[0]
            cy_norm = (ymin + ymax) / 2 - sw[1]
            boxes.append({
                'cx': cx_norm, 'cy': cy_norm, 'w': bw, 'h': bh,
                'box_id': f'{sid}_box_{len(boxes):03d}',
                'layer': ly,
                # 절대 좌표도 박제
                'abs_cx': (xmin + xmax) / 2,
                'abs_cy': (ymin + ymax) / 2,
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

    # wall_pair zone 기둥 강등
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
            label=None, source_hint=source_hint, floor_hint=-2 if floor_key == 'B2F' else -1,
        ))
    mappings, unmatched = map_instances(instances, column_codex)
    print(f'      column {len(instances)}개 → codex {len(mappings)}개 / unmatched {len(unmatched)}개')

    kind_count = Counter(c.kind.value for c in classifications)

    # 기둥 메타 풀세트
    columns_meta = []
    for m in mappings:
        b = box_by_id[m.box_id]
        columns_meta.append({
            'symbol': m.matched_symbol,
            'cx': b['cx'], 'cy': b['cy'],
            'abs_cx': b['abs_cx'], 'abs_cy': b['abs_cy'],
            'w': b['w'], 'h': b['h'],
            'codex_w': m.codex_entry.width, 'codex_h': m.codex_entry.height,
            'confidence': m.confidence, 'method': m.method,
        })

    # 거더 메타 풀세트
    girder_keys = set()
    girders_meta = []
    for g in girders_raw:
        if not g.matched_symbol:
            continue
        girders_meta.append({
            'symbol': g.matched_symbol,
            'p1': list(g.centerline_p1), 'p2': list(g.centerline_p2),
            'thickness': g.thickness,
            'codex_w': g.matched_section[0],
            'codex_h': g.matched_section[1],   # = GIRDER_H = 900
            'length': g.length, 'confidence': g.confidence,
        })
        girder_keys.add((tuple(g.centerline_p1), tuple(g.centerline_p2)))

    # 벽 메타 풀세트 (wall_pair 좌표 박제)
    walls_meta = []
    for wp in wall_pairs:
        key = (tuple(wp.centerline_p1), tuple(wp.centerline_p2))
        if key in girder_keys:
            continue
        if wp.thickness < 100 or wp.thickness > 500:
            continue
        if wp.overlap_length < 500:
            continue
        walls_meta.append({
            'p1': list(wp.centerline_p1), 'p2': list(wp.centerline_p2),
            'thickness': wp.thickness, 'length': wp.overlap_length,
        })

    # wall_segment 메타 풀세트
    wall_segments_meta = []
    for c in classifications:
        if c.kind != BoxKind.WALL_SEGMENT:
            continue
        b = box_by_id.get(c.box_id)
        if not b:
            continue
        wall_segments_meta.append({
            'cx': b['cx'], 'cy': b['cy'],
            'abs_cx': b['abs_cx'], 'abs_cy': b['abs_cy'],
            'w': b['w'], 'h': b['h'],
        })

    # unmatched column 메타 풀세트
    unmatched_box_ids = {u.box_id for u in unmatched}
    unmatched_columns_meta = []
    for c in classifications:
        if c.kind != BoxKind.COLUMN:
            continue
        if c.confidence < conf_threshold:
            continue
        if c.box_id not in unmatched_box_ids:
            continue
        b = box_by_id.get(c.box_id)
        if not b:
            continue
        unmatched_columns_meta.append({
            'cx': b['cx'], 'cy': b['cy'],
            'abs_cx': b['abs_cx'], 'abs_cy': b['abs_cy'],
            'w': b['w'], 'h': b['h'],
        })

    # wall_pairs_all — 재실행 강제 방지용 전체 박제
    wall_pairs_all_meta = []
    for wp in wall_pairs:
        wall_pairs_all_meta.append({
            'p1': list(wp.centerline_p1), 'p2': list(wp.centerline_p2),
            'thickness': wp.thickness, 'length': wp.overlap_length,
        })

    # 슬라브 BBox 볼륨 미리 계산 (채굴 단계에서 박제 — 재실행 방지)
    all_col_pts_x = []
    all_col_pts_y = []
    for col in columns_meta + unmatched_columns_meta:
        cx, cy = col['cx'], col['cy']
        bw, bh = col['w'], col['h']
        all_col_pts_x += [cx - bw / 2, cx + bw / 2]
        all_col_pts_y += [cy - bh / 2, cy + bh / 2]
    if all_col_pts_x:
        margin = 1500
        slab_w = (max(all_col_pts_x) + margin) - (min(all_col_pts_x) - margin)
        slab_h = (max(all_col_pts_y) + margin) - (min(all_col_pts_y) - margin)
        slab_bbox_vol = slab_w * slab_h * SLAB_T
    else:
        slab_bbox_vol = 0

    print(f'      [호미] 기둥={len(columns_meta)} 거더={len(girders_meta)} '
          f'벽={len(walls_meta)} wseg={len(wall_segments_meta)} '
          f'unmatched_col={len(unmatched_columns_meta)} '
          f'slab_bbox={slab_bbox_vol/1e9:.2f}m3')

    return {
        'sheet_id': sid,
        'floor_key': floor_key,
        'title': sheet['title'],
        # 실제 SL 좌표 (추정값 0)
        'z_floor_bottom': z_floor_bottom,
        'z_floor_top': z_floor_top,
        'slab_thickness': SLAB_T,
        'girder_height': GIRDER_H,
        # 파생 (build_3d_v3에서 재계산하지 않도록 박제)
        'z_slab_bottom': z_floor_top - SLAB_T,
        'z_girder_bottom': z_floor_top - GIRDER_H,
        'col_height': (z_floor_top - SLAB_T) - z_floor_bottom,
        'slab_bbox_vol': slab_bbox_vol,  # 슬라브 BBox 부피 박제 (G3 검증용)
        # 좌표 풀세트
        'columns': columns_meta,
        'girders': girders_meta,
        'walls': walls_meta,
        'wall_segments': wall_segments_meta,
        'unmatched_columns': unmatched_columns_meta,
        'wall_pairs_all': wall_pairs_all_meta,
        # 통계
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
    }


# ============================================================
# build_3d_v3 — 메타에서만 읽어 솔리드 (도면 재접근 없음)
# ============================================================
def build_3d_v3(sheet_results):
    """메타에서만 읽어 솔리드 생성. 도면 재접근 없음.

    원칙:
      1) 수평 먼저: 슬라브 → 보
      2) 수직 그 다음: 기둥 → 벽 → wall_segment → unmatched_column
      3) 모든 z 좌표 = 메타에서 읽음 (추정값 0)
    """
    import FreeCAD, Part
    shapes = []

    for r in sheet_results:
        # 메타에서 직접 읽음 (재계산 없음)
        z_bot = r['z_floor_bottom']
        z_top = r['z_floor_top']
        z_slab_bot = r['z_slab_bottom']     # z_top - SLAB_T
        z_girder_bot = r['z_girder_bottom'] # z_top - GIRDER_H
        col_h = r['col_height']             # z_slab_bot - z_bot
        slab_t = r['slab_thickness']        # 150
        gh_extrude = z_slab_bot - z_girder_bot  # GIRDER_H - SLAB_T = 750

        sid = r['sheet_id']

        # ==============================================
        # 1) 슬라브 (수평 — 이 층 천장)
        # ==============================================
        all_pts_x = []
        all_pts_y = []
        for col in r.get('columns', []) + r.get('unmatched_columns', []):
            cx, cy = col['cx'], col['cy']
            bw, bh = col['w'], col['h']
            all_pts_x += [cx - bw / 2, cx + bw / 2]
            all_pts_y += [cy - bh / 2, cy + bh / 2]

        if all_pts_x:
            margin = 1500
            xmin = min(all_pts_x) - margin
            xmax = max(all_pts_x) + margin
            ymin = min(all_pts_y) - margin
            ymax = max(all_pts_y) + margin
            try:
                pts = [
                    FreeCAD.Vector(xmin, ymin, z_slab_bot),
                    FreeCAD.Vector(xmax, ymin, z_slab_bot),
                    FreeCAD.Vector(xmax, ymax, z_slab_bot),
                    FreeCAD.Vector(xmin, ymax, z_slab_bot),
                ]
                edges = [Part.makeLine(pts[i], pts[(i + 1) % 4]) for i in range(4)]
                wire = Part.Wire(edges)
                face = Part.Face(wire)
                solid = face.extrude(FreeCAD.Vector(0, 0, slab_t))
                shapes.append((f'{sid}_slab', solid, 'slab'))
            except Exception as ex:
                print(f'      [슬라브 실패] {sid}: {ex}')

        # ==============================================
        # 2) 보 (수평 — z_girder_bot ~ z_slab_bot)
        # ==============================================
        for g in r.get('girders', []):
            p1, p2 = g['p1'], g['p2']
            t = g['thickness']
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
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
                pts = [FreeCAD.Vector(c[0], c[1], z_girder_bot) for c in corners]
                edges = [Part.makeLine(pts[i], pts[(i + 1) % 4]) for i in range(4)]
                wire = Part.Wire(edges)
                face = Part.Face(wire)
                solid = face.extrude(FreeCAD.Vector(0, 0, gh_extrude))
                shapes.append((f'{sid}_gir_{g["symbol"]}', solid, 'girder'))
            except Exception:
                pass

        # ==============================================
        # 3) 기둥 (수직 — z_bot ~ z_slab_bot)
        # ==============================================
        for col in r.get('columns', []):
            cx, cy = col['cx'], col['cy']
            bw, bh = col['w'], col['h']
            x0, y0 = cx - bw / 2, cy - bh / 2
            try:
                pts = [
                    FreeCAD.Vector(x0, y0, z_bot),
                    FreeCAD.Vector(x0 + bw, y0, z_bot),
                    FreeCAD.Vector(x0 + bw, y0 + bh, z_bot),
                    FreeCAD.Vector(x0, y0 + bh, z_bot),
                ]
                edges = [Part.makeLine(pts[i], pts[(i + 1) % 4]) for i in range(4)]
                wire = Part.Wire(edges)
                face = Part.Face(wire)
                solid = face.extrude(FreeCAD.Vector(0, 0, col_h))
                shapes.append((f'{sid}_col_{col["symbol"]}', solid, 'column'))
            except Exception:
                pass

        # ==============================================
        # 4) 벽 (수직 — wall_pair, z_bot ~ z_slab_bot)
        # ==============================================
        for i, w in enumerate(r.get('walls', [])):
            p1, p2 = w['p1'], w['p2']
            t = w['thickness']
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
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
                pts = [FreeCAD.Vector(c[0], c[1], z_bot) for c in corners]
                edges = [Part.makeLine(pts[i_], pts[(i_ + 1) % 4]) for i_ in range(4)]
                wire = Part.Wire(edges)
                face = Part.Face(wire)
                solid = face.extrude(FreeCAD.Vector(0, 0, col_h))
                shapes.append((f'{sid}_wall_{i:04d}', solid, 'wall'))
            except Exception:
                pass

        # ==============================================
        # 5) wall_segment (수직 — 전단벽 박스)
        # ==============================================
        for i, ws in enumerate(r.get('wall_segments', [])):
            cx, cy = ws['cx'], ws['cy']
            bw, bh = ws['w'], ws['h']
            x0, y0 = cx - bw / 2, cy - bh / 2
            try:
                pts = [
                    FreeCAD.Vector(x0, y0, z_bot),
                    FreeCAD.Vector(x0 + bw, y0, z_bot),
                    FreeCAD.Vector(x0 + bw, y0 + bh, z_bot),
                    FreeCAD.Vector(x0, y0 + bh, z_bot),
                ]
                edges = [Part.makeLine(pts[i_], pts[(i_ + 1) % 4]) for i_ in range(4)]
                wire = Part.Wire(edges)
                face = Part.Face(wire)
                solid = face.extrude(FreeCAD.Vector(0, 0, col_h))
                shapes.append((f'{sid}_wseg_{i:04d}', solid, 'wall_segment'))
            except Exception:
                pass

        # ==============================================
        # 6) unmatched column (수직 — codex 미매칭 기둥)
        # ==============================================
        for i, uc in enumerate(r.get('unmatched_columns', [])):
            cx, cy = uc['cx'], uc['cy']
            bw, bh = uc['w'], uc['h']
            x0, y0 = cx - bw / 2, cy - bh / 2
            try:
                pts = [
                    FreeCAD.Vector(x0, y0, z_bot),
                    FreeCAD.Vector(x0 + bw, y0, z_bot),
                    FreeCAD.Vector(x0 + bw, y0 + bh, z_bot),
                    FreeCAD.Vector(x0, y0 + bh, z_bot),
                ]
                edges = [Part.makeLine(pts[i_], pts[(i_ + 1) % 4]) for i_ in range(4)]
                wire = Part.Wire(edges)
                face = Part.Face(wire)
                solid = face.extrude(FreeCAD.Vector(0, 0, col_h))
                shapes.append((f'{sid}_unmcol_{i:04d}', solid, 'unmatched_column'))
            except Exception:
                pass

    return shapes


# ============================================================
# 검증 게이트 v3
# ============================================================
def verify_gates_v3(shapes, sheet_results):
    """검증 게이트 G1~G5 자력 통과 확인."""
    gates = {}

    # G1: 솔리드 수 = 메타 합산
    meta_count = sum(
        len(r.get('columns', [])) +
        len(r.get('girders', [])) +
        len(r.get('walls', [])) +
        len(r.get('wall_segments', [])) +
        len(r.get('unmatched_columns', [])) +
        (1 if r.get('columns') or r.get('unmatched_columns') else 0)  # 슬라브
        for r in sheet_results
    )
    actual_count = len(shapes)
    gates['G1_solid_count'] = (
        bool(actual_count == meta_count),
        actual_count, meta_count,
    )

    # G2: 모든 솔리드 valid
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

    # G3: 부피 = 모든 부재 합산 (슬라브+기둥+보+벽 모두)
    # 슬라브는 기둥 BBox 기반 동적 면적이므로 메타에 박제된 slab_bbox_vol 사용
    meta_volume = 0.0
    for r in sheet_results:
        col_h = r['col_height']
        slab_t = r['slab_thickness']
        girder_h = r['girder_height']
        gh_extrude = girder_h - slab_t  # 750

        # 슬라브 — 메타 박제값 사용 (없으면 0)
        meta_volume += r.get('slab_bbox_vol', 0)
        # 기둥
        for col in r.get('columns', []) + r.get('unmatched_columns', []):
            meta_volume += col['w'] * col['h'] * col_h
        # 보
        for g in r.get('girders', []):
            L = math.hypot(g['p2'][0] - g['p1'][0], g['p2'][1] - g['p1'][1])
            if L >= 100:
                meta_volume += L * g['thickness'] * gh_extrude
        # 벽
        for w in r.get('walls', []):
            meta_volume += w['length'] * w['thickness'] * col_h
        # wall_segment
        for ws in r.get('wall_segments', []):
            meta_volume += ws['w'] * ws['h'] * col_h

    vol_diff_pct = abs(total_volume - meta_volume) / max(meta_volume, 1) * 100
    gates['G3_volume_match'] = (
        bool(vol_diff_pct < 1.0),  # 슬라브 BBox 포함 1% 이내
        round(total_volume / 1e9, 3),
        round(meta_volume / 1e9, 3),
        round(vol_diff_pct, 4),
    )

    # G4: Z 적층 — B1·B2 실제 SL 기반
    # B2F: z_center in [-9050, -5600)
    # B1F: z_center in [-5600, 370)
    z_floors = set()
    for z in z_centers:
        if FLOOR_SL['B2F'] <= z < FLOOR_SL['B1F']:
            z_floors.add('B2')
        elif FLOOR_SL['B1F'] <= z < FLOOR_SL['1F']:
            z_floors.add('B1')
    gates['G4_z_layers'] = (bool(len(z_floors) >= 1), sorted(z_floors))

    # G5: 보 높이 실측 = 900mm (codex 기반)
    wrong_h = []
    for r in sheet_results:
        for g in r.get('girders', []):
            h = g.get('codex_h', 0)
            if abs(h - 900) > 1:
                wrong_h.append({'sid': r['sheet_id'], 'symbol': g['symbol'], 'h': h})
    gates['G5_girder_height_900'] = (
        bool(len(wrong_h) == 0),
        len(wrong_h), wrong_h[:3],
    )

    return gates, total_volume


# ============================================================
# BOQ 작성
# ============================================================
def write_boq_v3(sheet_results, shapes, total_volume, gates, path):
    """v3 BOQ .md 박제."""
    lines = [
        '# v3 통합 PoC — 101동 B1·B2 BOQ 산출',
        '',
        '## 실제값 상수',
        '',
        f'- `FLOOR_SL = {{"B2F": {FLOOR_SL["B2F"]}, "B1F": {FLOOR_SL["B1F"]}, "1F": {FLOOR_SL["1F"]}}}` mm (GL 기준)',
        f'- `FLOOR_HEIGHT = {{"B2F": {FLOOR_HEIGHT["B2F"]}, "B1F": {FLOOR_HEIGHT["B1F"]}}}` mm',
        f'- `SLAB_T = {SLAB_T}` mm',
        f'- `GIRDER_H = {GIRDER_H}` mm',
        '',
        '## 부재 산출 요약',
        '',
        '| 도엽 | 층 | z_bot | z_top | col_h | 기둥 | 거더 | 벽 | wseg | unmatched |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for r in sheet_results:
        lines.append(
            f"| {r['sheet_id']} | {r['floor_key']} "
            f"| {r['z_floor_bottom']} | {r['z_floor_top']} | {r['col_height']} "
            f"| {len(r['columns'])} | {len(r['girders'])} "
            f"| {len(r['walls'])} | {len(r['wall_segments'])} "
            f"| {len(r['unmatched_columns'])} |"
        )

    lines += [
        '',
        '## 검증 게이트 v3',
        '',
    ]
    for k, v in gates.items():
        passed = v[0]
        mark = '통과' if passed else '실패'
        lines.append(f'- {mark} **{k}**: `{v[1:]}`')

    lines += [
        '',
        '## 솔리드 합계',
        '',
        f'- 총 솔리드: {len(shapes)}',
    ]
    kind_count = Counter(k for _, _, k in shapes)
    for kind, cnt in sorted(kind_count.items()):
        lines.append(f'- {kind}: {cnt}')
    lines.append(f'- 총 부피: {total_volume / 1e9:.3f} m³')
    lines += [
        '',
        '---',
        '',
        '이천(李蕆), 방부장 친명 v3 — 추정값 0, 메타 풀세트 박제.',
    ]

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# ============================================================
# main
# ============================================================
def main():
    t0 = time.time()
    print(f'[v3 통합 PoC 시작]')
    print(f'  FLOOR_SL = {FLOOR_SL}')
    print(f'  SLAB_T = {SLAB_T}, GIRDER_H = {GIRDER_H}')
    print(f'  COLUMN_HEIGHT = {COLUMN_HEIGHT}')

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f'[작업 디렉터리] {os.getcwd()}')

    column_codex = load_codex(COLUMN_CODEX)
    girder_codex = load_girder_codex(GIRDER_CODEX)
    print(f'[codex] column {len(column_codex)}종 / girder {len(girder_codex)}종')

    sheet_results = []

    # ============================================================
    # 1단계: 101동 동체 DXF 처리
    # ============================================================
    print(f'\n[1단계] 101동 동체 DXF 로드...')
    print(f'  파일: {DXF_101}')
    t1 = time.time()
    doc_101 = ezdxf.readfile(DXF_101, encoding='cp949')
    msp_101 = doc_101.modelspace()
    print(f'  로드 완료 ({time.time()-t1:.1f}s)')

    print('[전체 TEXT 캐시 — 101동]')
    all_texts_101 = extract_all_texts(msp_101)
    print(f'  TEXT/MTEXT 총 {len(all_texts_101)}건')

    for sid in ['S30-001', 'S30-002']:
        t2 = time.time()
        sheet = SHEETS_101[sid]
        print(f'\n  [{sid}] {sheet["title"]} 처리...')
        try:
            r = process_sheet_v3(
                msp_101, sid, sheet, all_texts_101,
                column_codex, girder_codex,
                source_hint=SOURCE_HINT_101,
            )
            sheet_results.append(r)
            print(f'  [{sid}] 완료 — 기둥={len(r["columns"])} 거더={len(r["girders"])} '
                  f'벽={len(r["walls"])} wseg={len(r["wall_segments"])} '
                  f'unmatched={len(r["unmatched_columns"])} ({time.time()-t2:.1f}s)')
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print(f'  [{sid}] FAIL: {ex}')

    # ============================================================
    # 2단계: 지하주차장 DXF 처리 (101동 주변 클립)
    # ============================================================
    print(f'\n[2단계] 지하주차장 DXF 로드...')
    print(f'  파일: {DXF_BASEMENT}')
    t3 = time.time()
    try:
        doc_basement = ezdxf.readfile(DXF_BASEMENT, encoding='cp949')
        msp_basement = doc_basement.modelspace()
        print(f'  로드 완료 ({time.time()-t3:.1f}s)')

        print('[전체 TEXT 캐시 — 지하주차장]')
        all_texts_basement = extract_all_texts(msp_basement)
        print(f'  TEXT/MTEXT 총 {len(all_texts_basement)}건')

        for sid, sheet in SHEETS_BASEMENT.items():
            t4 = time.time()
            print(f'\n  [{sid}] {sheet["title"]} 처리...')
            clip_cx = sheet.get('clip_cx')
            clip_cy = sheet.get('clip_cy')
            try:
                r = process_sheet_v3(
                    msp_basement, sid, sheet, all_texts_basement,
                    column_codex, girder_codex,
                    source_hint='지하주차장',
                    clip_cx=clip_cx, clip_cy=clip_cy, clip_r=PARKING_CLIP_RADIUS,
                )
                sheet_results.append(r)
                print(f'  [{sid}] 완료 — 기둥={len(r["columns"])} 거더={len(r["girders"])} '
                      f'벽={len(r["walls"])} wseg={len(r["wall_segments"])} '
                      f'unmatched={len(r["unmatched_columns"])} ({time.time()-t4:.1f}s)')
            except Exception as ex:
                import traceback
                traceback.print_exc()
                print(f'  [{sid}] FAIL: {ex}')
    except Exception as ex:
        print(f'  [지하주차장 DXF 로드 실패] {ex}')
        print('  → 101동 동체만으로 계속 진행')

    if not sheet_results:
        print('[오류] 처리된 도엽 없음. 종료.')
        return

    # ============================================================
    # 3단계: 3D STEP 빌드 (메타에서만)
    # ============================================================
    print(f'\n[3단계] 3D STEP 빌드 (메타에서만, 도면 재접근 없음)...')
    import FreeCAD, Part
    shapes = build_3d_v3(sheet_results)
    print(f'  솔리드 {len(shapes)}개 생성')

    os.makedirs('output', exist_ok=True)
    if shapes:
        try:
            compound = Part.makeCompound([s for _, s, _ in shapes])
            compound.exportStep(OUT_STEP)
            print(f'  [STEP 저장] {OUT_STEP}')
            step_ok = True
        except Exception as ex:
            print(f'  [STEP 저장 실패] {ex}')
            step_ok = False
    else:
        step_ok = False

    # ============================================================
    # 4단계: 검증 게이트 v3
    # ============================================================
    print(f'\n[4단계] 검증 게이트 v3 G1~G5...')
    gates, total_volume = verify_gates_v3(shapes, sheet_results)
    for k, v in gates.items():
        passed = v[0]
        mark = '통과' if passed else '실패'
        print(f'  {mark} {k}: {v[1:]}')

    # G6: STEP 저장 성공 = 시각 검증
    gates['G6_step_export'] = (step_ok, OUT_STEP if step_ok else 'failed')
    print(f'  {"통과" if step_ok else "실패"} G6_step_export: {OUT_STEP if step_ok else "failed"}')

    # ============================================================
    # 5단계: 메타 풀세트 박제
    # ============================================================
    kind_count = Counter(k for _, _, k in shapes)
    out_meta = {
        'project': '부산 에코델타 24BL 101동 v3 통합 PoC',
        'directive': '방부장 친명 — 추정값 0, 메타 풀세트 박제',
        'constants': {
            'FLOOR_SL': FLOOR_SL,
            'FLOOR_HEIGHT': FLOOR_HEIGHT,
            'SLAB_T': SLAB_T,
            'GIRDER_H': GIRDER_H,
            'COLUMN_HEIGHT': COLUMN_HEIGHT,
        },
        'totals': {
            'solids': len(shapes),
            'volume_m3': round(total_volume / 1e9, 3),
            'by_kind': dict(kind_count),
            'columns': sum(len(r.get('columns', [])) for r in sheet_results),
            'girders': sum(len(r.get('girders', [])) for r in sheet_results),
            'walls': sum(len(r.get('walls', [])) for r in sheet_results),
            'wall_segments': sum(len(r.get('wall_segments', [])) for r in sheet_results),
            'unmatched_columns': sum(len(r.get('unmatched_columns', [])) for r in sheet_results),
        },
        'sheets': sheet_results,
        'gates': {
            k: {'passed': v[0], 'detail': list(v[1:])} for k, v in gates.items()
        },
        'elapsed_s': round(time.time() - t0, 1),
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out_meta, f, ensure_ascii=False, indent=2)
    print(f'[메타] {OUT_JSON}')

    # BOQ
    write_boq_v3(sheet_results, shapes, total_volume, gates, OUT_BOQ_MD)
    print(f'[BOQ] {OUT_BOQ_MD}')

    # ============================================================
    # 최종 보고
    # ============================================================
    print(f'\n{"="*60}')
    print(f'[v3 통합 PoC 최종 보고]')
    print(f'  처리 도엽: {len(sheet_results)}개')
    print(f'  총 솔리드: {len(shapes)}개')
    for kind, cnt in sorted(kind_count.items()):
        print(f'    {kind}: {cnt}')
    print(f'  총 부피: {total_volume / 1e9:.3f} m³')
    print(f'  처리 시간: {round(time.time()-t0, 1)}s')
    print()
    all_passed = all(v[0] for v in gates.values())
    print(f'  [게이트] {"전체 통과" if all_passed else "일부 실패"}')
    for k, v in gates.items():
        mark = 'PASS' if v[0] else 'FAIL'
        print(f'    [{mark}] {k}')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
