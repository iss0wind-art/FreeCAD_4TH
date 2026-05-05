"""
지하주차장 단지 마스터 모델 — 16동
- 동별 외곽선 + 지하층수(B1/B2)에 따른 높이
- 출력: STEP, glTF (Three.js WebGL용), JSON 메타데이터

층 구성:
- B2 동 (9개): Z=0~4400(B2) + 4400~8800(B1) → 두 박스로 분리
- B1 동 (7개): Z=0~4400(B1) → 한 박스
"""

import os, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_PATH = "tests/fixtures/새 블럭.dxf"
OUT_STEP = "output/complex_master.step"
OUT_GLB  = "output/complex_master.glb"
OUT_JSON = "output/complex_master.json"

B1_HEIGHT = 5600  # 지하1층 층고
B2_HEIGHT = 3850  # 지하2층 층고
# 지하1층 슬라브 상부 = GL = 0 (모든 동 윗면 정렬)
B1_TOP_Z    = 0
B1_BOTTOM_Z = B1_TOP_Z - B1_HEIGHT       # -5600
B2_BOTTOM_Z = B1_BOTTOM_Z - B2_HEIGHT    # -9450

B2_DONGS = {101, 102, 103, 104, 105, 106, 109, 110, 111}
B1_DONGS = {107, 108, 112, 113, 114, 115, 116}

# ── 1. DXF 파싱 (모델스페이스 + INSERT 블록 explode) ────────
import ezdxf
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

def iter_all_entities(container, depth=0, max_depth=10):
    """중첩 블록까지 재귀 explode"""
    if depth > max_depth:
        return
    for e in container:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all_entities(list(e.virtual_entities()), depth+1, max_depth)
            except Exception:
                pass
        else:
            yield e

# 동 텍스트 위치
dong_anchors = {}
for e in iter_all_entities(msp):
    if e.dxftype() != 'TEXT':
        continue
    if getattr(e.dxf, 'layer', '') != 'A-TEXT-3.0':
        continue
    text = e.dxf.text.strip()
    digits = ''.join(c for c in text if c.isdigit())
    if digits:
        n = int(digits)
        if 100 <= n <= 200:
            dong_anchors[n] = (e.dxf.insert.x, e.dxf.insert.y)

print(f"[동 라벨] {len(dong_anchors)}개 발견: {sorted(dong_anchors.keys())}")

# 모든 폴리라인
polys = []
for e in iter_all_entities(msp):
    if e.dxftype() != 'LWPOLYLINE':
        continue
    pts = [(x, y) for x, y, *_ in e.get_points()]
    if len(pts) >= 3:
        polys.append((pts, e.is_closed))
print(f"[폴리라인] {len(polys)}개")

# ── 2. 폴리라인 → 가까운 동에 할당 ──────────────────────────
def poly_centroid(pts):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return cx, cy

def poly_area(pts):
    n = len(pts)
    a = 0
    for i in range(n):
        j = (i + 1) % n
        a += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(a) / 2

# 1:1 매칭 (그리디) — 거리 짧은 것부터
candidates = []
for pi, (pts, closed) in enumerate(polys):
    cx, cy = poly_centroid(pts)
    area = poly_area(pts)
    if area < 100_000:  # 100m² 미만은 동 외곽이 아닐 가능성
        continue
    for n, (ax, ay) in dong_anchors.items():
        d = (cx - ax) ** 2 + (cy - ay) ** 2
        candidates.append((d, n, pi))
candidates.sort()

assigned_dong = set()
assigned_poly = set()
dong_outline = {}
for d, n, pi in candidates:
    if n in assigned_dong or pi in assigned_poly:
        continue
    assigned_dong.add(n); assigned_poly.add(pi)
    dong_outline[n] = polys[pi][0]
    print(f"  동 {n}: 폴리 #{pi} (면적 {poly_area(polys[pi][0])/1e6:.1f}m², 거리 {d**0.5:.0f}mm)")

missing = set(dong_anchors.keys()) - assigned_dong
if missing:
    print(f"  ⚠ 매칭 실패: {sorted(missing)}")

# ── 3. FreeCAD에서 extrude + STEP/GLTF/JSON ────────────────
print("\n[FreeCAD] 단지 모델 생성")
import FreeCAD
import Part
from shapely.geometry import Polygon as ShPoly
from shapely.validation import make_valid

# 좌표 정규화
all_pts = [p for pts in dong_outline.values() for p in pts]
min_x = min(p[0] for p in all_pts)
min_y = min(p[1] for p in all_pts)
def norm(p): return (p[0] - min_x, p[1] - min_y)

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

