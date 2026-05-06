"""
build_v6_bay_grid.py — 베이별 보+슬라브 그리드 빌드
====================================================
방부장 참조 모델 기준:
  - 기둥 간 보 연결 (adjacent column beams)
  - 베이별 슬라브 패널 (bay-by-bay slab)
  - 주차장 B1F 층고 4400mm (방부장 직접 명시)
  - 타워 B1F 층고 5970mm (도면 직독)

실행: freecadcmd tests/build_v6_bay_grid.py
"""
import sys, os, struct, math, json
os.chdir('D:/Git/FreeCAD_4TH')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, FreeCAD, Mesh
import numpy as np
import ezdxf
from core.dxf_parser.structural_extractor import StructuralExtractor

# ── 확정 치수 ────────────────────────────────────────────────
SL_B2F  = -9050.0
SL_B1F  = -5600.0
SL_1F   =   370.0
SLAB_T  =   150.0
GIRDER_H =  900.0

# 방부장 명시: 주차장 B1F 층고 4400mm
PKG_B1F_H   = 4400.0
PKG_B1F_TOP = SL_B1F + PKG_B1F_H   # -5600 + 4400 = -1200mm

# 타워 B1F 층고 (도면: 1F SL - B1F SL = 5970mm)
TOWER_B1F_TOP = SL_1F               # +370mm

# 좌표 통일 (centroid 기반)
TX, TY = -425013.0, 3616519.0
def btrans(x, y): return x + TX, y + TY

# 도면 경로
DONG_DXF   = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
BSMNT_DXF  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
DONG_CLIP  = (69013, 2241258, 229013, 2401258)
BSMNT_CLIP = (552082.0, -1376738.0, 712082.0, -1216738.0)

# ── 솔리드 생성 유틸 ─────────────────────────────────────────
def box_s(cx, cy, zb, zt, w, h):
    ht = zt - zb
    w, h = abs(w), abs(h)
    if ht <= 0 or w < 10 or h < 10: return None
    b = Part.makeBox(w, h, ht, FreeCAD.Vector(cx-w/2, cy-h/2, zb))
    return b if b.isValid() else None

def prism(pts, zb, zt):
    ht = zt - zb
    if ht <= 0 or len(pts) < 3: return None
    v = [FreeCAD.Vector(x, y, zb) for x, y in pts]
    v.append(v[0])
    try:
        wire = Part.makePolygon(v)
        face = Part.makeFace(wire, 'Part::FaceMakerBullseye')
        s = face.extrude(FreeCAD.Vector(0, 0, ht))
        return s if s.isValid() else None
    except:
        return None

def beam_box(x0, y0, x1, y1, bw, bh, zb, zt):
    """보 솔리드 — 중심선 + 폭/높이."""
    dx, dy = x1-x0, y1-y0
    ln = math.hypot(dx, dy)
    if ln < 100 or zt <= zb: return None
    ux, uy = -dy/ln, dx/ln
    pts = [(x0+ux*bw/2, y0+uy*bw/2), (x1+ux*bw/2, y1+uy*bw/2),
           (x1-ux*bw/2, y1-uy*bw/2), (x0-ux*bw/2, y0-uy*bw/2)]
    return prism(pts, zb, zt)

# ── 보 그리드 생성 알고리즘 ──────────────────────────────────
def build_beam_grid(col_pts, beam_w, beam_h, z_slab_top,
                    max_span=10500, angle_tol_deg=12):
    """
    기둥 위치 목록 → 인접 기둥 간 보 솔리드 목록.
    max_span: 보 연결 최대 거리 (mm)
    angle_tol_deg: 직교 방향 허용 각도 오차 (도)
    """
    beams = []
    used_pairs = set()
    z_beam_bot = z_slab_top - beam_h
    z_beam_top = z_slab_top - 0  # 보 상단 = 슬라브 하단

    for i, (x1, y1) in enumerate(col_pts):
        for j, (x2, y2) in enumerate(col_pts):
            if j <= i or (i, j) in used_pairs:
                continue
            dist = math.hypot(x2-x1, y2-y1)
            if dist > max_span or dist < 500:
                continue
            # 직교 방향만 (수평 또는 수직)
            angle_deg = abs(math.degrees(math.atan2(y2-y1, x2-x1))) % 180
            is_h = angle_deg < angle_tol_deg or angle_deg > (180 - angle_tol_deg)
            is_v = 90 - angle_tol_deg < angle_deg < 90 + angle_tol_deg
            if not (is_h or is_v):
                continue
            b = beam_box(x1, y1, x2, y2, beam_w, beam_h, z_beam_bot, z_beam_top)
            if b:
                beams.append(b)
            used_pairs.add((i, j))

    return beams

