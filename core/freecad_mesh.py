"""
FreeCAD Headless Mesh 생성 엔진 (Phase 3)

원칙:
- Part.cut() / Part.intersect() 전면 금지 (3D Boolean 폐기)
- Mesh 모듈만 사용 (비파괴 방식)
- 2D 분할 결과(polygon_clip)를 받아 각 영역 독립 Extrude
- 최종 출력: glTF (Three.js WebGL 뷰어용)

실행 환경: FreeCAD 1.1 내장 Python 3.11
  /c/Program Files/FreeCAD 1.1/bin/python.exe
"""

from __future__ import annotations

import json
import struct
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

# FreeCAD imports (런타임에 FreeCAD Python으로 실행)
try:
    import FreeCAD
    import Part
    import Mesh
    import MeshPart
    FREECAD_AVAILABLE = True
except ImportError:
    FREECAD_AVAILABLE = False


@dataclass
class ExtrudeRegion:
    """독립 Extrude 영역 (2D 분할 결과 한 조각)"""
    region_id: str          # "A_intersection" / "B_remainder"
    vertices_2d: list       # Shapely Polygon의 외곽 좌표 [(x, y), ...]
    height: float           # Extrude 높이 (mm)
    z_base: float           # 시작 Z값 (mm, 기본 0)
    material: str           # "CONCRETE" / "FORMWORK"


@dataclass
class MeshResult:
    """Mesh 생성 결과"""
    region_id: str
    points: list            # [[x, y, z], ...]  (mm 단위)
    facets: list            # [[i, j, k], ...]  삼각형 인덱스
    material: str
    volume_mm3: float
    surface_area_mm2: float


@dataclass
class GltfOutput:
    """glTF 출력 결과"""
    file_path: str
    mesh_count: int
    total_volume_m3: float
    total_surface_area_m2: float


def build_freecad_wire(vertices_2d: list, z_base: float = 0.0) -> "Part.Wire":
    """2D 좌표 목록 → FreeCAD Wire (2D 폴리라인)"""
    if not FREECAD_AVAILABLE:
        raise RuntimeError("FreeCAD not available in current Python environment")

    points = [FreeCAD.Vector(x, y, z_base) for x, y in vertices_2d]
    if points[0] != points[-1]:
        points.append(points[0])  # 닫힌 폴리곤

    edges = [Part.makeLine(points[i], points[i + 1]) for i in range(len(points) - 1)]
    wire = Part.Wire(edges)
    return wire


def extrude_region_to_shape(region: ExtrudeRegion) -> "Part.Shape":
    """
    2D 분할 영역 → 3D Shape (독립 Extrude, Boolean 연산 없음).
    Part.Face → extrude(방향벡터) 방식.
    """
    if not FREECAD_AVAILABLE:
        raise RuntimeError("FreeCAD not available")

    wire = build_freecad_wire(region.vertices_2d, z_base=region.z_base)
    face = Part.Face(wire)
    direction = FreeCAD.Vector(0, 0, region.height)
    shape = face.extrude(direction)
    return shape


def shape_to_mesh(shape: "Part.Shape", linear_deflection: float = 1.0) -> "Mesh.Mesh":
    """Part.Shape → Mesh (삼각형 분할)"""
    if not FREECAD_AVAILABLE:
        raise RuntimeError("FreeCAD not available")
    return MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=linear_deflection,
        AngularDeflection=0.5,
    )


def mesh_to_result(mesh: "Mesh.Mesh", region: ExtrudeRegion) -> MeshResult:
    """FreeCAD Mesh → MeshResult (직렬화 가능 구조)"""
    points = [[p.x, p.y, p.z] for p in mesh.Points]
    facets = [[f.PointIndices[0], f.PointIndices[1], f.PointIndices[2]]
               for f in mesh.Facets]

    # 체적 및 표면적 (FreeCAD Mesh 내장 속성)
    volume_mm3 = mesh.Volume if hasattr(mesh, 'Volume') else 0.0
    area_mm2 = mesh.Area if hasattr(mesh, 'Area') else 0.0

    return MeshResult(
        region_id=region.region_id,
        points=points,
        facets=facets,
        material=region.material,
        volume_mm3=abs(volume_mm3),
        surface_area_mm2=abs(area_mm2),
    )


def extrude_regions(regions: list[ExtrudeRegion]) -> list[MeshResult]:
    """
    2D 분할 영역 목록을 각각 독립 Extrude → Mesh 목록 반환.
    Boolean 연산 없음. 완전히 독립적으로 처리.
    """
    results = []
    for region in regions:
        shape = extrude_region_to_shape(region)
        mesh = shape_to_mesh(shape)
        result = mesh_to_result(mesh, region)
        results.append(result)
    return results


