"""
core/manifest_parser.py 테스트 — Phase 1 Track C TDD

샘플: spec/sample_project.boq.yaml (4기둥+4보)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.manifest_parser import (
    GridRef,
    ManifestModel,
    ProjectMeta,
    normalize_to_mm,
    parse_manifest,
)

# ─────────────────────────────────────────────────────────────
# fixtures
# ─────────────────────────────────────────────────────────────
SAMPLE_YAML = """\
$schema: "https://boq.local/schemas/manifest/v1"
version: "1.0"

project:
  id: "SAMPLE-001"
  name: "Phase 1 검증 샘플"
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
"""


@pytest.fixture
def sample_manifest() -> ManifestModel:
    return parse_manifest(SAMPLE_YAML)


# ─────────────────────────────────────────────────────────────
# 단위 정규화
# ─────────────────────────────────────────────────────────────
class TestNormalizeToMm:
    def test_mm_value_unchanged(self):
        assert normalize_to_mm(500.0) == 500.0

    def test_m_value_converted(self):
        assert normalize_to_mm(0.5) == 500.0

    def test_boundary_exactly_10(self):
        # 10.0 은 mm 간주
        assert normalize_to_mm(10.0) == 10.0

    def test_boundary_below_10(self):
        # 9.9 → m 간주 → 9900
        assert normalize_to_mm(9.9) == pytest.approx(9900.0)

    def test_overflow_raises(self):
        with pytest.raises(ValueError, match="HUMAN_REQUIRED"):
            normalize_to_mm(200000.0)  # 200000mm = 200m > 100m 허용 한계


# ─────────────────────────────────────────────────────────────
# 파싱 — 정상 케이스
# ─────────────────────────────────────────────────────────────
class TestParseManifestHappy:
    def test_project_id(self, sample_manifest):
        assert sample_manifest.project.id == "SAMPLE-001"

    def test_grid_x_lines(self, sample_manifest):
        assert sample_manifest.grid.x_lines["B"] == 6000

    def test_floor_count(self, sample_manifest):
        assert len(sample_manifest.floors) == 1

    def test_member_count(self, sample_manifest):
        assert len(sample_manifest.members) == 3

    def test_column_placement(self, sample_manifest):
        col = next(m for m in sample_manifest.members if m.id == "C-A1-1F")
        assert col.at is not None
        assert col.at.grid == ["A", "1"]

    def test_beam_from_to(self, sample_manifest):
        beam = next(m for m in sample_manifest.members if m.id == "B-A1-B1-1F")
        assert beam.from_ is not None
        assert beam.to is not None
        assert beam.z_offset == -100

    def test_subtype_defaults_none(self, sample_manifest):
        col = next(m for m in sample_manifest.members if m.id == "C-A1-1F")
        assert col.subtype is None


# ─────────────────────────────────────────────────────────────
# 파싱 — 검증 오류
# ─────────────────────────────────────────────────────────────
class TestParseManifestValidation:
    def test_invalid_project_id(self):
        bad = SAMPLE_YAML.replace('id: "SAMPLE-001"', 'id: "A B"', 1)
        with pytest.raises(Exception):
            parse_manifest(bad)

    def test_duplicate_member_id(self):
        bad = SAMPLE_YAML.replace('"C-B2-1F"', '"C-A1-1F"', 1)
        with pytest.raises(Exception, match="중복"):
            parse_manifest(bad)

    def test_missing_floor_reference(self):
        bad = SAMPLE_YAML.replace('floor: "1F"', 'floor: "99F"', 1)
        with pytest.raises(Exception, match="floor"):
            parse_manifest(bad)

    def test_invalid_grid_key(self):
        bad = SAMPLE_YAML.replace('grid: ["A", "1"]', 'grid: ["Z", "1"]', 1)
        with pytest.raises(Exception, match="x_lines"):
            parse_manifest(bad)

    def test_no_placement_pattern(self):
        no_placement = """\
project:
  id: "T1"
  name: "test"
floors:
  - id: "1F"
    z_base: 0
    height: 3000
members:
  - id: "M1"
    spec: "X"
    type: column
    floor: "1F"
"""
        with pytest.raises(Exception, match="배치 패턴"):
            parse_manifest(no_placement)

    def test_z_offset_out_of_range(self):
        bad = SAMPLE_YAML.replace("z_offset: -100", "z_offset: -99999")
        with pytest.raises(Exception):
            parse_manifest(bad)

    def test_units_invalid(self):
        bad = SAMPLE_YAML.replace("units: mm", "units: km")
        with pytest.raises(Exception):
            parse_manifest(bad)

    def test_subtype_invalid_value(self):
        bad = SAMPLE_YAML.replace(
            'type: column\n    floor: "1F"\n    at: { grid: ["C-A1-1F"',
            'type: column\n    floor: "1F"\n    subtype: flying_beam\n    at: { grid: ["A"',
        )
        # subtype 값 오류는 ValidationError
        edge_yaml = SAMPLE_YAML + "\n  - id: 'X1'\n    spec: 'TC1'\n    type: beam\n    floor: '1F'\n    subtype: bad_type\n    from: {grid: ['A','1']}\n    to: {grid: ['B','1']}\n"
        with pytest.raises(Exception):
            parse_manifest(edge_yaml)
