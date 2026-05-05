"""
102동 지하1층 단일 작업 (B1F만, 102동 영역만)
- B1F GIRDER 블록 explode → 거더 추출
- B1F-PC 블록 explode → PC 부재 추출
- 모델스페이스 슬라브 (00_SLAB END + ETC)
- 102동 영역 내로 클리핑

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_b1f_102.py
"""

import sys
import os
import math
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_PATH = "tests/fixtures/102_B1F.dxf"
OUT_PATH = "output/test_102_B1F.step"

GIRDER_HEIGHT = 700      # 거더 임시 높이 (mm) - 슬라브 아래로 매달림
PC_HEIGHT     = 300      # PC 슬래브 임시 높이 - 슬라브 아래로 매달림
SLAB_THICKNESS = 210
FLOOR_HEIGHT  = 4400     # 지하주차장 층고 4.4m
SLAB_BOTTOM_Z = FLOOR_HEIGHT - SLAB_THICKNESS  # 4190
WALL_HEIGHT   = SLAB_BOTTOM_Z   # 벽-기둥: 0 ~ 슬라브 바닥
GIRDER_Z_BASE = SLAB_BOTTOM_Z - GIRDER_HEIGHT   # 거더: 슬라브 바닥에서 700 아래
PC_Z_BASE     = SLAB_BOTTOM_Z - PC_HEIGHT        # PC: 슬라브 바닥에서 300 아래
WALL_THICKNESS = 250     # 지하 벽체 임시 두께

# ── 1. 도면 로드 ─────────────────────────────────────────────
import ezdxf
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

# ── 2. 102동 클리핑 영역 (슬라브로부터 자동) ─────────────────
slab_lines = []
slab_lwpolys = []
for e in msp:
    if e.dxf.layer != '00_SLAB END + ETC':
        continue
    if e.dxftype() == 'LINE':
        slab_lines.append(((e.dxf.start.x, e.dxf.start.y),
                           (e.dxf.end.x, e.dxf.end.y)))
    elif e.dxftype() == 'LWPOLYLINE':
        pts = [(x, y) for x, y, *_ in e.get_points()]
        slab_lwpolys.append((pts, e.is_closed))

all_pts = [p for s, e in slab_lines for p in [s, e]]
all_pts += [p for pts, _ in slab_lwpolys for p in pts]
clip_xmin = min(p[0] for p in all_pts) - 5000
clip_xmax = max(p[0] for p in all_pts) + 5000
clip_ymin = min(p[1] for p in all_pts) - 5000
clip_ymax = max(p[1] for p in all_pts) + 5000

print(f"[클립영역] X={clip_xmin:.0f}~{clip_xmax:.0f}, Y={clip_ymin:.0f}~{clip_ymax:.0f}")

def in_clip(x, y):
    return clip_xmin <= x <= clip_xmax and clip_ymin <= y <= clip_ymax

# 좌표 정규화
norm_x = clip_xmin
norm_y = clip_ymin

def norm(p):
    return (p[0] - norm_x, p[1] - norm_y)

# ── 3. 슬라브 (모델스페이스) ─────────────────────────────────
print(f"[슬라브] LINE {len(slab_lines)}개 + LWPOLYLINE {len(slab_lwpolys)}개")

# ── 4. B1F GIRDER + B1F-PC 블록 explode → 영역 내 부재 ─────
girder_polys = []
girder_lines = []
pc_polys = []

for ins in msp.query('INSERT'):
    name = ins.dxf.name
    is_girder = ('B1F' in name and 'GIRDER' in name)
    is_pc = ('B1F' in name and 'PC' in name)
    if not (is_girder or is_pc):
        continue

    print(f"[블록] {name} explode 중...")
    for ent in ins.virtual_entities():
        if ent.dxftype() == 'LWPOLYLINE':
            pts = [(x, y) for x, y, *_ in ent.get_points()]
            if not pts or not all(in_clip(x, y) for x, y in pts):
                continue
            (girder_polys if is_girder else pc_polys).append(pts)
        elif ent.dxftype() == 'LINE' and is_girder:
            s, e = ent.dxf.start, ent.dxf.end
            if in_clip(s.x, s.y) and in_clip(e.x, e.y):
                girder_lines.append(((s.x, s.y), (e.x, e.y)))

