"""
DXF → FreeCAD 3D 생성 테스트 v2
101동 기준층 (벽식 구조: 벽체 + 슬라브)

파라미터 (사용자 지정):
  - 모든 벽체 두께: 210mm
  - 슬라브 두께: 210mm
  - 층고: 2830mm

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_dxf_to_freecad.py
"""

import sys
import os
import math

DXF_PATH = "tests/fixtures/free_test.dxf"
OUT_PATH = "output/test_101dong.step"

WALL_THICKNESS = 210
SLAB_THICKNESS = 210
FLOOR_HEIGHT   = 2830
WALL_HEIGHT    = FLOOR_HEIGHT - SLAB_THICKNESS  # 2620 (슬라브 바닥에서 트림)
SLAB_BOTTOM_Z  = WALL_HEIGHT                      # 2620

# ── 1. DXF 파싱 ──────────────────────────────────────────────
import ezdxf
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

wall_lines = []
slab_lines = []

for e in msp.query('LINE'):
    s, ed = e.dxf.start, e.dxf.end
    seg = ((s.x, s.y), (ed.x, ed.y))
    layer = e.dxf.layer
    # 외부참조(XR...) 또는 직접 레이어명 모두 처리
    if layer.endswith('A-WALL-RC') or 'A-WALL-RC' in layer:
        wall_lines.append(seg)
    elif layer == '00_SLAB END + ETC':
        slab_lines.append(seg)

print(f"[DXF] 벽체 라인: {len(wall_lines)}개")
print(f"[DXF] 슬라브 라인: {len(slab_lines)}개")

# 좌표 정규화 기준점
all_pts = [p for s, e in wall_lines + slab_lines for p in [s, e]]
min_x = min(p[0] for p in all_pts)
min_y = min(p[1] for p in all_pts)

def norm(p):
    return (p[0] - min_x, p[1] - min_y)

# ── 2. 슬라브 폴리라인 다중 영역 조립 ─────────────────────────
def assemble_loops(lines, tol=10):
    """모든 닫힌 루프 추출"""
    segments = [(norm(s), norm(e)) for s, e in lines]
    used = [False] * len(segments)
    loops = []

    while True:
        # 시작점 찾기 (사용 안 된 첫 세그먼트)
        start_idx = next((i for i, u in enumerate(used) if not u), None)
        if start_idx is None:
            break

        loop = [segments[start_idx][0], segments[start_idx][1]]
        used[start_idx] = True

        for _ in range(len(segments)):
            last = loop[-1]
            found = False
            for j, seg in enumerate(segments):
                if used[j]:
                    continue
                if abs(seg[0][0] - last[0]) < tol and abs(seg[0][1] - last[1]) < tol:
                    loop.append(seg[1]); used[j] = True; found = True; break
                if abs(seg[1][0] - last[0]) < tol and abs(seg[1][1] - last[1]) < tol:
                    loop.append(seg[0]); used[j] = True; found = True; break
            if not found:
                break
            # 닫혔는지 검사
            if abs(loop[-1][0] - loop[0][0]) < tol and abs(loop[-1][1] - loop[0][1]) < tol:
                break

        if len(loop) >= 4:  # 최소 삼각형
            loops.append(loop)

    return loops

slab_loops = assemble_loops(slab_lines, tol=50)
print(f"[슬라브] 닫힌 루프: {len(slab_loops)}개")
for i, lp in enumerate(slab_loops):
    closed = abs(lp[-1][0]-lp[0][0]) < 50 and abs(lp[-1][1]-lp[0][1]) < 50
    print(f"  루프{i+1}: {len(lp)}점, 닫힘={closed}")

# ── 3. 벽체 라인 페어링 ──────────────────────────────────────
def line_dir_normal(seg):
    (x1, y1), (x2, y2) = seg
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return None, None, 0
    return (dx/L, dy/L), (-dy/L, dx/L), L