# ── 베이별 슬라브 패널 ────────────────────────────────────────
def build_bay_slabs(col_pts, z_slab_bot, z_slab_top,
                    max_span=10500, row_tol=800):
    """
    기둥 위치 → 베이(Bay)별 슬라브 패널.
    1. 동일 행(Y ≈ 같음) 기둥들 그룹화
    2. 인접 행 쌍 + 인접 열 쌍 = 직사각형 베이 → 슬라브
    """
    slabs = []
    if len(col_pts) < 4:
        return slabs

    # Y 좌표로 그룹화 (row_tol 이내 = 같은 행)
    sorted_pts = sorted(col_pts, key=lambda p: p[1])
    rows = []
    for pt in sorted_pts:
        placed = False
        for row in rows:
            if abs(pt[1] - row[0][1]) < row_tol:
                row.append(pt)
                placed = True
                break
        if not placed:
            rows.append([pt])

    # 각 행 내에서 X로 정렬
    rows = [sorted(row, key=lambda p: p[0]) for row in rows
            if len(row) >= 2]
    rows.sort(key=lambda r: r[0][1])

    # 인접 행 쌍에서 베이 찾기
    for ri in range(len(rows) - 1):
        row_a = rows[ri]
        row_b = rows[ri + 1]
        y_span = abs(row_b[0][1] - row_a[0][1])
        if y_span > max_span:
            continue

        # row_a의 인접 열 쌍
        for ci in range(len(row_a) - 1):
            xa0, ya0 = row_a[ci]
            xa1, ya1 = row_a[ci + 1]
            x_span = abs(xa1 - xa0)
            if x_span > max_span:
                continue

            # row_b에서 대응하는 열 찾기
            def find_near(pts, x_target, tol=row_tol):
                best = min(pts, key=lambda p: abs(p[0] - x_target))
                return best if abs(best[0] - x_target) < tol + x_span * 0.3 else None

            pb0 = find_near(row_b, xa0)
            pb1 = find_near(row_b, xa1)
            if pb0 is None or pb1 is None:
                continue
            if abs(pb0[0] - pb1[0]) > max_span:
                continue

            # 4점 슬라브 패널
            xmin = min(xa0, xa1, pb0[0], pb1[0])
            xmax = max(xa0, xa1, pb0[0], pb1[0])
            ymin = min(ya0, row_b[0][1])
            ymax = max(ya0, row_b[0][1])

            pts4 = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
            s = prism(pts4, z_slab_bot, z_slab_top)
            if s:
                slabs.append(s)

    return slabs

# ── 추출 ─────────────────────────────────────────────────────
print('[추출] 지하주차장 골조...')
ext = StructuralExtractor(min_col_size=100, max_col_size=3000, min_slab_area_m2=50)
doc_b = ezdxf.readfile(BSMNT_DXF, encoding='cp949')
d2 = ext.extract(doc_b, clip=BSMNT_CLIP)
print(f'  기둥{len(d2.columns)} 전단벽{len(d2.shear_walls)} 슬라브외곽{len(d2.slab_outlines)}')

print('[추출] 101동 골조...')
doc_d = ezdxf.readfile(DONG_DXF, encoding='cp949')
d1 = ext.extract(doc_d, clip=DONG_CLIP)
print(f'  기둥{len(d1.columns)} 전단벽{len(d1.shear_walls)}')

# ── 빌드 ─────────────────────────────────────────────────────
doc = FreeCAD.newDocument('v6')
shapes = []
stats = {'slab':0, 'col':0, 'beam':0, 'wall':0}

# ─── 지하주차장 ────────────────────────────────────────────
pkg_pts = [(btrans(c.cx, c.cy)) for c in d2.columns]
pkg_col_data = [(btrans(c.cx, c.cy), c.w, c.h) for c in d2.columns]

for fk, zb, zt, bh_top in [
    ('B2F', SL_B2F, SL_B1F, SL_B1F),          # B2F: 3450mm
    ('B1F', SL_B1F, PKG_B1F_TOP, PKG_B1F_TOP)  # B1F: 4400mm (방부장 명시)
]:
    z_slab_b = zt - SLAB_T
    z_slab_t = zt
    z_col_t  = z_slab_b
    z_beam_b = z_slab_b - GIRDER_H
    z_beam_t = z_slab_b

    print(f'\n[주차장 {fk}] 층고={zt-zb:.0f}mm  B1F-TOP={zt:.0f}mm')

    # 기둥
    for (ux, uy), cw, ch in pkg_col_data:
        s = box_s(ux, uy, zb, z_col_t, cw, ch)
        if s: shapes.append(s); stats['col'] += 1

    # 보 그리드 (주차장 보: 폭400, 높이900)
    beams = build_beam_grid(pkg_pts, beam_w=400, beam_h=GIRDER_H,
                            z_slab_top=zt, max_span=10500)
    shapes.extend(beams); stats['beam'] += len(beams)
    print(f'  기둥{len(pkg_col_data)}  보{len(beams)}')

    # 베이별 슬라브 패널
    bay_slabs = build_bay_slabs(pkg_pts, z_slab_b, z_slab_t, max_span=10500)
    shapes.extend(bay_slabs); stats['slab'] += len(bay_slabs)
    print(f'  베이슬라브{len(bay_slabs)}')