print(f"[추출] 거더 폴리곤 {len(girder_polys)}개, 거더 LINE {len(girder_lines)}개, PC {len(pc_polys)}개")

# ── 4-helper. 평행선 페어링 함수 ─────────────────────────────
def line_dir_normal(seg):
    (x1, y1), (x2, y2) = seg
    dx, dy = x2-x1, y2-y1
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return None, None, 0
    return (dx/L, dy/L), (-dy/L, dx/L), L

def is_parallel(s1, s2, tol=0.05):
    d1, _, _ = line_dir_normal(s1)
    d2, _, _ = line_dir_normal(s2)
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
        s1 = lines[i]
        _, _, L1 = line_dir_normal(s1)
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

# ── 4c. 벽체 추출: 모델스페이스 S-ABW1/S-ARW1 + B2F-WALL COL 블록 ─
wall_polys = []
wall_lines = []

for e in msp:
    if e.dxf.layer in ('S-ABW1', 'S-ARW1') and e.dxftype() == 'LWPOLYLINE':
        pts = [(x, y) for x, y, *_ in e.get_points()]
        if pts and all(in_clip(x, y) for x, y in pts):
            wall_polys.append(pts)

for ins in msp.query('INSERT'):
    if 'WALL' not in ins.dxf.name or 'COL' not in ins.dxf.name:
        continue
    print(f"[블록] {ins.dxf.name} (벽-기둥) explode 중...")
    for ent in ins.virtual_entities():
        if ent.dxftype() == 'LWPOLYLINE':
            pts = [(x, y) for x, y, *_ in ent.get_points()]
            if pts and all(in_clip(x, y) for x, y in pts):
                wall_polys.append(pts)
        elif ent.dxftype() == 'LINE':
            s, e2 = ent.dxf.start, ent.dxf.end
            if in_clip(s.x, s.y) and in_clip(e2.x, e2.y):
                wall_lines.append(((s.x, s.y), (e2.x, e2.y)))

print(f"[벽-기둥] 폴리곤 {len(wall_polys)}개, LINE {len(wall_lines)}개")

norm_wlines = [(norm(s), norm(e)) for s, e in wall_lines]
wall_pairs = pair_lines(norm_wlines, dist_min=150, dist_max=400, min_len=150, min_overlap=100)
print(f"[벽-기둥] LINE 페어링: {len(wall_pairs)}개 세그먼트")

normalized = [(norm(s), norm(e)) for s, e in girder_lines]
girder_pairs = pair_lines(normalized, dist_min=100, dist_max=600, min_len=200, min_overlap=200)
print(f"[거더] LINE 페어링: {len(girder_pairs)}개 거더 세그먼트")

# ── 5. FreeCAD 3D 생성 ──────────────────────────────────────
print("\n[FreeCAD] 3D 생성 시작...")
import FreeCAD
import Part
from shapely.geometry import Polygon as ShPoly
from shapely.validation import make_valid

def loop_to_face(coords, z, tol=1.0):
    cleaned = [coords[0]]
    for p in coords[1:]:
        if abs(p[0] - cleaned[-1][0]) > tol or abs(p[1] - cleaned[-1][1]) > tol:
            cleaned.append(p)
    if abs(cleaned[0][0] - cleaned[-1][0]) > tol or abs(cleaned[0][1] - cleaned[-1][1]) > tol:
        cleaned.append(cleaned[0])
    if len(cleaned) < 4:
        return None
    pts = [FreeCAD.Vector(x, y, z) for x, y in cleaned]
    edges = []
    for k in range(len(pts) - 1):
        if pts[k].distanceToPoint(pts[k+1]) > tol:
            edges.append(Part.makeLine(pts[k], pts[k+1]))
    wire = Part.Wire(edges)
    if not wire.isClosed():
        edges.append(Part.makeLine(pts[-1], pts[0]))
        wire = Part.Wire(edges)
    return Part.Face(wire)