def extrude_poly(coords, z_base, height):
    norm_coords = [norm(p) for p in coords]
    poly = ShPoly(norm_coords)
    if not poly.is_valid:
        fixed = make_valid(poly)
        if fixed.geom_type == 'MultiPolygon':
            poly = max(fixed.geoms, key=lambda p: p.area)
        elif fixed.geom_type == 'GeometryCollection':
            polys2 = [g for g in fixed.geoms if g.geom_type == 'Polygon']
            if not polys2: return None
            poly = max(polys2, key=lambda p: p.area)
        else:
            poly = fixed
    if not hasattr(poly, 'exterior'): return None
    coords2 = list(poly.exterior.coords)
    face = loop_to_face(coords2, z_base)
    if face is None: return None
    return face.extrude(FreeCAD.Vector(0, 0, height))

# 동별 솔리드 생성
shapes = []  # [(label, solid)]
metadata = {"complex_name": "단지 마스터플랜", "buildings": []}

for n in sorted(dong_outline.keys()):
    coords = dong_outline[n]
    area = poly_area(coords) / 1e6  # m²
    if n in B2_DONGS:
        # 지하2층(아래 3850) + 지하1층(위 5600) — 윗면이 Z=0
        b2 = extrude_poly(coords, B2_BOTTOM_Z, B2_HEIGHT)
        b1 = extrude_poly(coords, B1_BOTTOM_Z, B1_HEIGHT)
        if b2: shapes.append((f"D{n}_B2", b2))
        if b1: shapes.append((f"D{n}_B1", b1))
        metadata["buildings"].append({
            "dong": n, "underground_floors": 2,
            "footprint_area_m2": round(area, 1),
            "concrete_volume_m3": round(area * (B1_HEIGHT + B2_HEIGHT) / 1000, 1),
            "status": "pending",
            "color_hex": "#cccccc"
        })
    elif n in B1_DONGS:
        # 지하1층만 5600 — 윗면이 Z=0
        b1 = extrude_poly(coords, B1_BOTTOM_Z, B1_HEIGHT)
        if b1: shapes.append((f"D{n}_B1", b1))
        metadata["buildings"].append({
            "dong": n, "underground_floors": 1,
            "footprint_area_m2": round(area, 1),
            "concrete_volume_m3": round(area * B1_HEIGHT / 1000, 1),
            "status": "pending",
            "color_hex": "#cccccc"
        })

print(f"[솔리드] {len(shapes)}개 생성")

# ── 3b. 동 번호 텍스트 솔리드 (윗면에 마킹) ─────────────────
FONT_PATH = "C:/Windows/Fonts/malgun.ttf"  # 한글 지원 폰트
TEXT_HEIGHT = 200    # 글자 두께 200mm (도드라짐)

def text_solids(text, cx, cy, z, font_size):
    """텍스트 → 3D 솔리드 리스트"""
    try:
        wires = Part.makeWireString(text, FONT_PATH, font_size)
    except Exception as ex:
        print(f"  텍스트 '{text}' 와이어 실패: {ex}")
        return []
    solids = []
    # 글자 폭 추정용 (글자 수 × 폰트크기 × 0.6)
    text_width = len(text) * font_size * 0.6
    offset_x = cx - text_width / 2
    offset_y = cy - font_size / 2
    for char_wires in wires:
        if not char_wires:
            continue
        # 외곽 와이어 + 내부 구멍 와이어 (Face의 holes)
        try:
            outer = char_wires[0]
            holes = char_wires[1:] if len(char_wires) > 1 else []
            face = Part.Face([outer] + list(holes))
            solid = face.extrude(FreeCAD.Vector(0, 0, TEXT_HEIGHT))
            solid.translate(FreeCAD.Vector(offset_x, offset_y, z))
            solids.append(solid)
        except Exception:
            try:
                # fallback: 첫 와이어만
                face = Part.Face(char_wires[0])
                solid = face.extrude(FreeCAD.Vector(0, 0, TEXT_HEIGHT))
                solid.translate(FreeCAD.Vector(offset_x, offset_y, z))
                solids.append(solid)
            except Exception:
                pass
    return solids

text_count = 0
for n in sorted(dong_outline.keys()):
    coords = [norm(p) for p in dong_outline[n]]
    cx = sum(p[0] for p in coords) / len(coords)
    cy = sum(p[1] for p in coords) / len(coords)
    xs = [p[0] for p in coords]; ys = [p[1] for p in coords]
    short_side = min(max(xs)-min(xs), max(ys)-min(ys))
    font_size = max(min(short_side / 4, 4000), 1200)
    underground = "B2" if n in B2_DONGS else "B1"
    label_text = f"{n}동 ({underground})"
    label_solids = text_solids(label_text, cx, cy, B1_TOP_Z, font_size)
    for i, s in enumerate(label_solids):
        shapes.append((f"L{n}_{i}", s))
        text_count += 1

