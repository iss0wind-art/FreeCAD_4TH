"""
102동 지하1층 v3 — 슬라브 폴리곤 클립 + Boolean fuse 트림 + 자동 공제 BOQ

v2 대비 변경:
1. 슬라브 외곽선 폴리곤 안 부재만 통과 (외톨이 제거)
2. Boolean fuse로 부재 그룹 통합 → 거푸집 공제 자동 산출
3. BOQ 결과 (공제 전/후) 자동 리포트

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_b1f_102_v3_trim_boq.py
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_PATH = "tests/fixtures/102_B1F.dxf"
OUT_PATH = "output/test_102_B1F_v3.step"
BOQ_PATH = "output/boq_102_B1F_v3.md"

GIRDER_HEIGHT = 700
PC_HEIGHT     = 300
SLAB_THICKNESS = 210
FLOOR_HEIGHT  = 4400
SLAB_BOTTOM_Z = FLOOR_HEIGHT - SLAB_THICKNESS
WALL_HEIGHT   = SLAB_BOTTOM_Z
GIRDER_Z_BASE = SLAB_BOTTOM_Z - GIRDER_HEIGHT
PC_Z_BASE     = SLAB_BOTTOM_Z - PC_HEIGHT

from core.patent_c_port import (
    weld_vertices, normalize_to_grid,
    merge_collinear_lines, align_pair_to_rectangle,
)

# ── 1. DXF + 슬라브 폴리라인 ────────────────────────────────
import ezdxf
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

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

print(f"[슬라브] LINE {len(slab_lines)}개, LWPOLYLINE {len(slab_lwpolys)}개")

# 슬라브 폴리곤 조립 → 메인 영역 정의
def assemble_loops(lines, tol=50):
    segments = [list(l) for l in lines]
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

slab_loops_raw = assemble_loops(slab_lines, tol=50)

from shapely.geometry import Polygon as ShPoly, Point as ShPt
from shapely.ops import unary_union
from shapely.validation import make_valid

def safe_polygon(coords):
    poly = ShPoly(coords)
    if not poly.is_valid:
        fixed = make_valid(poly)
        if fixed.geom_type == 'MultiPolygon':
            poly = max(fixed.geoms, key=lambda p: p.area)
        elif fixed.geom_type == 'GeometryCollection':
            polys = [g for g in fixed.geoms if g.geom_type == 'Polygon']
            poly = max(polys, key=lambda p: p.area) if polys else None
        else:
            poly = fixed
    return poly

# 슬라브 폴리곤들 (LINE + LWPOLYLINE 모두) 합집합
slab_polys = []
for loop in slab_loops_raw:
    p = safe_polygon(loop)
    if p and hasattr(p, 'area') and p.area > 5_000_000:  # 5m² 이상만 메인 후보
        slab_polys.append(p)
for pts, _ in slab_lwpolys:
    p = safe_polygon(pts)
    if p and hasattr(p, 'area'):
        slab_polys.append(p)

if not slab_polys:
    raise RuntimeError("슬라브 폴리곤 없음")
clip_region = unary_union(slab_polys)
print(f"[클립] 슬라브 영역 {clip_region.area/1e6:.1f}m² (메인 부재 필터)")

def in_slab(x, y, buffer=500):
    return clip_region.buffer(buffer).contains(ShPt(x, y))

# ── 2. 부재 추출 (슬라브 폴리곤 안만) ───────────────────────
girder_polys = []
girder_lines = []
pc_polys = []
wall_polys = []
wall_lines = []

# 정규화 기준점 = 슬라브 폴리곤 BoundBox
sb = clip_region.bounds  # (minx, miny, maxx, maxy)
norm_x, norm_y = sb[0] - 5000, sb[1] - 5000
def norm(p): return (p[0] - norm_x, p[1] - norm_y)

for ins in msp.query('INSERT'):
    name = ins.dxf.name
    is_girder = ('B1F' in name and 'GIRDER' in name)
    is_pc = ('B1F' in name and 'PC' in name)
    is_wall = ('WALL' in name and 'COL' in name)
    if not (is_girder or is_pc or is_wall):
        continue
    for ent in ins.virtual_entities():
        if ent.dxftype() == 'LWPOLYLINE':
            pts = [(x, y) for x, y, *_ in ent.get_points()]
            if not pts: continue
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            if not in_slab(cx, cy):
                continue
            if is_girder: girder_polys.append(pts)
            elif is_pc: pc_polys.append(pts)
            elif is_wall: wall_polys.append(pts)
        elif ent.dxftype() == 'LINE':
            s, e2 = ent.dxf.start, ent.dxf.end
            mx, my = (s.x+e2.x)/2, (s.y+e2.y)/2
            if not in_slab(mx, my):
                continue
            seg = ((s.x, s.y), (e2.x, e2.y))
            if is_girder: girder_lines.append(seg)
            elif is_wall: wall_lines.append(seg)

for e in msp:
    if e.dxf.layer in ('S-ABW1', 'S-ARW1') and e.dxftype() == 'LWPOLYLINE':
        pts = [(x, y) for x, y, *_ in e.get_points()]
        if not pts: continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        if in_slab(cx, cy):
            wall_polys.append(pts)

print(f"[부재] 거더 폴리 {len(girder_polys)}, LINE {len(girder_lines)}")
print(f"[부재] 벽-기둥 폴리 {len(wall_polys)}, LINE {len(wall_lines)}")
print(f"[부재] PC {len(pc_polys)}")

# ── 3. Patent C 적용 ────────────────────────────────────────
def apply_patent_c(lines, label):
    if not lines: return []
    eps = []
    for s, e in lines: eps += [s, e]
    welded = weld_vertices(eps, tolerance=5.0)
    normalized = normalize_to_grid(welded, tolerance=1.0)
    cleaned = []
    for i in range(0, len(normalized), 2):
        s = normalized[i]; e = normalized[i+1] if i+1 < len(normalized) else None
        if e and (abs(s[0]-e[0]) > 1 or abs(s[1]-e[1]) > 1):
            cleaned.append((s, e))
    merged = merge_collinear_lines(cleaned, angle_tol_deg=1.0, gap_tol=50.0)
    print(f"  [{label}] {len(lines)} → {len(cleaned)} → {len(merged)}")
    return merged

print("[Patent C 적용]")
girder_lines = apply_patent_c(girder_lines, "거더")
wall_lines = apply_patent_c(wall_lines, "벽-기둥")

# 페어링 (이전 함수 재사용)
def line_dir_normal(seg):
    (x1, y1), (x2, y2) = seg
    dx, dy = x2-x1, y2-y1
    L = math.hypot(dx, dy)
    return ((dx/L, dy/L), (-dy/L, dx/L), L) if L > 1e-6 else (None, None, 0)

def is_parallel(s1, s2, tol=0.05):
    d1, _, _ = line_dir_normal(s1); d2, _, _ = line_dir_normal(s2)
    return d1 and d2 and abs(d1[0]*d2[1]-d1[1]*d2[0]) < tol

def line_distance(s1, s2):
    d1, n1, _ = line_dir_normal(s1)
    if not d1: return float('inf')
    mx1=(s1[0][0]+s1[1][0])/2; my1=(s1[0][1]+s1[1][1])/2
    mx2=(s2[0][0]+s2[1][0])/2; my2=(s2[0][1]+s2[1][1])/2
    return abs((mx2-mx1)*n1[0]+(my2-my1)*n1[1])

def overlap_check(s1, s2):
    d1, _, L1 = line_dir_normal(s1)
    if not d1: return 0
    base = s1[0]
    t1=(s2[0][0]-base[0])*d1[0]+(s2[0][1]-base[1])*d1[1]
    t2=(s2[1][0]-base[0])*d1[0]+(s2[1][1]-base[1])*d1[1]
    lo, hi = sorted([t1, t2])
    return max(0, min(L1, hi) - max(0, lo))

def pair_lines(lines, dist_min, dist_max, min_len=200, min_overlap=200):
    used=[False]*len(lines); pairs=[]
    for i in range(len(lines)):
        if used[i]: continue
        s1=lines[i]; _, _, L1 = line_dir_normal(s1)
        if L1 < min_len: continue
        best_j, best_ov = -1, 0
        for j in range(i+1, len(lines)):
            if used[j]: continue
            s2=lines[j]
            if not is_parallel(s1, s2): continue
            d = line_distance(s1, s2)
            if not (dist_min <= d <= dist_max): continue
            ov = overlap_check(s1, s2)
            if ov > best_ov: best_ov=ov; best_j=j
        if best_j >= 0 and best_ov > min_overlap:
            pairs.append((s1, lines[best_j]))
            used[i]=True; used[best_j]=True
    return pairs

norm_wlines = [(norm(s), norm(e)) for s, e in wall_lines]
norm_glines = [(norm(s), norm(e)) for s, e in girder_lines]
wall_pairs = pair_lines(norm_wlines, 150, 400, 150, 100)
girder_pairs = pair_lines(norm_glines, 100, 600, 200, 200)
print(f"[페어링] 벽-기둥 {len(wall_pairs)}, 거더 {len(girder_pairs)}")

# ── 4. FreeCAD 솔리드 생성 ──────────────────────────────────
print("\n[FreeCAD] 3D 생성")
import FreeCAD, Part

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
    poly = safe_polygon(coords)
    if poly is None or not hasattr(poly, 'exterior'): return None
    coords2 = list(poly.exterior.coords)
    face = loop_to_face(coords2, z_base)
    if face is None: return None
    return face.extrude(FreeCAD.Vector(0, 0, height))

shapes_by_type = {'slab': [], 'girder': [], 'pc': [], 'wall': []}

for loop in slab_loops_raw:
    nc = [norm(p) for p in loop]
    sld = make_extrusion(nc, SLAB_BOTTOM_Z, SLAB_THICKNESS)
    if sld: shapes_by_type['slab'].append(sld)
for pts, _ in slab_lwpolys:
    nc = [norm(p) for p in pts]
    sld = make_extrusion(nc, SLAB_BOTTOM_Z, SLAB_THICKNESS)
    if sld: shapes_by_type['slab'].append(sld)

for pts in girder_polys:
    nc = [norm(p) for p in pts]
    sld = make_extrusion(nc, GIRDER_Z_BASE, GIRDER_HEIGHT)
    if sld: shapes_by_type['girder'].append(sld)
for s1, s2 in girder_pairs:
    rect = align_pair_to_rectangle(s1, s2)
    sld = make_extrusion(rect, GIRDER_Z_BASE, GIRDER_HEIGHT)
    if sld: shapes_by_type['girder'].append(sld)

for pts in pc_polys:
    nc = [norm(p) for p in pts]
    sld = make_extrusion(nc, PC_Z_BASE, PC_HEIGHT)
    if sld: shapes_by_type['pc'].append(sld)

for pts in wall_polys:
    nc = [norm(p) for p in pts]
    sld = make_extrusion(nc, 0, WALL_HEIGHT)
    if sld: shapes_by_type['wall'].append(sld)
for s1, s2 in wall_pairs:
    rect = align_pair_to_rectangle(s1, s2)
    sld = make_extrusion(rect, 0, WALL_HEIGHT)
    if sld: shapes_by_type['wall'].append(sld)

for k, v in shapes_by_type.items():
    print(f"  {k}: {len(v)}개")

all_solids = sum(shapes_by_type.values(), [])
print(f"[총] {len(all_solids)}개 솔리드")

# ── 5. ★ Boolean Fuse 트림 + 공제 BOQ ★ ────────────────────
print("\n[트림] Boolean Fuse 시작...")

def vert_area(s):
    a = 0
    for f in s.Faces:
        try:
            n = f.normalAt(0.5, 0.5)
            if abs(n.z) < 0.1: a += f.Area
        except: pass
    return a / 1e6

def down_area(s):
    a = 0
    for f in s.Faces:
        try:
            n = f.normalAt(0.5, 0.5)
            if n.z < -0.9: a += f.Area
        except: pass
    return a / 1e6

# Before — 부재 단순 합산
before = {}
for k, lst in shapes_by_type.items():
    vol = sum(s.Volume for s in lst) / 1e9
    side = sum(vert_area(s) for s in lst)
    bot = sum(down_area(s) for s in lst)
    before[k] = {'vol': vol, 'side': side, 'bot': bot, 'count': len(lst)}

print("[Before] 단순 합산")
for k, v in before.items():
    print(f"  {k}: {v['count']}개 / V={v['vol']:.3f}m³ / 측면={v['side']:.2f}m² / 하면={v['bot']:.2f}m²")

# Fuse — 전체 부재
print("\n[Fuse] 전체 fuse 진행...")
fused = all_solids[0]
fail_count = 0
for i, s in enumerate(all_solids[1:], 1):
    try:
        fused = fused.fuse(s)
    except Exception as ex:
        fail_count += 1
print(f"  통합 면 수: {len(fused.Faces)}, fuse 실패: {fail_count}개")

after_vol = fused.Volume / 1e9
after_side = vert_area(fused)
after_bot = down_area(fused)

# 거푸집 면적 (관행 공식)
# 벽-기둥: 측면만
# 거더: 측면 + 하면
# 슬라브: 하면 + 측면 (둘레)
# PC: 측면 + 하면
form_before = (before['wall']['side']
               + before['girder']['side'] + before['girder']['bot']
               + before['slab']['side'] + before['slab']['bot']
               + before['pc']['side'] + before['pc']['bot'])
form_after = after_side + after_bot

vol_before = sum(v['vol'] for v in before.values())
vol_dedu = vol_before - after_vol
form_dedu = form_before - form_after

# ── 6. BOQ 리포트 ───────────────────────────────────────────
print(f"\n{'='*50}")
print(f"102동 지하1층 — BOQ (자동 공제 적용)")
print(f"{'='*50}")
print(f"콘크리트 체적:")
print(f"  공제 전: {vol_before:>10.3f} m³")
print(f"  공제 후: {after_vol:>10.3f} m³")
print(f"  공제량 : {vol_dedu:>10.3f} m³  ({vol_dedu/vol_before*100:.1f}%)")
print(f"거푸집 면적:")
print(f"  공제 전: {form_before:>10.2f} m²")
print(f"  공제 후: {form_after:>10.2f} m²")
print(f"  공제량 : {form_dedu:>10.2f} m²  ({form_dedu/form_before*100:.1f}%)")
print(f"{'='*50}")

# Markdown BOQ
from datetime import datetime
md = []
md.append(f"# 102동 지하1층 BOQ — 자동 트림 공제 적용\n")
md.append(f"> 산출일시: {datetime.now().isoformat(timespec='seconds')}")
md.append(f"> 도면: 102_B1F.dxf | 적용: Patent C v11.4 + Boolean Fuse 트림\n")
md.append("## 부재별 (공제 전)\n")
md.append("| 부재 | 수량 | 콘크리트(m³) | 측면적(m²) | 하면적(m²) |")
md.append("|------|-----:|-------------:|-----------:|-----------:|")
for k, v in before.items():
    md.append(f"| {k} | {v['count']} | {v['vol']:.3f} | {v['side']:.2f} | {v['bot']:.2f} |")
md.append(f"\n## 자동 공제 결과\n")
md.append(f"| 항목 | 공제 전 | 공제 후 | 공제량 | 공제율 |")
md.append(f"|------|--------:|--------:|-------:|------:|")
md.append(f"| 콘크리트(m³) | {vol_before:.3f} | {after_vol:.3f} | {vol_dedu:.3f} | {vol_dedu/vol_before*100:.1f}% |")
md.append(f"| 거푸집(m²) | {form_before:.2f} | {form_after:.2f} | {form_dedu:.2f} | {form_dedu/form_before*100:.1f}% |")
md.append(f"\n## 산출 기준\n")
md.append(f"- 슬라브 폴리곤 클립으로 외톨이 제거")
md.append(f"- Patent C 청구항 1·4 + Healer.weld_vertices 적용 (라인 정밀도)")
md.append(f"- align_pair_to_rectangle (정사영) 적용 (페어 직각화)")
md.append(f"- Boolean Fuse 전체 통합 → 부재 접촉면 자동 공제")

with open(BOQ_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md))
print(f"\n[BOQ] {BOQ_PATH}")

# STEP 저장 (Fused 결과)
fused.exportStep(OUT_PATH)
print(f"[STEP] {OUT_PATH}")
print("완료.")