def make_extrusion(coords, z_base, height):
    """좌표 폴리곤 → 자체교차 수정 → extrude"""
    norm_coords = [norm(p) for p in coords]
    poly = ShPoly(norm_coords)
    if not poly.is_valid:
        fixed = make_valid(poly)
        if fixed.geom_type == 'MultiPolygon':
            poly = max(fixed.geoms, key=lambda p: p.area)
        elif fixed.geom_type == 'GeometryCollection':
            polys = [g for g in fixed.geoms if g.geom_type == 'Polygon']
            if not polys:
                return None
            poly = max(polys, key=lambda p: p.area)
        else:
            poly = fixed
    if not hasattr(poly, 'exterior'):
        return None
    coords2 = list(poly.exterior.coords)
    face = loop_to_face(coords2, z_base)
    if face is None:
        return None
    return face.extrude(FreeCAD.Vector(0, 0, height))

shapes = []

# 슬라브 LWPOLYLINE 처리 (1순위)
slab_count = 0
slab_vol = 0
for pts, closed in slab_lwpolys:
    sld = make_extrusion(pts, SLAB_BOTTOM_Z, SLAB_THICKNESS)
    if sld:
        shapes.append((f'slab_lp_{slab_count+1}', sld))
        slab_count += 1
        slab_vol += sld.Volume / 1e9

# 슬라브 LINE 어셈블리
def assemble_loops(lines, tol=50):
    segments = [[norm(s), norm(e)] for s, e in lines]
    used = [False] * len(segments)
    loops = []
    while True:
        start = next((i for i, u in enumerate(used) if not u), None)
        if start is None:
            break
        loop = [segments[start][0], segments[start][1]]
        used[start] = True
        for _ in range(len(segments)):
            last = loop[-1]
            found = False
            for j, seg in enumerate(segments):
                if used[j]: continue
                if abs(seg[0][0]-last[0]) < tol and abs(seg[0][1]-last[1]) < tol:
                    loop.append(seg[1]); used[j] = True; found = True; break
                if abs(seg[1][0]-last[0]) < tol and abs(seg[1][1]-last[1]) < tol:
                    loop.append(seg[0]); used[j] = True; found = True; break
            if not found:
                break
            if abs(loop[-1][0]-loop[0][0]) < tol and abs(loop[-1][1]-loop[0][1]) < tol:
                break
        if len(loop) >= 4:
            loops.append(loop)
    return loops

slab_line_loops = assemble_loops(slab_lines)
for loop in slab_line_loops:
    poly = ShPoly(loop)
    if not poly.is_valid:
        fixed = make_valid(poly)
        if fixed.geom_type == 'MultiPolygon':
            poly = max(fixed.geoms, key=lambda p: p.area)
        elif hasattr(fixed, 'exterior'):
            poly = fixed
        else:
            continue
    if not hasattr(poly, 'exterior'):
        continue
    coords = list(poly.exterior.coords)
    face = loop_to_face(coords, SLAB_BOTTOM_Z)
    if face is None: continue
    try:
        sld = face.extrude(FreeCAD.Vector(0, 0, SLAB_THICKNESS))
        shapes.append((f'slab_ln_{slab_count+1}', sld))
        slab_count += 1
        slab_vol += sld.Volume / 1e9
    except Exception:
        pass

print(f"[슬라브] {slab_count}개 / {slab_vol:.3f} m³")

