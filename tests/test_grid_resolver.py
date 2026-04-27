"""
core/grid_resolver.py 테스트 — Phase 1 Track E

sample_project.boq.yaml: A=(0,0), B=(6000,0), 1=(0,0), 2=(0,8000)
"""

from __future__ import annotations

import math
import pytest

from core.grid_resolver import resolve_at, resolve_all, _column_polygon, _beam_polygon
from core.manifest_parser import GridConfig, GridRef, parse_manifest


# ─────────────────────────────────────────────────────────────
# fixture — 샘플 그리드
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def sample_grid() -> GridConfig:
    return GridConfig(
        origin=[0.0, 0.0],
        rotation=0.0,
        x_lines={"A": 0.0, "B": 6000.0},
        y_lines={"1": 0.0, "2": 8000.0},
    )


SAMPLE_YAML = """\
project:
  id: "SAMPLE-001"
  name: "test"
  units: mm

grid:
  origin: [0, 0]
  rotation: 0
  x_lines:
    A: 0
    B: 6000
  y_lines:
    "1": 0
    "2": 8000

floors:
  - id: "1F"
    z_base: 0
    height: 4500

members:
  - id: "C-A1-1F"
    spec: "TC1"
    type: column
    floor: "1F"
    at: { grid: ["A", "1"] }

  - id: "C-B1-1F"
    spec: "TC1"
    type: column
    floor: "1F"
    at: { grid: ["B", "1"] }

  - id: "C-A2-1F"
    spec: "TC1"
    type: column
    floor: "1F"
    at: { grid: ["A", "2"] }

  - id: "C-B2-1F"
    spec: "TC1"
    type: column
    floor: "1F"
    at: { grid: ["B", "2"] }

  - id: "B-A1-B1-1F"
    spec: "RG1"
    type: beam
    floor: "1F"
    from: { grid: ["A", "1"] }
    to: { grid: ["B", "1"] }
    z_offset: -100

  - id: "B-A2-B2-1F"
    spec: "RG1"
    type: beam
    floor: "1F"
    from: { grid: ["A", "2"] }
    to: { grid: ["B", "2"] }
    z_offset: -100

  - id: "B-A1-A2-1F"
    spec: "RG1"
    type: beam
    floor: "1F"
    from: { grid: ["A", "1"] }
    to: { grid: ["A", "2"] }
    z_offset: -100

  - id: "B-B1-B2-1F"
    spec: "RG1"
    type: beam
    floor: "1F"
    from: { grid: ["B", "1"] }
    to: { grid: ["B", "2"] }
    z_offset: -100
"""


# ─────────────────────────────────────────────────────────────
# resolve_at
# ─────────────────────────────────────────────────────────────
class TestResolveAt:
    def test_grid_a1_origin(self, sample_grid):
        ref = GridRef(grid=["A", "1"])
        x, y = resolve_at(ref, sample_grid)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(0.0)

    def test_grid_b2(self, sample_grid):
        ref = GridRef(grid=["B", "2"])
        x, y = resolve_at(ref, sample_grid)
        assert x == pytest.approx(6000.0)
        assert y == pytest.approx(8000.0)

    def test_xy_absolute(self, sample_grid):
        ref = GridRef(xy=[3500.0, 4200.0])
        x, y = resolve_at(ref, sample_grid)
        assert x == pytest.approx(3500.0)
        assert y == pytest.approx(4200.0)

    def test_grid_without_config_raises(self):
        ref = GridRef(grid=["A", "1"])
        with pytest.raises(ValueError, match="grid 설정"):
            resolve_at(ref, None)

    def test_rotation_90_degrees(self):
        grid = GridConfig(
            origin=[0.0, 0.0],
            rotation=90.0,
            x_lines={"A": 1000.0},
            y_lines={"1": 0.0},
        )
        ref = GridRef(grid=["A", "1"])
        x, y = resolve_at(ref, grid)
        # 90도 회전: local(1000, 0) → global(0, 1000)
        assert x == pytest.approx(0.0, abs=1e-6)
        assert y == pytest.approx(1000.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────
# 폴리곤 생성
# ─────────────────────────────────────────────────────────────
class TestPolygons:
    def test_column_polygon_vertex_count(self):
        verts = _column_polygon(0, 0, 500, 500, 0)
        assert len(verts) == 4

    def test_column_polygon_centroid(self):
        verts = _column_polygon(1000, 2000, 600, 400, 0)
        cx = sum(v[0] for v in verts) / 4
        cy = sum(v[1] for v in verts) / 4
        assert cx == pytest.approx(1000.0, abs=1e-6)
        assert cy == pytest.approx(2000.0, abs=1e-6)

    def test_beam_polygon_vertex_count(self):
        verts = _beam_polygon(0, 0, 6000, 0, 300)
        assert len(verts) == 4

    def test_beam_polygon_width(self):
        verts = _beam_polygon(0, 0, 6000, 0, 300)
        y_vals = sorted(set(v[1] for v in verts))
        assert abs(y_vals[-1] - y_vals[0]) == pytest.approx(300.0, abs=1e-6)

    def test_beam_zero_length_raises(self):
        with pytest.raises(ValueError, match="길이 0"):
            _beam_polygon(0, 0, 0, 0, 300)


# ─────────────────────────────────────────────────────────────
# resolve_all — sample YAML 8개 부재
# ─────────────────────────────────────────────────────────────
class TestResolveAll:
    def test_sample_8_members_resolved(self):
        manifest = parse_manifest(SAMPLE_YAML)
        results = resolve_all(manifest)
        assert len(results) == 8

    def test_column_member_type(self):
        manifest = parse_manifest(SAMPLE_YAML)
        results = resolve_all(manifest)
        columns = [r for r in results if r["member_type"] == "COLUMN"]
        assert len(columns) == 4

    def test_beam_member_type(self):
        manifest = parse_manifest(SAMPLE_YAML)
        results = resolve_all(manifest)
        beams = [r for r in results if r["member_type"] == "BEAM"]
        assert len(beams) == 4

    def test_column_has_vertices(self):
        manifest = parse_manifest(SAMPLE_YAML)
        results = resolve_all(manifest)
        col = next(r for r in results if r["member_id"] == "C-A1-1F")
        assert len(col["vertices_2d"]) == 4

    def test_beam_z_offset_applied(self):
        manifest = parse_manifest(SAMPLE_YAML)
        results = resolve_all(manifest)
        beam = next(r for r in results if r["member_id"] == "B-A1-B1-1F")
        assert beam["z_base"] == pytest.approx(0 + (-100))

    def test_unsupported_type_skipped(self):
        slab_yaml = SAMPLE_YAML + """\
  - id: "S-1F"
    spec: "SL1"
    type: slab
    floor: "1F"
    polygon:
      - grid: ["A", "1"]
      - grid: ["B", "1"]
      - grid: ["B", "2"]
"""
        manifest = parse_manifest(slab_yaml)
        results = resolve_all(manifest)
        assert all(r["member_type"] in ("COLUMN", "BEAM") for r in results)
