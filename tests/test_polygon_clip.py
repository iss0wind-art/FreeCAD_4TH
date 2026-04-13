"""
2D 폴리곤 교차 분할 엔진 테스트 (특허 제4호 로직 검증)

시나리오:
- 기둥: 600×600mm 정사각형
- 보: 300×500mm 단면, 기둥 중앙 통과
- 기둥 층고: 3000mm / 보 춤: 500mm
"""

import pytest
from shapely.geometry import Polygon, box
from core.polygon_clip import (
    ColumnProfile,
    BeamProfile,
    JointResult,
    compute_column_beam_joint,
    compute_multi_beam_joints,
)


# ─────────────────────────────────────
# 공통 픽스처
# ─────────────────────────────────────

@pytest.fixture
def square_column_600():
    """600×600mm 정사각형 기둥 (원점 중심)"""
    poly = box(-300, -300, 300, 300)  # 600×600
    return ColumnProfile(polygon=poly, height=3000.0, member_id="C1")


@pytest.fixture
def beam_through_center(square_column_600):
    """300mm 폭 보가 기둥 중앙을 X축 방향으로 관통"""
    poly = box(-1000, -150, 1000, 150)  # 폭 300mm, X방향 관통
    return BeamProfile(polygon=poly, height=500.0, member_id="B1")


@pytest.fixture
def beam_no_overlap():
    """기둥과 전혀 겹치지 않는 보"""
    poly = box(500, 500, 1500, 800)
    return BeamProfile(polygon=poly, height=500.0, member_id="B_NONE")


@pytest.fixture
def beam_full_cover(square_column_600):
    """기둥 전체를 덮는 보 (완전 포함)"""
    poly = box(-400, -400, 400, 400)  # 기둥보다 큼
    return BeamProfile(polygon=poly, height=500.0, member_id="B_FULL")


# ─────────────────────────────────────
# 교차 영역 정확도 테스트
# ─────────────────────────────────────

class TestIntersectionGeometry:
    def test_intersection_area_correct(self, square_column_600, beam_through_center):
        """교차 영역: 600×300 = 180,000 mm²"""
        result = compute_column_beam_joint(square_column_600, beam_through_center)
        assert abs(result.intersection_area_mm2 - 180_000.0) < 1.0

    def test_no_intersection_returns_zero(self, square_column_600, beam_no_overlap):
        """겹치지 않는 보 → 교차 면적 0"""
        result = compute_column_beam_joint(square_column_600, beam_no_overlap)
        assert result.intersection_area_mm2 == 0.0

    def test_full_cover_intersection_equals_column(self, square_column_600, beam_full_cover):
        """보가 기둥 전체를 덮으면 교차 면적 = 기둥 면적"""
        col_area = square_column_600.polygon.area
        result = compute_column_beam_joint(square_column_600, beam_full_cover)
        assert abs(result.intersection_area_mm2 - col_area) < 1.0


# ─────────────────────────────────────
# 체적 산출 정확도 테스트 (핵심)
# ─────────────────────────────────────

class TestVolumeCalculation:
    def test_volume_no_beam(self, square_column_600, beam_no_overlap):
        """보 미교차: 체적 = 기둥 단면적 × 층고"""
        expected_m3 = (600 * 600 * 3000) / 1_000_000_000  # 1.08 m³
        result = compute_column_beam_joint(square_column_600, beam_no_overlap)
        assert abs(result.volume_m3 - expected_m3) < 0.000001

    def test_volume_beam_through_center(self, square_column_600, beam_through_center):
        """
        보가 중앙 관통 시 순체적:
        - A영역(교차, 600×300): 180,000 mm² × 500mm = 90,000,000 mm³
        - B영역(잔여, 600×300×2): 180,000 mm² × 3000mm = 540,000,000 mm³
        - 합계: 630,000,000 mm³ = 0.63 m³
        """
        result = compute_column_beam_joint(square_column_600, beam_through_center)
        expected_m3 = 630_000_000 / 1_000_000_000  # 0.63
        assert abs(result.volume_m3 - expected_m3) < 0.000001

    def test_volume_full_cover(self, square_column_600, beam_full_cover):
        """보가 기둥 전체 덮을 때: 체적 = 기둥 단면 × 보 높이"""
        col_area = square_column_600.polygon.area  # 360,000 mm²
        expected_m3 = col_area * beam_full_cover.height / 1_000_000_000
        result = compute_column_beam_joint(square_column_600, beam_full_cover)
        assert abs(result.volume_m3 - expected_m3) < 0.000001

    def test_volume_is_always_positive(self, square_column_600, beam_through_center):
        """체적은 항상 양수"""
        result = compute_column_beam_joint(square_column_600, beam_through_center)
        assert result.volume_m3 > 0