def line_distance(s1, s2):
    """평행한 두 선분 사이의 수직 거리"""
    d1, n1, _ = line_dir_normal(s1)
    if d1 is None:
        return float('inf')
    mx1 = (s1[0][0] + s1[1][0]) / 2
    my1 = (s1[0][1] + s1[1][1]) / 2
    mx2 = (s2[0][0] + s2[1][0]) / 2
    my2 = (s2[0][1] + s2[1][1]) / 2
    return abs((mx2 - mx1) * n1[0] + (my2 - my1) * n1[1])

def is_parallel(s1, s2, tol=0.05):
    d1, _, _ = line_dir_normal(s1)
    d2, _, _ = line_dir_normal(s2)
    if d1 is None or d2 is None:
        return False
    cross = abs(d1[0]*d2[1] - d1[1]*d2[0])
    return cross < tol

def overlap_check(s1, s2):
    """평행 두 선분이 어느 정도 겹치는지 (투영 길이)"""
    d1, _, L1 = line_dir_normal(s1)
    if d1 is None:
        return 0
    base = s1[0]
    # s2의 두 끝점을 s1 방향에 투영
    t1 = (s2[0][0] - base[0]) * d1[0] + (s2[0][1] - base[1]) * d1[1]
    t2 = (s2[1][0] - base[0]) * d1[0] + (s2[1][1] - base[1]) * d1[1]
    lo, hi = sorted([t1, t2])
    return max(0, min(L1, hi) - max(0, lo))

print("[벽체] 페어링 시작...")
pair_dist_min = WALL_THICKNESS - 30
pair_dist_max = WALL_THICKNESS + 30

normalized_walls = [(norm(s), norm(e)) for s, e in wall_lines]
used = [False] * len(normalized_walls)
wall_pairs = []

for i in range(len(normalized_walls)):
    if used[i]:
        continue
    s1 = normalized_walls[i]
    _, _, L1 = line_dir_normal(s1)
    if L1 < 100:  # 너무 짧은 선분 제외
        continue

    best_j = -1
    best_overlap = 0
    for j in range(i+1, len(normalized_walls)):
        if used[j]:
            continue
        s2 = normalized_walls[j]
        if not is_parallel(s1, s2):
            continue
        d = line_distance(s1, s2)
        if not (pair_dist_min <= d <= pair_dist_max):
            continue
        ov = overlap_check(s1, s2)
        if ov > best_overlap:
            best_overlap = ov
            best_j = j

    if best_j >= 0 and best_overlap > 100:
        wall_pairs.append((s1, normalized_walls[best_j]))
        used[i] = True
        used[best_j] = True

print(f"[벽체] 페어링 완료: {len(wall_pairs)}개 벽 세그먼트")

# ── 4. FreeCAD 3D 생성 ──────────────────────────────────────
print("\n[FreeCAD] 3D 생성 시작...")
import FreeCAD
import Part

shapes = []
slab_total_vol = 0
wall_total_vol = 0

# 슬라브 생성 (Shapely로 자체교차 자동 수정)
from shapely.geometry import Polygon as ShPoly
from shapely.validation import make_valid

def loop_to_freecad_face(coords, z, tol=1.0):
    """좌표 리스트 → FreeCAD Face (mm). 중복점·영길이 엣지 제거."""
    # 중복 연속점 제거
    cleaned = [coords[0]]
    for p in coords[1:]:
        if abs(p[0] - cleaned[-1][0]) > tol or abs(p[1] - cleaned[-1][1]) > tol:
            cleaned.append(p)
    if abs(cleaned[0][0] - cleaned[-1][0]) > tol or abs(cleaned[0][1] - cleaned[-1][1]) > tol:
        cleaned.append(cleaned[0])

    pts = [FreeCAD.Vector(x, y, z) for x, y in cleaned]
    edges = []
    for k in range(len(pts) - 1):
        if pts[k].distanceToPoint(pts[k+1]) > tol:
            edges.append(Part.makeLine(pts[k], pts[k+1]))
    wire = Part.Wire(edges)
    if not wire.isClosed():
        # 강제 닫기
        edges.append(Part.makeLine(pts[-1], pts[0]))
        wire = Part.Wire(edges)
    return Part.Face(wire)

