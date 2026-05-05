"""
102동 지하1층 v2 — 정도전 청구항 적용 (정밀도 3건 검증)

v1 (test_b1f_102.py) 대비 변경:
1. LINE 추출 직후 weld_vertices + normalize_to_grid (정밀도 ③ 부재 분해 방지)
2. merge_collinear_lines (동일 직선 사전 통합, 정밀도 ③ 강화)
3. align_pair_to_rectangle (라인 페어를 정사영으로 직사각형화, 정밀도 ① 평행사변형 제거)

청구항 출처: d:/Git/BOQ_2/.../trim_manager.rb + geometry_builder.rb (정도전, Patent C v11.4)
이식: d:/Git/FreeCAD_4TH/core/patent_c_port.py

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_b1f_102_v2_patent_c.py
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_PATH = "tests/fixtures/102_B1F.dxf"
OUT_PATH = "output/test_102_B1F_v2.step"

GIRDER_HEIGHT = 700
PC_HEIGHT     = 300
SLAB_THICKNESS = 210
FLOOR_HEIGHT  = 4400
SLAB_BOTTOM_Z = FLOOR_HEIGHT - SLAB_THICKNESS
WALL_HEIGHT   = SLAB_BOTTOM_Z
GIRDER_Z_BASE = SLAB_BOTTOM_Z - GIRDER_HEIGHT
PC_Z_BASE     = SLAB_BOTTOM_Z - PC_HEIGHT
WALL_THICKNESS = 250

from core.patent_c_port import (
    weld_vertices, normalize_to_grid,
    merge_collinear_lines, align_pair_to_rectangle,
)

# ── 1. DXF 파싱 ─────────────────────────────────────────────
import ezdxf
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

slab_lines = []
slab_lwpolys = []
for e in msp:
    layer = e.dxf.layer
    if layer == '00_SLAB END + ETC':
        if e.dxftype() == 'LINE':
            slab_lines.append(((e.dxf.start.x, e.dxf.start.y),
                               (e.dxf.end.x, e.dxf.end.y)))
        elif e.dxftype() == 'LWPOLYLINE':
            pts = [(x, y) for x, y, *_ in e.get_points()]
            slab_lwpolys.append((pts, e.is_closed))

print(f"[DXF] 슬라브 LINE {len(slab_lines)}개, LWPOLYLINE {len(slab_lwpolys)}개")

# 클립 영역
all_pts_for_clip = [p for s, ed in slab_lines for p in [s, ed]]
all_pts_for_clip += [p for pts, _ in slab_lwpolys for p in pts]
clip_xmin = min(p[0] for p in all_pts_for_clip) - 5000
clip_xmax = max(p[0] for p in all_pts_for_clip) + 5000
clip_ymin = min(p[1] for p in all_pts_for_clip) - 5000
clip_ymax = max(p[1] for p in all_pts_for_clip) + 5000

def in_clip(x, y):
    return clip_xmin <= x <= clip_xmax and clip_ymin <= y <= clip_ymax

norm_x = clip_xmin
norm_y = clip_ymin
def norm(p): return (p[0] - norm_x, p[1] - norm_y)

# ── 2. 거더/PC 추출 ─────────────────────────────────────────
girder_polys = []
girder_lines = []
pc_polys = []
wall_polys = []
wall_lines = []

for ins in msp.query('INSERT'):
    name = ins.dxf.name
    is_girder = ('B1F' in name and 'GIRDER' in name)
    is_pc = ('B1F' in name and 'PC' in name)
    is_wall = ('WALL' in name and 'COL' in name)
    if not (is_girder or is_pc or is_wall):
        continue
    print(f"[블록] {name}")
    for ent in ins.virtual_entities():
        if ent.dxftype() == 'LWPOLYLINE':
            pts = [(x, y) for x, y, *_ in ent.get_points()]
            if not pts or not all(in_clip(x, y) for x, y in pts):
                continue
            if is_girder: girder_polys.append(pts)
            elif is_pc: pc_polys.append(pts)
            elif is_wall: wall_polys.append(pts)
        elif ent.dxftype() == 'LINE':
            s, e2 = ent.dxf.start, ent.dxf.end
            if in_clip(s.x, s.y) and in_clip(e2.x, e2.y):
                seg = ((s.x, s.y), (e2.x, e2.y))
                if is_girder: girder_lines.append(seg)
                elif is_wall: wall_lines.append(seg)

# 모델스페이스 S-ABW1, S-ARW1 (벽체)
for e in msp:
    if e.dxf.layer in ('S-ABW1', 'S-ARW1') and e.dxftype() == 'LWPOLYLINE':
        pts = [(x, y) for x, y, *_ in e.get_points()]
        if pts and all(in_clip(x, y) for x, y in pts):
            wall_polys.append(pts)

print(f"[추출] 거더 폴리 {len(girder_polys)}개, LINE {len(girder_lines)}개")
print(f"[추출] 벽-기둥 폴리 {len(wall_polys)}개, LINE {len(wall_lines)}개")
print(f"[추출] PC {len(pc_polys)}개")

# ── 3. ★ 정도전 청구항 적용 ★ ──────────────────────────────
print("\n[Patent C 적용] 정도전 청구항 1·4 + Healer 적용...")

def apply_patent_c_to_lines(lines, label):
    """LINE 리스트에 weld + normalize + merge collinear 적용"""
    if not lines:
        return lines
    # 1) 정점 추출 → weld → normalize
    all_endpoints = []
    for s, e in lines:
        all_endpoints.append(s)
        all_endpoints.append(e)
    welded_pts = weld_vertices(all_endpoints, tolerance=5.0)  # 5mm 이내 동일 노드
    normalized_pts = normalize_to_grid(welded_pts, tolerance=1.0)  # 1mm 그리드

    # weld된 결과로 LINE 재구성
    cleaned = []
    for i in range(0, len(normalized_pts), 2):
        s = normalized_pts[i]
        e = normalized_pts[i+1] if i+1 < len(normalized_pts) else None
        if e and (abs(s[0]-e[0]) > 1 or abs(s[1]-e[1]) > 1):
            cleaned.append((s, e))

    # 2) 동일 직선 LINE 통합
    merged = merge_collinear_lines(cleaned, angle_tol_deg=1.0, gap_tol=50.0)
    print(f"  [{label}] {len(lines)} → weld·normalize → {len(cleaned)} → merge collinear → {len(merged)}")
    return merged

girder_lines_v2 = apply_patent_c_to_lines(girder_lines, "거더")
wall_lines_v2  = apply_patent_c_to_lines(wall_lines, "벽-기둥")

# ── 4. 페어링 (이전과 동일 알고리즘) ────────────────────────
def line_dir_normal(seg):
    (x1, y1), (x2, y2) = seg
    dx, dy = x2-x1, y2-y1
    L = math.hypot(dx, dy)
    if L < 1e-6: return None, None, 0
    return (dx/L, dy/L), (-dy/L, dx/L), L

def is_parallel(s1, s2, tol=0.05):
    d1, _, _ = line_dir_normal(s1); d2, _, _ = line_dir_normal(s2)
    if d1 is None or d2 is None: return False
    return abs(d1[0]*d2[1] - d1[1]*d2[0]) < tol

def line_distance(s1, s2):
    d1, n1, _ = line_dir_normal(s1)
    if d1 is None: return float('inf')
    mx1 = (s1[0][0]+s1[1][0])/2; my1 = (s1[0][1]+s1[1][1])/2
    mx2 = (s2[0][0]+s2[1][0])/2; my2 = (s2[0][1]+s2[1][1])/2
    return abs((mx2-mx1)*n1[0] + (my2-my1)*n1[1])

def overlap_check(s1, s2):
    d1, _, L1 = line_dir_normal(s1)
    if d1 is None: return 0
    base = s1[0]
    t1 = (s2[0][0]-base[0])*d1[0] + (s2[0][1]-base[1])*d1[1]
    t2 = (s2[1][0]-base[0])*d1[0] + (s2[1][1]-base[1])*d1[1]
    lo, hi = sorted([t1, t2])
    return max(0, min(L1, hi) - max(0, lo))

def pair_lines(lines, dist_min, dist_max, min_len=200, min_overlap=200):
    used = [False] * len(lines)
    pairs = []
    for i in range(len(lines)):
        if used[i]: continue
        s1 = lines[i]; _, _, L1 = line_dir_normal(s1)
        if L1 < min_len: continue
        best_j, best_ov = -1, 0
        for j in range(i+1, len(lines)):
            if used[j]: continue
            s2 = lines[j]
            if not is_parallel(s1, s2): continue
            d = line_distance(s1, s2)
            if not (dist_min <= d <= dist_max): continue
            ov = overlap_check(s1, s2)
            if ov > best_ov:
                best_ov = ov; best_j = j
        if best_j >= 0 and best_ov > min_overlap:
            pairs.append((s1, lines[best_j]))
            used[i] = True; used[best_j] = True
    return pairs

# 정규화된 좌표로 페어링
norm_wlines = [(norm(s), norm(e)) for s, e in wall_lines_v2]
norm_glines = [(norm(s), norm(e)) for s, e in girder_lines_v2]
wall_pairs = pair_lines(norm_wlines, 150, 400, 150, 100)
girder_pairs = pair_lines(norm_glines, 100, 600, 200, 200)
print(f"[페어링] 벽-기둥 {len(wall_pairs)}개, 거더 {len(girder_pairs)}개")

# ── 5. ★ 페어 → 직사각형 정렬 (정밀도 ① 해결) ★ ────────────
print("[Patent C] 라인 페어 직사각형 정렬 (청구항 1 정사영 응용)")

# ── 6. FreeCAD 3D 생성 ─────────────────────────────────────
print("\n[FreeCAD] 3D 생성")
import FreeCAD, Part
from shapely.geometry import Polygon as ShPoly
from shapely.validation import make_valid

def loop_to_face(coords, z, tol=1.0):
    cleaned = [coords[0]]
    for p in coords[1:]:
        if abs(p[0]-cleaned[-1][0]) > tol or abs(p[1]-cleaned[-1][1]) > tol:
            cleaned.append(p)
    if abs(cleaned[0][0]-cleaned[-1][0]) > tol or abs(cleaned[0][1]-cleaned[-1][1]) > tol:
        cleaned.append(cleaned[0])
    if len(cleaned) < 4: return None
    pts = [FreeCAD.Vector(x, y, z) for x, y in cleaned]
    edges = []
    for k in range(len(pts)-1):
        if pts[k].distanceToPoint(pts[k+1]) > tol:
            edges.append(Part.makeLine(pts[k], pts[k+1]))
    wire = Part.Wire(edges)
    if not wire.isClosed():
        edges.append(Part.makeLine(pts[-1], pts[0]))
        wire = Part.Wire(edges)
    return Part.Face(wire)

def make_extrusion(coords, z_base, height):
    poly = ShPoly(coords)
    if not poly.is_valid:
        fixed = make_valid(poly)
        if fixed.geom_type == 'MultiPolygon':
            poly = max(fixed.geoms, key=lambda p: p.area)
        elif fixed.geom_type == 'GeometryCollection':
            polys = [g for g in fixed.geoms if g.geom_type == 'Polygon']
            if not polys: return None
            poly = max(polys, key=lambda p: p.area)
        else:
            poly = fixed
    if not hasattr(poly, 'exterior'): return None
    coords2 = list(poly.exterior.coords)
    face = loop_to_face(coords2, z_base)
    if face is None: return None
    return face.extrude(FreeCAD.Vector(0, 0, height))

shapes = []

# 슬라브 (이전과 동일, LWPOLYLINE → LINE 어셈블리)
def assemble_loops(lines, tol=50):
    segments = [[norm(s), norm(e)] for s, e in lines]
    used = [False]*len(segments)
    loops = []
    while True:
        start = next((i for i, u in enumerate(used) if not u), None)
        if start is None: break
        loop = [segments[start][0], segments[start][1]]
        used[start] = True
        for _ in range(len(segments)):
            last = loop[-1]; found = False
            for j, seg in enumerate(segments):
                if used[j]: continue
                if abs(seg[0][0]-last[0]) < tol and abs(seg[0][1]-last[1]) < tol:
                    loop.append(seg[1]); used[j] = True; found = True; break
                if abs(seg[1][0]-last[0]) < tol and abs(seg[1][1]-last[1]) < tol:
                    loop.append(seg[0]); used[j] = True; found = True; break
            if not found: break
            if abs(loop[-1][0]-loop[0][0]) < tol and abs(loop[-1][1]-loop[0][1]) < tol:
                break
        if len(loop) >= 4: loops.append(loop)
    return loops

slab_loops = assemble_loops(slab_lines, tol=50)
slab_count = 0; slab_vol = 0
for loop in slab_loops:
    sld = make_extrusion(loop, SLAB_BOTTOM_Z, SLAB_THICKNESS)
    if sld:
        shapes.append((f'slab_{slab_count+1}', sld))
        slab_count += 1; slab_vol += sld.Volume / 1e9

for pts, _ in slab_lwpolys:
    nc = [norm(p) for p in pts]
    sld = make_extrusion(nc, SLAB_BOTTOM_Z, SLAB_THICKNESS)
    if sld:
        shapes.append((f'slab_lp_{slab_count+1}', sld))
        slab_count += 1; slab_vol += sld.Volume / 1e9
print(f"[슬라브] {slab_count}개 / {slab_vol:.3f} m³")

# 거더 (★ 페어 → 직사각형 정렬 후 extrude)
girder_count = 0; girder_vol = 0
for pts in girder_polys:
    nc = [norm(p) for p in pts]
    sld = make_extrusion(nc, GIRDER_Z_BASE, GIRDER_HEIGHT)
    if sld:
        shapes.append((f'girder_lp_{girder_count+1}', sld))
        girder_count += 1; girder_vol += sld.Volume / 1e9

for s1, s2 in girder_pairs:
    rect = align_pair_to_rectangle(s1, s2)  # ★ 평행사변형 제거
    sld = make_extrusion(rect, GIRDER_Z_BASE, GIRDER_HEIGHT)
    if sld:
        shapes.append((f'girder_ln_{girder_count+1}', sld))
        girder_count += 1; girder_vol += sld.Volume / 1e9
print(f"[거더] {girder_count}개 / {girder_vol:.3f} m³")

# PC
pc_count = 0; pc_vol = 0
for pts in pc_polys:
    nc = [norm(p) for p in pts]
    sld = make_extrusion(nc, PC_Z_BASE, PC_HEIGHT)
    if sld:
        shapes.append((f'pc_{pc_count+1}', sld))
        pc_count += 1; pc_vol += sld.Volume / 1e9
print(f"[PC] {pc_count}개 / {pc_vol:.3f} m³")

# 벽-기둥 (★ 페어 → 직사각형 정렬)
wall_count = 0; wall_vol = 0
for pts in wall_polys:
    nc = [norm(p) for p in pts]
    sld = make_extrusion(nc, 0, WALL_HEIGHT)
    if sld:
        shapes.append((f'wall_lp_{wall_count+1}', sld))
        wall_count += 1; wall_vol += sld.Volume / 1e9

for s1, s2 in wall_pairs:
    rect = align_pair_to_rectangle(s1, s2)  # ★ 평행사변형 제거
    sld = make_extrusion(rect, 0, WALL_HEIGHT)
    if sld:
        shapes.append((f'wall_ln_{wall_count+1}', sld))
        wall_count += 1; wall_vol += sld.Volume / 1e9
print(f"[벽-기둥] {wall_count}개 / {wall_vol:.3f} m³")

# ── 7. 결과 저장 + STEP ────────────────────────────────────
total_vol = slab_vol + girder_vol + pc_vol + wall_vol
print(f"\n{'='*45}")
print(f"102동 지하1층 — Patent C 적용 v2")
print(f"{'='*45}")
print(f"  슬라브 : {slab_count:3d}개  {slab_vol:>10.3f} m³")
print(f"  거더   : {girder_count:3d}개  {girder_vol:>10.3f} m³")
print(f"  PC     : {pc_count:3d}개  {pc_vol:>10.3f} m³")
print(f"  벽-기둥: {wall_count:3d}개  {wall_vol:>10.3f} m³")
print(f"  합계   : {len(shapes):3d}개  {total_vol:>10.3f} m³")
print(f"{'='*45}")

os.makedirs("output", exist_ok=True)
if shapes:
    compound = Part.makeCompound([s for _, s in shapes])
    compound.exportStep(OUT_PATH)
    print(f"\n[저장] {OUT_PATH}")
print("완료.")
