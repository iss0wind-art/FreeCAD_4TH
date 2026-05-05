"""
102동 전체 골조 — 9 도엽 자동 적층

도엽 S30-021~029 각각의 영역에서 부재 추출 → 도엽 번호 순으로 Z축 적층.
사용자가 각 층을 직관적으로 식별 가능.

방부장 친명: 102 B2F 그려라 → 자력 도엽 매핑 막힘 → 전체 적층 후 식별.
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_PATH = r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-021~029-102동 구조평면도.dxf"
OUT_PATH = "output/test_102_full_stack.step"

FLOOR_HEIGHT = 4400  # 표준 층고
SLAB_THICKNESS = 210
WALL_HEIGHT = FLOOR_HEIGHT - SLAB_THICKNESS

import ezdxf
import re

def iter_all(container, depth=0, max_d=8):
    if depth > max_d: return
    for e in container:
        if e.dxftype() == 'INSERT':
            try: yield from iter_all(list(e.virtual_entities()), depth+1, max_d)
            except: pass
        else: yield e

doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

# ── 1. 도엽 위치 식별 ─────────────────────────────────────
sheets = {}
for e in iter_all(msp):
    if e.dxftype() != 'TEXT': continue
    try:
        t = e.dxf.text.strip()
        m = re.match(r'^S30-(\d{3})$', t)
        if m and 21 <= int(m.group(1)) <= 29:
            sheets[t] = (e.dxf.insert.x, e.dxf.insert.y)
    except: pass

print(f"[도엽] {len(sheets)}장")

# 도엽 박스 크기 추정 (인접 도엽 간 거리)
xs = sorted(set(p[0] for p in sheets.values()))
ys = sorted(set(p[1] for p in sheets.values()))
sheet_w = (xs[1] - xs[0]) if len(xs) >= 2 else 126000
sheet_h = (ys[-1] - ys[0]) if len(ys) >= 2 else 178200
print(f"[도엽 박스] 가로≈{sheet_w:.0f}, 세로≈{sheet_h:.0f}")

# 각 도엽 영역 = 표제 좌표 기준 박스
# 가정: 표제는 도엽 박스 좌하단
def sheet_zone(sx, sy):
    return (sx - 5000, sy + 5000, sx + sheet_w, sy + sheet_h)

# ── 2. 도엽별로 부재 추출 ─────────────────────────────────
def extract_sheet_data(sx, sy):
    x0, y0, x1, y1 = sheet_zone(sx, sy)
    slab_lines = []
    wall_lines = []
    for e in iter_all(msp):
        if e.dxftype() != 'LINE': continue
        layer = e.dxf.layer
        s, ed = e.dxf.start, e.dxf.end
        if not (x0 <= s.x <= x1 and y0 <= s.y <= y1): continue
        if 'SLAB' in layer.upper() or 'SLAB END' in layer.upper():
            slab_lines.append(((s.x, s.y), (ed.x, ed.y)))
        elif 'WALL' in layer.upper() or 'A-WALL-RC' in layer:
            wall_lines.append(((s.x, s.y), (ed.x, ed.y)))
    # 슬라브 LWPOLYLINE
    slab_polys = []
    for e in iter_all(msp):
        if e.dxftype() != 'LWPOLYLINE': continue
        layer = e.dxf.layer
        if 'SLAB' not in layer.upper(): continue
        pts = [(x, y) for x, y, *_ in e.get_points()]
        if not pts: continue
        if not (x0 <= pts[0][0] <= x1 and y0 <= pts[0][1] <= y1): continue
        slab_polys.append(pts)
    return slab_lines, wall_lines, slab_polys

# ── 3. FreeCAD 빌드 ──────────────────────────────────────
print("\n[FreeCAD] 빌드 시작")
import FreeCAD, Part
from shapely.geometry import Polygon as ShPoly
from shapely.validation import make_valid

def safe_polygon(coords):
    p = ShPoly(coords)
    if not p.is_valid:
        f = make_valid(p)
        if f.geom_type == 'MultiPolygon': p = max(f.geoms, key=lambda x: x.area)
        elif hasattr(f, 'exterior'): p = f
        else: return None
    return p

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

# 9 도엽 동시 처리 — 도엽 번호로 층 정렬 (가설: 029=옥상, 021=PIT/지하)
sorted_sheets = sorted(sheets.items())
print(f"\n적층 순서: {[s[0] for s in sorted_sheets]}")

shapes = []
for idx, (sheet_id, (sx, sy)) in enumerate(sorted_sheets):
    z_floor = idx * FLOOR_HEIGHT
    print(f"\n[{sheet_id}] Z={z_floor}~{z_floor+FLOOR_HEIGHT}mm")

    slab_lines, wall_lines, slab_polys = extract_sheet_data(sx, sy)
    print(f"  슬라브 LINE {len(slab_lines)}, 폴리 {len(slab_polys)}, 벽 LINE {len(wall_lines)}")

    # 좌표 정규화 — 도엽 좌하단을 (0,0)으로
    def norm(p):
        return (p[0] - sx, p[1] - sy)

    # 슬라브 (LWPOLYLINE 우선)
    slab_count = 0
    slab_z = z_floor + WALL_HEIGHT
    for pts in slab_polys[:50]:  # 도엽당 최대 50개
        nc = [norm(p) for p in pts]
        try:
            poly = safe_polygon(nc)
            if not poly or not hasattr(poly, 'exterior'): continue
            face = loop_to_face(list(poly.exterior.coords), slab_z)
            if face:
                sld = face.extrude(FreeCAD.Vector(0, 0, SLAB_THICKNESS))
                shapes.append((f'{sheet_id}_slab_{slab_count}', sld))
                slab_count += 1
        except: pass

    # 벽 LINE 페어링 (단순)
    wall_count = 0
    used = [False] * len(wall_lines)
    norm_walls = [(norm(s), norm(e)) for s, e in wall_lines]
    for i in range(len(norm_walls)):
        if used[i]: continue
        s1 = norm_walls[i]
        L1 = math.hypot(s1[1][0]-s1[0][0], s1[1][1]-s1[0][1])
        if L1 < 200: continue
        # 평행 가까운 페어
        for j in range(i+1, min(i+30, len(norm_walls))):
            if used[j]: continue
            s2 = norm_walls[j]
            # 수직 거리 추정
            dx = s1[1][0]-s1[0][0]; dy = s1[1][1]-s1[0][1]
            L = math.hypot(dx, dy)
            if L < 1: continue
            nx, ny = -dy/L, dx/L
            mx2 = (s2[0][0]+s2[1][0])/2; my2 = (s2[0][1]+s2[1][1])/2
            mx1 = (s1[0][0]+s1[1][0])/2; my1 = (s1[0][1]+s1[1][1])/2
            d = abs((mx2-mx1)*nx + (my2-my1)*ny)
            if not (150 < d < 400): continue
            # 페어 → 직사각형
            corners = [s1[0], s1[1], s2[1], s2[0]]
            try:
                face = loop_to_face(corners, z_floor)
                if face:
                    sld = face.extrude(FreeCAD.Vector(0, 0, WALL_HEIGHT))
                    shapes.append((f'{sheet_id}_wall_{wall_count}', sld))
                    wall_count += 1
                    used[i] = used[j] = True
                    break
            except: pass
    print(f"  생성: 슬라브 {slab_count}, 벽 {wall_count}")

# 결과
print(f"\n[총] {len(shapes)}개 솔리드")
os.makedirs("output", exist_ok=True)
if shapes:
    compound = Part.makeCompound([s for _, s in shapes])
    compound.exportStep(OUT_PATH)
    print(f"[저장] {OUT_PATH}")
print("완료.")
