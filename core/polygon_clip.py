"""
2D 폴리곤 교차 분할 엔진 (특허 제4호 핵심 로직)

3D Boolean 연산(Part.cut, Part.intersect) 전면 금지.
모든 기둥-보 교차는 2D X-Y 평면에서 Shapely로 선행 분할 후,
각 영역을 독립적으로 Z값까지 Extrude.
"""

from dataclasses import dataclass
from typing import Optional
from shapely.geometry import Polygon, LineString, MultiLineString
from shapely.ops import unary_union


@dataclass
class ColumnProfile:
    """기둥 단면 프로파일"""
    polygon: Polygon      # Shapely Polygon (X-Y 평면)
    height: float         # 층고 (mm 단위)
    member_id: str        # 부재 ID


@dataclass
class BeamProfile:
    """보 단면 프로파일"""
    polygon: Polygon      # Shapely Polygon (X-Y 평면, 보의 footprint)
    height: float         # 보 춤 (mm 단위)
    member_id: str        # 부재 ID


@dataclass
class JointResult:
    """교차점 연산 결과"""
    member_id: str
    volume_m3: float               # 순체적 (m³)
    formwork_area_m2: float        # 거푸집 면적 (m²)
    formwork_deduction_m2: float   # 거푸집 공제량 (m², 사칙연산)
    intersection_area_mm2: float   # 교차 영역 면적 (mm²)
    cut_line_length_mm: float      # 2D 가상 절단선 길이 (mm)


def compute_column_beam_joint(
    column: ColumnProfile,
    beam: BeamProfile,
) -> JointResult:
    """
    기둥-보 교차 지점 2D 선행 분할 후 순체적·거푸집 산출.

    알고리즘:
    1. intersection(A) = 기둥 폴리곤 ∩ 보 폴리곤
    2. remainder(B)    = 기둥 폴리곤 - 보 폴리곤
    3. 체적 = A.area × beam.height + B.area × column.height
    4. 절단선 = 두 영역 경계의 공유 선분
    5. 거푸집 공제 = 절단선 길이 × min(높이) × 2
    """
    intersection = column.polygon.intersection(beam.polygon)
    remainder = column.polygon.difference(beam.polygon)

    intersection_area = intersection.area   # mm²
    remainder_area = remainder.area         # mm²

    # 체적 (mm³ → m³)
    vol_intersection = intersection_area * beam.height
    vol_remainder = remainder_area * column.height
    total_volume_mm3 = vol_intersection + vol_remainder
    total_volume_m3 = total_volume_mm3 / 1_000_000_000

    # 절단선 길이 (mm): 기둥 경계 ∩ 보 경계
    cut_line = column.polygon.boundary.intersection(beam.polygon)
    cut_line_length = _extract_total_length(cut_line)

    # 거푸집 공제 (mm² → m²): 사칙연산, 3D 스캔 불필요
    shorter_height = min(column.height, beam.height)
    formwork_deduction_mm2 = cut_line_length * shorter_height * 2
    formwork_deduction_m2 = formwork_deduction_mm2 / 1_000_000

    # 기둥 순 거푸집 면적 (외주 × 높이 - 공제)
    perimeter_mm = column.polygon.exterior.length
    gross_formwork_mm2 = perimeter_mm * column.height
    net_formwork_m2 = (gross_formwork_mm2 - formwork_deduction_mm2) / 1_000_000

    return JointResult(
        member_id=column.member_id,
        volume_m3=round(total_volume_m3, 6),
        formwork_area_m2=round(net_formwork_m2, 4),
        formwork_deduction_m2=round(formwork_deduction_m2, 4),
        intersection_area_mm2=round(intersection_area, 2),
        cut_line_length_mm=round(cut_line_length, 2),
    )


def compute_multi_beam_joints(
    column: ColumnProfile,
    beams: list[BeamProfile],
) -> JointResult:
    """
    기둥 1개 + 보 N개 교차 처리 (복합 교차).
    모든 보의 union을 먼저 구한 후 단일 교차로 처리.
    """
    if not beams:
        # 보 없음: 순수 기둥 체적만
        vol_m3 = column.polygon.area * column.height / 1_000_000_000
        perimeter = column.polygon.exterior.length
        formwork_m2 = perimeter * column.height / 1_000_000
        return JointResult(
            member_id=column.member_id,
            volume_m3=round(vol_m3, 6),
            formwork_area_m2=round(formwork_m2, 4),
            formwork_deduction_m2=0.0,
            intersection_area_mm2=0.0,
            cut_line_length_mm=0.0,
        )

    beam_union = unary_union([b.polygon for b in beams])
    # 복합 교차의 대표 높이: 가장 낮은 보 높이 사용
    min_beam_height = min(b.height for b in beams)

    dummy_beam = BeamProfile(
        polygon=beam_union,
        height=min_beam_height,
        member_id="UNION",
    )
    return compute_column_beam_joint(column, dummy_beam)


def _extract_total_length(geom) -> float:
    """Shapely geometry에서 총 선분 길이 추출"""
    if geom.is_empty:
        return 0.0
    if hasattr(geom, 'length'):
        return geom.length
    return 0.0