for i, loop in enumerate(slab_loops):
    try:
        # Shapely로 자체교차 검사 + 수정
        poly = ShPoly(loop)
        if not poly.is_valid:
            fixed = make_valid(poly)
            # 가장 큰 면적의 폴리곤 선택
            if fixed.geom_type == 'MultiPolygon':
                poly = max(fixed.geoms, key=lambda p: p.area)
            elif fixed.geom_type == 'GeometryCollection':
                polys = [g for g in fixed.geoms if g.geom_type == 'Polygon']
                if not polys:
                    print(f"  슬라브{i+1}: 수정 불가, 스킵")
                    continue
                poly = max(polys, key=lambda p: p.area)
            else:
                poly = fixed
            print(f"  슬라브{i+1}: 자체교차 수정됨")

        coords = list(poly.exterior.coords)
        face = loop_to_freecad_face(coords, SLAB_BOTTOM_Z)
        slab = face.extrude(FreeCAD.Vector(0, 0, SLAB_THICKNESS))
        shapes.append((f'slab_{i+1}', slab))
        v = slab.Volume / 1e9
        slab_total_vol += v
        print(f"  슬라브{i+1}: {v:.4f}m³ ({len(coords)-1}점)")
    except Exception as ex:
        print(f"  슬라브{i+1}: 오류 - {ex}")

# 벽체 생성 (페어 사이에 face 만들고 extrude)
for i, (s1, s2) in enumerate(wall_pairs):
    try:
        # s1, s2의 4개 끝점으로 사각형 만들기
        # s2를 뒤집어 연결: s1 시작 → s1 끝 → s2 끝/시작(가까운 쪽) → 다시 s1 시작
        p1, p2 = s1
        p3, p4 = s2

        # p2와 더 가까운 점 찾기
        d_p2_p3 = math.hypot(p2[0]-p3[0], p2[1]-p3[1])
        d_p2_p4 = math.hypot(p2[0]-p4[0], p2[1]-p4[1])
        if d_p2_p3 < d_p2_p4:
            corners = [p1, p2, p3, p4]
        else:
            corners = [p1, p2, p4, p3]

        pts = [FreeCAD.Vector(x, y, 0) for x, y in corners]
        pts.append(pts[0])
        edges = [Part.makeLine(pts[k], pts[k+1]) for k in range(4)]
        wire = Part.Wire(edges)
        if not wire.isClosed():
            continue
        face = Part.Face(wire)
        wall = face.extrude(FreeCAD.Vector(0, 0, WALL_HEIGHT))
        shapes.append((f'wall_{i+1}', wall))
        wall_total_vol += wall.Volume / 1e9
    except Exception as ex:
        pass  # 개별 오류는 무시

print(f"[벽체] 생성 성공: {sum(1 for n,_ in shapes if n.startswith('wall'))}/{len(wall_pairs)}")

# ── 5. 결과 ──────────────────────────────────────────────────
print(f"\n{'='*40}")
print(f"총 형상: {len(shapes)}개")
print(f"  슬라브: {slab_total_vol:.4f} m³")
print(f"  벽체  : {wall_total_vol:.4f} m³")
print(f"  합계  : {slab_total_vol + wall_total_vol:.4f} m³")
print(f"{'='*40}")

# STEP 저장
os.makedirs("output", exist_ok=True)
if shapes:
    compound = Part.makeCompound([s for _, s in shapes])
    compound.exportStep(OUT_PATH)
    print(f"\n[저장] {OUT_PATH}")
else:
    print("[저장] 생성된 형상이 없어 저장하지 않음")
print("완료.")
