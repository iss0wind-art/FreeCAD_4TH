"""
FreeCAD Headless Mesh 생성 + glTF 출력 테스트 (Phase 3)

실행 환경: FreeCAD 내장 Python
  /c/Program Files/FreeCAD 1.1/bin/python.exe -m pytest tests/test_freecad_mesh.py -v

검증 항목:
- ExtrudeRegion 독립 Extrude (Boolean 없음)
- Mesh 포인트/패싯 정확도
- glTF 파일 생성 및 구조 검증
- polygon_clip 연계 파이프라인
"""

import pytest
import json
import os
from pathlib import Path
from shapely.geometry import box

from core.freecad_mesh import (
    ExtrudeRegion,
    MeshResult,
    GltfOutput,
    extrude_regions,
    export_gltf,
    regions_from_clip_result,
    FREECAD_AVAILABLE,
)
from core.polygon_clip import (
    ColumnProfile,
    BeamProfile,
    compute_column_beam_joint,
)

# FreeCAD 없으면 해당 테스트 스킵
freecad_only = pytest.mark.skipif(
    not FREECAD_AVAILABLE,
    reason="FreeCAD Python 환경에서만 실행 (freecad/bin/python.exe)"
)

OUTPUT_DIR = Path("tests/output")


@pytest.fixture(autouse=True)
def ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────
# ExtrudeRegion 데이터 구조 테스트
# (FreeCAD 불필요 - 순수 Python)
# ─────────────────────────────────────

class TestExtrudeRegion:
    def test_region_fields_required(self):
        """필수 필드 구비 확인"""
        region = ExtrudeRegion(
            region_id="TEST",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=3000.0,
            z_base=0.0,
            material="CONCRETE",
        )
        assert region.region_id == "TEST"
        assert region.height == 3000.0
        assert region.material == "CONCRETE"

    def test_region_vertices_count(self):
        """사각형 기둥: 4개 꼭짓점"""
        region = ExtrudeRegion(
            region_id="C1",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=3000.0, z_base=0.0, material="CONCRETE",
        )
        assert len(region.vertices_2d) == 4


# ─────────────────────────────────────
# FreeCAD Mesh 생성 테스트
# ─────────────────────────────────────

class TestExtrudeRegions:
    @freecad_only
    def test_single_box_region_creates_mesh(self):
        """600×600mm 기둥 단면 → Mesh 생성 확인"""
        region = ExtrudeRegion(
            region_id="C1_full",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=3000.0, z_base=0.0, material="CONCRETE",
        )
        results = extrude_regions([region])
        assert len(results) == 1
        mesh_r = results[0]
        assert mesh_r.region_id == "C1_full"
        assert len(mesh_r.points) > 0
        assert len(mesh_r.facets) > 0

    @freecad_only
    def test_mesh_facets_are_triangles(self):
        """모든 패싯은 삼각형 (인덱스 3개)"""
        region = ExtrudeRegion(
            region_id="BOX",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=1000.0, z_base=0.0, material="CONCRETE",
        )
        results = extrude_regions([region])
        for facet in results[0].facets:
            assert len(facet) == 3

    @freecad_only
    def test_two_independent_regions_no_boolean(self):
        """
        2개 영역 독립 Extrude → 각각 Mesh 생성.
        Boolean 연산 없이 두 결과가 독립적으로 존재해야 함.
        """
        region_A = ExtrudeRegion(
            region_id="A_intersection",
            vertices_2d=[(-300, -150), (300, -150), (300, 150), (-300, 150)],
            height=500.0, z_base=0.0, material="CONCRETE",
        )
        region_B_top = ExtrudeRegion(
            region_id="B_remainder",
            vertices_2d=[(-300, 150), (300, 150), (300, 300), (-300, 300)],
            height=3000.0, z_base=0.0, material="CONCRETE",
        )
        results = extrude_regions([region_A, region_B_top])
        assert len(results) == 2
        assert results[0].region_id == "A_intersection"
        assert results[1].region_id == "B_remainder"

    @freecad_only
    def test_volume_approximation(self):
        """
        600×600×3000mm 박스의 Mesh 체적이 이론값에 근사.
        이론값: 1,080,000,000 mm³ (허용 오차 5%)
        """
        region = ExtrudeRegion(
            region_id="COL",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=3000.0, z_base=0.0, material="CONCRETE",
        )
        results = extrude_regions([region])
        expected_mm3 = 600 * 600 * 3000  # 1,080,000,000
        assert results[0].volume_mm3 == pytest.approx(expected_mm3, rel=0.05)

    @freecad_only
    def test_material_preserved_in_result(self):
        """입력 material이 MeshResult에 그대로 보존됨"""
        region = ExtrudeRegion(
            region_id="FM",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=3000.0, z_base=0.0, material="FORMWORK",
        )
        results = extrude_regions([region])
        assert results[0].material == "FORMWORK"


# ─────────────────────────────────────
# glTF 출력 테스트
# ─────────────────────────────────────

