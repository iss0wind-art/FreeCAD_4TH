"""
지하주차장 통합 도면 — 2단계: 핵심영역 필터 + 동별 클러스터링

발견:
- 도면 좌표 outlier 다수 (BoundBox 7880×6735m이지만 99.9%가 한 영역)
- 슬라브 closed LWPOLY 5개뿐 — 외곽 LINE 폐합 필요

전략:
1. 콘텐츠 밀집 영역(중앙값 기준 ±n m) 내 엔티티만 필터
2. 슬라브 외곽 LINE을 assemble_loops로 폐합
3. DBSCAN/sklearn으로 부재 중심점 클러스터링 → 동별 그룹
"""

import os, sys, time, math
sys.path.insert(0, r'd:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_PATH = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"

t0 = time.time()
import ezdxf
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()
print(f"[로딩 완료] {time.time()-t0:.1f}초")

# ── 1. 콘텐츠 밀집 영역 식별 (중앙값 기준) ──────────────────
all_cx, all_cy = [], []
for e in msp:
    if e.dxftype() != 'LINE': continue
    cx = (e.dxf.start.x + e.dxf.end.x) / 2
    cy = (e.dxf.start.y + e.dxf.end.y) / 2
    all_cx.append(cx); all_cy.append(cy)

import statistics
mx, my = statistics.median(all_cx), statistics.median(all_cy)
print(f"[중앙값] X={mx:.0f}, Y={my:.0f}")

# 중앙값 ±2km 내 핵심 영역
RADIUS = 2_500_000  # 2.5 km in mm (도면 단위)
core_minx, core_maxx = mx - RADIUS, mx + RADIUS
core_miny, core_maxy = my - RADIUS, my + RADIUS

def in_core(x, y):
    return core_minx <= x <= core_maxx and core_miny <= y <= core_maxy

# ── 2. 핵심 영역 LINE 통계 (레이어별) ────────────────────────
from collections import Counter
core_lines_by_layer = {}
core_count = 0
total_count = 0
for e in msp:
    if e.dxftype() != 'LINE': continue
    total_count += 1
    cx = (e.dxf.start.x + e.dxf.end.x) / 2
    cy = (e.dxf.start.y + e.dxf.end.y) / 2
    if not in_core(cx, cy): continue
    core_count += 1
    layer = e.dxf.layer
    if layer not in core_lines_by_layer:
        core_lines_by_layer[layer] = []
    core_lines_by_layer[layer].append(((e.dxf.start.x, e.dxf.start.y),
                                        (e.dxf.end.x, e.dxf.end.y)))

print(f"\n[핵심영역 필터] {core_count}/{total_count} LINE ({core_count/total_count*100:.1f}%)")
for layer in ['00_UNDER ELEMENT', '00_SHEAR WALL', '00_COLUMN', '00_BEAM',
              '00_(APT)BEAM', '00_SLAB END + ETC']:
    n = len(core_lines_by_layer.get(layer, []))
    print(f"  {layer:30s}: {n}")

# ── 3. 슬라브 외곽 LINE 폐합 시도 ────────────────────────────
slab_lines = core_lines_by_layer.get('00_SLAB END + ETC', [])
print(f"\n[슬라브 외곽] LINE {len(slab_lines)}개")

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

t1 = time.time()
slab_loops_raw = assemble_loops(slab_lines, tol=200)
print(f"[폐합] {len(slab_loops_raw)}개 loop, {time.time()-t1:.1f}초")

from shapely.geometry import Polygon as ShPoly, MultiPoint
from shapely.ops import unary_union
from shapely.validation import make_valid

def safe_polygon(coords):
    try:
        poly = ShPoly(coords)
        if not poly.is_valid:
            fixed = make_valid(poly)
            if hasattr(fixed, 'geoms'):
                polys = [g for g in fixed.geoms if g.geom_type == 'Polygon']
                poly = max(polys, key=lambda p: p.area) if polys else None
            else:
                poly = fixed if fixed.geom_type == 'Polygon' else None
        return poly
    except: return None

slab_polys = []
for loop in slab_loops_raw:
    p = safe_polygon(loop)
    if p and hasattr(p, 'area') and p.area > 50_000_000:  # 50 m² 이상
        slab_polys.append(p)

# Closed LWPOLYLINE도 추가
for e in msp:
    if e.dxf.layer != '00_SLAB END + ETC' or e.dxftype() != 'LWPOLYLINE':
        continue
    try:
        pts = [(x, y) for x, y, *_ in e.get_points()]
        if not pts: continue
        cx = sum(p[0] for p in pts)/len(pts)
        cy = sum(p[1] for p in pts)/len(pts)
        if not in_core(cx, cy): continue
        p = safe_polygon(pts)
        if p and hasattr(p, 'area') and p.area > 50_000_000:
            slab_polys.append(p)
    except: pass

print(f"[유효 슬라브 폴리곤(50m²+)] {len(slab_polys)}개")
slab_polys.sort(key=lambda p: -p.area)
print(f"[상위 15개]")
for i, p in enumerate(slab_polys[:15]):
    cx, cy = p.centroid.x, p.centroid.y
    print(f"  #{i+1}: {p.area/1e6:8.1f} m²  중심 ({cx:.0f}, {cy:.0f})")

# ── 4. 기둥 중심점으로 동별 클러스터링 ──────────────────────
print(f"\n[기둥 중심점 클러스터링]")
column_lines = core_lines_by_layer.get('00_COLUMN', [])
column_centers = []
for s, e in column_lines:
    cx = (s[0]+e[0])/2; cy = (s[1]+e[1])/2
    column_centers.append((cx, cy))

print(f"  기둥 LINE 중심점 {len(column_centers)}개")

# DBSCAN 시도 (sklearn 없이 수동 grid binning)
GRID = 30_000  # 30 m grid
grid_count = Counter()
for cx, cy in column_centers:
    gx = int(cx // GRID); gy = int(cy // GRID)
    grid_count[(gx, gy)] += 1

# Connected component
print(f"  30m 그리드 셀 수: {len(grid_count)}")
dense_cells = [(g, c) for g, c in grid_count.items() if c >= 5]
print(f"  밀집 셀(5+): {len(dense_cells)}")

# 4-neighbor BFS clustering
visited = set()
clusters = []
dense_set = {g for g, _ in dense_cells}
for cell in dense_set:
    if cell in visited: continue
    stack = [cell]; cluster = []
    while stack:
        c = stack.pop()
        if c in visited: continue
        visited.add(c); cluster.append(c)
        gx, gy = c
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0: continue
                n = (gx+dx, gy+dy)
                if n in dense_set and n not in visited:
                    stack.append(n)
    if len(cluster) >= 3:
        clusters.append(cluster)

clusters.sort(key=lambda c: -len(c))
print(f"  클러스터 수(셀 3+): {len(clusters)}")
for i, cluster in enumerate(clusters[:20]):
    xs = [g[0]*GRID + GRID/2 for g in cluster]
    ys = [g[1]*GRID + GRID/2 for g in cluster]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    cx = (minx+maxx)/2; cy = (miny+maxy)/2
    n_cols = sum(grid_count[g] for g in cluster)
    print(f"  #{i+1}: {len(cluster)}셀 / {n_cols}기둥 / 중심({cx:.0f},{cy:.0f}) / {(maxx-minx)/1000:.0f}×{(maxy-miny)/1000:.0f}m")

# ── 5. 시범 영역 후보 결정 ───────────────────────────────────
# 가장 큰 슬라브 폴리곤을 시범 영역으로
if slab_polys:
    target = slab_polys[0]
    cx, cy = target.centroid.x, target.centroid.y
    minx, miny, maxx, maxy = target.bounds
    print(f"\n[시범 영역 선택] 가장 큰 슬라브 폴리곤")
    print(f"  면적: {target.area/1e6:.1f} m²")
    print(f"  BoundBox: X {minx:.0f}~{maxx:.0f} ({(maxx-minx)/1000:.1f}m)")
    print(f"            Y {miny:.0f}~{maxy:.0f} ({(maxy-miny)/1000:.1f}m)")
    print(f"  중심: ({cx:.0f}, {cy:.0f})")

# 그러나 슬라브 폴리곤이 작을 수 있음. 클러스터 #1을 시범 영역으로 권장
if clusters:
    cluster1 = clusters[0]
    xs = [g[0]*GRID + GRID/2 for g in cluster1]
    ys = [g[1]*GRID + GRID/2 for g in cluster1]
    c1_minx = min(xs) - GRID; c1_maxx = max(xs) + GRID
    c1_miny = min(ys) - GRID; c1_maxy = max(ys) + GRID
    print(f"\n[시범 영역 후보] 클러스터 #1 (가장 많은 기둥)")
    print(f"  BoundBox: X {c1_minx:.0f}~{c1_maxx:.0f} ({(c1_maxx-c1_minx)/1000:.1f}m)")
    print(f"            Y {c1_miny:.0f}~{c1_maxy:.0f} ({(c1_maxy-c1_miny)/1000:.1f}m)")

print(f"\n[총] {time.time()-t0:.1f}초")