# 거더 (LWPOLYLINE) - 슬라브 아래에 매달림
girder_count = 0
girder_vol = 0
for pts in girder_polys:
    sld = make_extrusion(pts, GIRDER_Z_BASE, GIRDER_HEIGHT)
    if sld:
        shapes.append((f'girder_lp_{girder_count+1}', sld))
        girder_count += 1
        girder_vol += sld.Volume / 1e9

# 거더 (LINE 페어 → 사각형 face → extrude)
for i, (s1, s2) in enumerate(girder_pairs):
    try:
        p1, p2 = s1
        p3, p4 = s2
        d_p2_p3 = math.hypot(p2[0]-p3[0], p2[1]-p3[1])
        d_p2_p4 = math.hypot(p2[0]-p4[0], p2[1]-p4[1])
        corners = [p1, p2, p3, p4] if d_p2_p3 < d_p2_p4 else [p1, p2, p4, p3]
        face = loop_to_face(corners, GIRDER_Z_BASE)
        if face is None: continue
        sld = face.extrude(FreeCAD.Vector(0, 0, GIRDER_HEIGHT))
        shapes.append((f'girder_ln_{girder_count+1}', sld))
        girder_count += 1
        girder_vol += sld.Volume / 1e9
    except Exception:
        pass

print(f"[거더] {girder_count}개 / {girder_vol:.3f} m³")

# PC
pc_count = 0
pc_vol = 0
for pts in pc_polys:
    sld = make_extrusion(pts, PC_Z_BASE, PC_HEIGHT)
    if sld:
        shapes.append((f'pc_{pc_count+1}', sld))
        pc_count += 1
        pc_vol += sld.Volume / 1e9
print(f"[PC] {pc_count}개 / {pc_vol:.3f} m³")

# 벽-기둥 (LWPOLYLINE)
wall_count = 0
wall_vol = 0
for pts in wall_polys:
    sld = make_extrusion(pts, 0, WALL_HEIGHT)
    if sld:
        shapes.append((f'wall_lp_{wall_count+1}', sld))
        wall_count += 1
        wall_vol += sld.Volume / 1e9

# 벽-기둥 (LINE 페어)
for s1, s2 in wall_pairs:
    try:
        p1, p2 = s1; p3, p4 = s2
        d_p2_p3 = math.hypot(p2[0]-p3[0], p2[1]-p3[1])
        d_p2_p4 = math.hypot(p2[0]-p4[0], p2[1]-p4[1])
        corners = [p1, p2, p3, p4] if d_p2_p3 < d_p2_p4 else [p1, p2, p4, p3]
        face = loop_to_face(corners, 0)
        if face is None: continue
        sld = face.extrude(FreeCAD.Vector(0, 0, WALL_HEIGHT))
        shapes.append((f'wall_ln_{wall_count+1}', sld))
        wall_count += 1
        wall_vol += sld.Volume / 1e9
    except Exception:
        pass

print(f"[벽-기둥] {wall_count}개 / {wall_vol:.3f} m³")

# ── 6. 결과 ──────────────────────────────────────────────────
total_vol = slab_vol + girder_vol + pc_vol + wall_vol
print(f"\n{'='*45}")
print(f"102동 지하1층 (102_B1F)")
print(f"{'='*45}")
print(f"  슬라브 : {slab_count:3d}개  {slab_vol:>10.3f} m³")
print(f"  거더   : {girder_count:3d}개  {girder_vol:>10.3f} m³")
print(f"  PC     : {pc_count:3d}개  {pc_vol:>10.3f} m³")
print(f"  벽-기둥: {wall_count:3d}개  {wall_vol:>10.3f} m³")
print(f"{'='*45}")
print(f"  합계   : {len(shapes):3d}개  {total_vol:>10.3f} m³")
print(f"{'='*45}")

os.makedirs("output", exist_ok=True)
if shapes:
    compound = Part.makeCompound([s for _, s in shapes])
    compound.exportStep(OUT_PATH)
    print(f"\n[저장] {OUT_PATH}")
print("완료.")