class TestExportGltf:
    @freecad_only
    def test_gltf_file_created(self):
        """glTF 파일이 지정 경로에 생성됨"""
        region = ExtrudeRegion(
            region_id="GLTF_TEST",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=3000.0, z_base=0.0, material="CONCRETE",
        )
        mesh_results = extrude_regions([region])
        output_path = str(OUTPUT_DIR / "test_column.gltf")
        result = export_gltf(mesh_results, output_path)
        assert Path(output_path).exists()
        assert result.mesh_count == 1

    @freecad_only
    def test_gltf_valid_json(self):
        """생성된 glTF가 유효한 JSON 구조"""
        region = ExtrudeRegion(
            region_id="JSON_TEST",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=1000.0, z_base=0.0, material="CONCRETE",
        )
        mesh_results = extrude_regions([region])
        output_path = str(OUTPUT_DIR / "test_json.gltf")
        export_gltf(mesh_results, output_path)

        with open(output_path, "r") as f:
            data = json.load(f)
        assert "asset" in data
        assert "meshes" in data
        assert "nodes" in data
        assert "buffers" in data

    @freecad_only
    def test_gltf_volume_reported(self):
        """GltfOutput에 총 체적이 기록됨 (m³ 단위)"""
        region = ExtrudeRegion(
            region_id="VOL_TEST",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=3000.0, z_base=0.0, material="CONCRETE",
        )
        mesh_results = extrude_regions([region])
        output_path = str(OUTPUT_DIR / "test_vol.gltf")
        result = export_gltf(mesh_results, output_path)

        expected_m3 = 600 * 600 * 3000 / 1_000_000_000  # 1.08
        assert result.total_volume_m3 == pytest.approx(expected_m3, rel=0.05)

    @freecad_only
    def test_gltf_multi_mesh(self):
        """복수 Mesh → 단일 glTF에 통합"""
        regions = [
            ExtrudeRegion("R1", [(-300, -150), (300, -150), (300, 150), (-300, 150)],
                          500.0, 0.0, "CONCRETE"),
            ExtrudeRegion("R2", [(-300, 150), (300, 150), (300, 300), (-300, 300)],
                          3000.0, 0.0, "CONCRETE"),
        ]
        mesh_results = extrude_regions(regions)
        output_path = str(OUTPUT_DIR / "test_multi.gltf")
        result = export_gltf(mesh_results, output_path)
        assert result.mesh_count == 2
        assert result.total_volume_m3 > 0

    @freecad_only
    def test_gltf_coordinates_in_meters(self):
        """glTF 내부 좌표가 m 단위 (max < 1.0 for 600mm)"""
        region = ExtrudeRegion(
            region_id="UNIT_TEST",
            vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
            height=3000.0, z_base=0.0, material="CONCRETE",
        )
        mesh_results = extrude_regions([region])
        output_path = str(OUTPUT_DIR / "test_units.gltf")
        export_gltf(mesh_results, output_path)

        with open(output_path, "r") as f:
            data = json.load(f)
        # Position accessor의 max 값이 m 단위여야 함 (600mm = 0.6m)
        pos_accessor = next(
            a for a in data["accessors"]
            if a.get("type") == "VEC3" and "max" in a
        )
        assert pos_accessor["max"][0] <= 1.0  # 600mm = 0.6m < 1.0m


# ─────────────────────────────────────
# polygon_clip → freecad_mesh 파이프라인 통합 테스트
# ─────────────────────────────────────

class TestPipelineIntegration:
    @freecad_only
    def test_clip_to_gltf_pipeline(self):
        """
        전체 파이프라인: 2D 분할 → FreeCAD Extrude → glTF 출력.
        기둥(600×600) + 보(300mm 폭) → 순체적 0.63m³ 근사.
        """
        col_poly = box(-300, -300, 300, 300)
        beam_poly = box(-1000, -150, 1000, 150)

        col = ColumnProfile(polygon=col_poly, height=3000.0, member_id="C1")
        beam = BeamProfile(polygon=beam_poly, height=500.0, member_id="B1")
        clip_result = compute_column_beam_joint(col, beam)

        regions = regions_from_clip_result(
            clip_result,
            column_height=3000.0,
            beam_height=500.0,
            column_polygon=col_poly,
            beam_polygon=beam_poly,
        )
        assert len(regions) >= 2  # A(교차) + B(잔여) 최소 2개

        mesh_results = extrude_regions(regions)
        output_path = str(OUTPUT_DIR / "pipeline_test.gltf")
        gltf_out = export_gltf(mesh_results, output_path)

        # 이론 체적 0.63m³에 5% 이내
        assert gltf_out.total_volume_m3 == pytest.approx(0.63, rel=0.05)
        assert Path(output_path).exists()

    @freecad_only
    def test_regions_from_clip_result_structure(self):
        """regions_from_clip_result 반환값 구조 검증"""
        col_poly = box(-300, -300, 300, 300)
        beam_poly = box(-1000, -150, 1000, 150)
        col = ColumnProfile(polygon=col_poly, height=3000.0, member_id="C1")
        beam = BeamProfile(polygon=beam_poly, height=500.0, member_id="B1")
        clip_result = compute_column_beam_joint(col, beam)

        regions = regions_from_clip_result(
            clip_result, 3000.0, 500.0, col_poly, beam_poly
        )
        for r in regions:
            assert isinstance(r, ExtrudeRegion)
            assert r.height > 0
            assert len(r.vertices_2d) >= 3
            assert r.material in ("CONCRETE", "FORMWORK")