print(f"[텍스트] 동 번호+층수 마킹 {text_count}개 추가")

# ── 4. STEP 출력 ───────────────────────────────────────────
os.makedirs("output", exist_ok=True)
compound = Part.makeCompound([s for _, s in shapes])
compound.exportStep(OUT_STEP)
print(f"[저장] {OUT_STEP}")

# ── 5. glTF 출력 (Three.js용, 동마다 노드 분리) ─────────────
import MeshPart
import numpy as np
import base64
import pygltflib
from pygltflib import (GLTF2, Scene, Node, Mesh as GMesh, Primitive,
                       Accessor, BufferView, Buffer,
                       FLOAT, UNSIGNED_INT, ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER)

gltf = GLTF2()
gltf.scene = 0
gltf.scenes = [Scene(nodes=[])]
binary = b""
buffer_views = []
accessors = []
meshes = []
nodes = []

# 머터리얼: 미작업(회색), 현재(노랑), 완료(초록)
gltf.materials = [
    pygltflib.Material(name="pending",
        pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
            baseColorFactor=[0.80, 0.80, 0.80, 1.0],
            metallicFactor=0.0, roughnessFactor=0.8)),
    pygltflib.Material(name="current",
        pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
            baseColorFactor=[0.95, 0.85, 0.20, 1.0],
            metallicFactor=0.0, roughnessFactor=0.6)),
    pygltflib.Material(name="completed",
        pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
            baseColorFactor=[0.50, 0.85, 0.50, 1.0],
            metallicFactor=0.0, roughnessFactor=0.7)),
]

for label, solid in shapes:
    mesh_obj = MeshPart.meshFromShape(Shape=solid, LinearDeflection=10.0, AngularDeflection=0.5)
    pts = np.array([[p.x/1000, p.y/1000, p.z/1000] for p in mesh_obj.Points], dtype=np.float32)
    idx = np.array([[f.PointIndices[0], f.PointIndices[1], f.PointIndices[2]] for f in mesh_obj.Facets], dtype=np.uint32).flatten()

    pts_bytes = pts.tobytes()
    idx_bytes = idx.tobytes()

    bv_i = len(buffer_views)
    buffer_views.append(BufferView(buffer=0, byteOffset=len(binary),
                                    byteLength=len(idx_bytes), target=ELEMENT_ARRAY_BUFFER))
    binary += idx_bytes
    if len(binary) % 4:
        binary += b"\x00" * (4 - len(binary) % 4)

    bv_p = len(buffer_views)
    buffer_views.append(BufferView(buffer=0, byteOffset=len(binary),
                                    byteLength=len(pts_bytes), target=ARRAY_BUFFER))
    binary += pts_bytes

    a_i = len(accessors)
    accessors.append(Accessor(bufferView=bv_i, componentType=UNSIGNED_INT, count=len(idx), type="SCALAR"))
    a_p = len(accessors)
    accessors.append(Accessor(bufferView=bv_p, componentType=FLOAT, count=len(pts),
                              type="VEC3", max=pts.max(axis=0).tolist(), min=pts.min(axis=0).tolist()))

    meshes.append(GMesh(name=label,
        primitives=[Primitive(attributes=pygltflib.Attributes(POSITION=a_p),
                              indices=a_i, material=0)]))
    node = Node(mesh=len(meshes)-1, name=label)
    node.extras = {"label": label}
    nodes.append(node)
    gltf.scenes[0].nodes.append(len(nodes)-1)

gltf.bufferViews = buffer_views
gltf.accessors = accessors
gltf.meshes = meshes
gltf.nodes = nodes
# GLB 단일 바이너리 패키징 (uri 없이 binary blob 사용)
gltf.buffers = [Buffer(byteLength=len(binary))]
gltf.set_binary_blob(binary)
gltf.save(OUT_GLB)  # .glb 확장자 자동 인식
print(f"[저장] {OUT_GLB}")

# ── 6. JSON 메타데이터 ─────────────────────────────────────
with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)
print(f"[저장] {OUT_JSON}")

# 요약
total_area = sum(b["footprint_area_m2"] for b in metadata["buildings"])
total_vol  = sum(b["concrete_volume_m3"] for b in metadata["buildings"])
print(f"\n{'='*45}")
print(f"단지 마스터플랜")
print(f"{'='*45}")
print(f"  총 동수    : {len(metadata['buildings'])}개")
print(f"  B2 동      : {sum(1 for b in metadata['buildings'] if b['underground_floors']==2)}개")
print(f"  B1 동      : {sum(1 for b in metadata['buildings'] if b['underground_floors']==1)}개")
print(f"  총 부지면적: {total_area:,.1f} m²")
print(f"  추정 체적  : {total_vol:,.1f} m³")
print(f"{'='*45}")
print("완료.")