# ─── 101동 타워 ────────────────────────────────────────────
dong_pts = [(c.cx, c.cy) for c in d1.columns]
dong_col_data = [(c.cx, c.cy, c.w, c.h) for c in d1.columns]

for fk, zb, zt in [
    ('B2F', SL_B2F, SL_B1F),
    ('B1F', SL_B1F, TOWER_B1F_TOP)  # 타워: 5970mm
]:
    z_slab_b = zt - SLAB_T
    z_col_t  = z_slab_b
    z_beam_t = z_slab_b
    z_beam_b = z_slab_b - GIRDER_H

    print(f'\n[타워 {fk}] 층고={zt-zb:.0f}mm')

    for cx, cy, cw, ch in dong_col_data:
        s = box_s(cx, cy, zb, z_col_t, cw, ch)
        if s: shapes.append(s); stats['col'] += 1

    # 타워 보 그리드
    t_beams = build_beam_grid(dong_pts, beam_w=400, beam_h=GIRDER_H,
                               z_slab_top=zt, max_span=9000)
    shapes.extend(t_beams); stats['beam'] += len(t_beams)

    # 타워 베이 슬라브
    t_slabs = build_bay_slabs(dong_pts, z_slab_b, zt, max_span=9000)
    shapes.extend(t_slabs); stats['slab'] += len(t_slabs)
    print(f'  기둥{len(dong_col_data)} 보{len(t_beams)} 베이슬라브{len(t_slabs)}')

# ─── 전단벽 (주차장) ─────────────────────────────────────────
for fk, zb, zt in [('B2F', SL_B2F, SL_B1F), ('B1F', SL_B1F, PKG_B1F_TOP)]:
    cnt = 0
    for wp in d2.shear_walls:
        if cnt >= 80: break
        if wp.thickness < 150 or wp.overlap_length < 1500: continue
        x0, y0 = btrans(*wp.centerline_p1)
        x1, y1 = btrans(*wp.centerline_p2)
        dx, dy = x1-x0, y1-y0; ln = math.hypot(dx, dy)
        if ln < 100: continue
        ux, uy = -dy/ln, dx/ln; t = wp.thickness
        pts = [(x0+ux*t/2, y0+uy*t/2),(x1+ux*t/2, y1+uy*t/2),
               (x1-ux*t/2, y1-uy*t/2),(x0-ux*t/2, y0-uy*t/2)]
        s = prism(pts, zb, zt-SLAB_T)
        if s: shapes.append(s); stats['wall'] += 1; cnt += 1

# ── STEP + STL 출력 ──────────────────────────────────────────
print(f'\n[결과] {stats}')
compound = Part.makeCompound(shapes)
feat = doc.addObject('Part::Feature', 'v6')
feat.Shape = compound; doc.recompute()
feat.Shape.exportStep('output/poc_v6_101.step')
vol = compound.Volume / 1e9
n_sol = len(feat.Shape.Solids)
print(f'[완료] {n_sol} 솔리드, {vol:.0f} m³')
print(f'  주차장B1F: SL{SL_B1F:.0f}→천장{PKG_B1F_TOP:.0f}mm (층고{PKG_B1F_H:.0f}mm)')
print(f'  타워B1F: SL{SL_B1F:.0f}→1F{TOWER_B1F_TOP:.0f}mm (층고{TOWER_B1F_TOP-SL_B1F:.0f}mm)')

m2 = Mesh.Mesh()
mesh_tup = feat.Shape.tessellate(300.0)
verts2, faces2 = mesh_tup
for f in faces2:
    m2.addFacet(FreeCAD.Vector(*verts2[f[0]]),
                FreeCAD.Vector(*verts2[f[1]]),
                FreeCAD.Vector(*verts2[f[2]]))
m2.write('output/poc_v6_101.stl')
print('[STEP] output/poc_v6_101.step')
print('[STL]  output/poc_v6_101.stl')