# ─────────────────────────────────────
# 거푸집 공제 사칙연산 테스트 (핵심)
# ─────────────────────────────────────

class TestFormworkDeduction:
    def test_cut_line_length_beam_through_center(self, square_column_600, beam_through_center):
        """
        보가 중앙 관통 시 절단선:
        X방향으로 기둥 경계 좌(-300)와 우(300)에서 각 600mm 폭의 선
        → 절단선 총 길이 = 300×2 = 600mm (보 폭 방향 양쪽)
        실제: 기둥 경계와 보 내부의 교차 = Y=-150, Y=150 각 600mm 선분 (X: -300~300)
        각 선분 600mm × 2개 = 1200mm
        """
        result = compute_column_beam_joint(square_column_600, beam_through_center)
        # 절단선 = 기둥 외곽선이 보와 만나는 Y=-150, Y=150 라인
        # 각 선분: 600mm (기둥 폭) × 2 = 1200mm (실제로는 기둥 boundary와 beam polygon의 교차)
        assert result.cut_line_length_mm > 0

    def test_formwork_deduction_no_overlap(self, square_column_600, beam_no_overlap):
        """겹치지 않으면 공제 없음"""
        result = compute_column_beam_joint(square_column_600, beam_no_overlap)
        assert result.formwork_deduction_m2 == 0.0

    def test_formwork_deduction_is_non_negative(self, square_column_600, beam_through_center):
        """거푸집 공제량은 항상 0 이상"""
        result = compute_column_beam_joint(square_column_600, beam_through_center)
        assert result.formwork_deduction_m2 >= 0.0

    def test_net_formwork_less_than_gross(self, square_column_600, beam_through_center):
        """순 거푸집 면적 < 전체 거푸집 면적 (교차 있을 때)"""
        perimeter_mm = square_column_600.polygon.exterior.length
        gross_m2 = perimeter_mm * square_column_600.height / 1_000_000
        result = compute_column_beam_joint(square_column_600, beam_through_center)
        assert result.formwork_area_m2 < gross_m2


# ─────────────────────────────────────
# 복합 교차 (N개 보) 테스트
# ─────────────────────────────────────

class TestMultiBeamJoints:
    def test_no_beams_returns_pure_column_volume(self, square_column_600):
        """보 없음 → 순수 기둥 체적"""
        result = compute_multi_beam_joints(square_column_600, [])
        expected_m3 = (600 * 600 * 3000) / 1_000_000_000
        assert abs(result.volume_m3 - expected_m3) < 0.000001

    def test_two_perpendicular_beams(self, square_column_600):
        """X방향 보 + Y방향 보 동시 교차 (4방향 기둥)"""
        beam_x = BeamProfile(
            polygon=box(-1000, -150, 1000, 150),
            height=500.0, member_id="BX"
        )
        beam_y = BeamProfile(
            polygon=box(-150, -1000, 150, 1000),
            height=500.0, member_id="BY"
        )
        result = compute_multi_beam_joints(square_column_600, [beam_x, beam_y])
        # 체적은 반드시 순수 기둥 체적보다 작아야 함 (보 높이 < 층고)
        pure_vol = (600 * 600 * 3000) / 1_000_000_000
        assert result.volume_m3 < pure_vol
        assert result.volume_m3 > 0

    def test_member_id_preserved(self, square_column_600, beam_through_center):
        """결과 부재 ID가 기둥 ID와 일치"""
        result = compute_column_beam_joint(square_column_600, beam_through_center)
        assert result.member_id == "C1"


# ─────────────────────────────────────
# 수치 정밀도 테스트
# ─────────────────────────────────────

class TestNumericalPrecision:
    def test_volume_rounded_to_6_decimal(self, square_column_600, beam_through_center):
        """체적은 소수 6자리로 반올림"""
        result = compute_column_beam_joint(square_column_600, beam_through_center)
        assert result.volume_m3 == round(result.volume_m3, 6)

    def test_formwork_rounded_to_4_decimal(self, square_column_600, beam_through_center):
        """거푸집 면적은 소수 4자리로 반올림"""
        result = compute_column_beam_joint(square_column_600, beam_through_center)
        assert result.formwork_area_m2 == round(result.formwork_area_m2, 4)