def export_gltf(mesh_results: list[MeshResult], output_path: str) -> GltfOutput:
    """
    MeshResult 목록 → glTF 2.0 파일 (Three.js WebGL 뷰어용).
    pygltflib 사용. mm → m 단위 변환.
    """
    import pygltflib
    from pygltflib import (
        GLTF2, Scene, Node, Mesh as GltfMesh, Primitive,
        Accessor, BufferView, Buffer,
        FLOAT, UNSIGNED_INT, ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER,
    )

    gltf = GLTF2()
    gltf.scene = 0
    gltf.scenes = [Scene(nodes=[])]

    all_binary = b""
    buffer_views = []
    accessors = []
    meshes = []
    nodes = []

    MATERIAL_COLORS = {
        "CONCRETE": [0.6, 0.6, 0.6, 1.0],
        "FORMWORK":  [0.8, 0.5, 0.2, 1.0],
        "CONCRETE_JOINT": [0.3, 0.3, 0.8, 1.0],
    }

    gltf.materials = [
        pygltflib.Material(
            name=mat,
            pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
                baseColorFactor=color,
                metallicFactor=0.0,
                roughnessFactor=0.8,
            )
        )
        for mat, color in MATERIAL_COLORS.items()
    ]
    material_index = {name: i for i, name in enumerate(MATERIAL_COLORS)}

    total_volume_m3 = 0.0
    total_area_m2 = 0.0

    for mesh_r in mesh_results:
        # mm → m 단위 변환
        pts_m = [[x / 1000, y / 1000, z / 1000] for x, y, z in mesh_r.points]
        pts_np = np.array(pts_m, dtype=np.float32)
        idx_np = np.array(mesh_r.facets, dtype=np.uint32).flatten()

        # 바이너리 버퍼 추가
        pts_bytes = pts_np.tobytes()
        idx_bytes = idx_np.tobytes()

        bv_idx = len(buffer_views)
        buffer_views.append(BufferView(
            buffer=0,
            byteOffset=len(all_binary),
            byteLength=len(idx_bytes),
            target=ELEMENT_ARRAY_BUFFER,
        ))
        all_binary += idx_bytes

        # 정렬 패딩 (4바이트)
        if len(all_binary) % 4:
            pad = 4 - (len(all_binary) % 4)
            all_binary += b"\x00" * pad

        bv_pts = len(buffer_views)
        buffer_views.append(BufferView(
            buffer=0,
            byteOffset=len(all_binary),
            byteLength=len(pts_bytes),
            target=ARRAY_BUFFER,
        ))
        all_binary += pts_bytes

        # Accessor 추가
        acc_idx = len(accessors)
        accessors.append(Accessor(
            bufferView=bv_idx,
            componentType=UNSIGNED_INT,
            count=len(idx_np),
            type="SCALAR",
        ))
        acc_pts = len(accessors)
        accessors.append(Accessor(
            bufferView=bv_pts,
            componentType=FLOAT,
            count=len(pts_m),
            type="VEC3",
            max=pts_np.max(axis=0).tolist(),
            min=pts_np.min(axis=0).tolist(),
        ))

        mat_idx = material_index.get(mesh_r.material, 0)
        meshes.append(GltfMesh(
            name=mesh_r.region_id,
            primitives=[Primitive(
                attributes=pygltflib.Attributes(POSITION=acc_pts),
                indices=acc_idx,
                material=mat_idx,
            )]
        ))
        node_idx = len(nodes)
        nodes.append(Node(mesh=node_idx, name=mesh_r.region_id))
        gltf.scenes[0].nodes.append(node_idx)

        total_volume_m3 += mesh_r.volume_mm3 / 1_000_000_000
        total_area_m2 += mesh_r.surface_area_mm2 / 1_000_000

    gltf.bufferViews = buffer_views
    gltf.accessors = accessors
    gltf.meshes = meshes
    gltf.nodes = nodes
    gltf.buffers = [Buffer(
        byteLength=len(all_binary),
        uri="data:application/octet-stream;base64," + base64.b64encode(all_binary).decode(),
    )]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    gltf.save(output_path)

    return GltfOutput(
        file_path=output_path,
        mesh_count=len(mesh_results),
        total_volume_m3=round(total_volume_m3, 6),
        total_surface_area_m2=round(total_area_m2, 4),
    )


def regions_from_clip_result(clip_result, column_height: float, beam_height: float,
                              column_polygon, beam_polygon) -> list[ExtrudeRegion]:
    """
    polygon_clip.JointResult + Shapely 폴리곤 → ExtrudeRegion 목록 생성 헬퍼.
    A영역(교차): beam_height까지 / B영역(잔여): column_height까지 독립 Extrude.
    """
    intersection = column_polygon.intersection(beam_polygon)
    remainder = column_polygon.difference(beam_polygon)

    regions = []

    if not intersection.is_empty:
        coords = list(intersection.exterior.coords)
        regions.append(ExtrudeRegion(
            region_id=f"{clip_result.member_id}_intersection",
            vertices_2d=coords,
            height=beam_height,
            z_base=0.0,
            material="CONCRETE",
        ))

    if not remainder.is_empty:
        # difference 결과가 MultiPolygon일 수 있음
        geoms = list(remainder.geoms) if hasattr(remainder, 'geoms') else [remainder]
        for i, geom in enumerate(geoms):
            coords = list(geom.exterior.coords)
            regions.append(ExtrudeRegion(
                region_id=f"{clip_result.member_id}_remainder_{i}",
                vertices_2d=coords,
                height=column_height,
                z_base=0.0,
                material="CONCRETE",
            ))

    return regions
