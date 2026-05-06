"""
sheet_data_model.py — 메타 풀세트 표준 데이터 클래스
부산 에코델타 24BL FreeCAD BOQ 자동화 3지국

모든 치수는 도면에서 읽은 값. 추정 없음.
출처: output/actual_dimensions_v3.json
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 좌표/단면 기본 타입
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class Rect:
    """직사각형 단면 (mm 단위)"""
    w: float
    h: float

    @property
    def area_mm2(self) -> float:
        return self.w * self.h


@dataclass(frozen=True)
class CircleSection:
    """원형 단면 (mm 단위)"""
    diameter: float

    @property
    def w(self) -> float:
        return self.diameter

    @property
    def h(self) -> float:
        return self.diameter


# ---------------------------------------------------------------------------
# 부재 데이터 클래스
# ---------------------------------------------------------------------------

@dataclass
class ColumnData:
    """기둥 인스턴스"""
    symbol: str                       # 기둥 기호 (e.g. TC1, C1, -2~-1C1)
    center: Point2D                   # 평면 중심 좌표 (DXF 좌표계)
    section_w: float                  # 단면 폭 (mm)
    section_h: float                  # 단면 높이 (mm)
    is_circular: bool = False         # 원형 단면 여부
    z_bottom: Optional[float] = None  # 기둥 하단 z (mm, GL 기준)
    z_top: Optional[float] = None     # 기둥 상단 z (mm, GL 기준)
    source_codex: str = ""            # 출처 codex ('101~112동' | '지하주차장' | ...)
    matched: bool = True              # codex 매칭 여부


@dataclass
class GirderData:
    """보(Girder) 인스턴스"""
    symbol: str                       # 보 기호 (e.g. G1, RB20)
    start: Point2D                    # 보 시작점
    end: Point2D                      # 보 끝점
    width: float                      # 보 폭 (mm)
    height: float                     # 보 높이 (mm)
    z_bottom: Optional[float] = None  # 보 하단 z
    z_top: Optional[float] = None     # 보 상단 z


@dataclass
class WallData:
    """벽체 세그먼트"""
    start: Point2D
    end: Point2D
    thickness: float                  # 벽체 두께 (mm)
    z_bottom: Optional[float] = None
    z_top: Optional[float] = None


@dataclass
class WallPair:
    """벽체 쌍 (두 LINE이 이루는 벽체)"""
    line_a_start: Point2D
    line_a_end: Point2D
    line_b_start: Point2D
    line_b_end: Point2D
    thickness: float                  # 두 선 간격 = 벽체 두께
    length: float                     # 벽체 길이
    z_bottom: Optional[float] = None
    z_top: Optional[float] = None


# ---------------------------------------------------------------------------
# 층 치수 상수 (도면에서 읽은 값 — 변경 금지)
# ---------------------------------------------------------------------------

class FloorDimensions:
    """
    부산 에코델타 24BL 확정 치수
    출처: actual_dimensions_v3.json (도면 직독, 추정 없음)
    """

    # 슬라브 레벨 (SL, mm, GL 기준)
    SL_B2F: float = -9050.0
    SL_B1F: float = -5600.0
    SL_1F: float = 370.0

    # 층고 (mm)
    FLOOR_HEIGHT_B2F: float = 3450.0   # B1F SL - B2F SL
    FLOOR_HEIGHT_B1F: float = 5970.0   # 1F SL - B1F SL

    # 슬라브 두께 (mm) — S40-051~057 150mm 826건 최다
    SLAB_THICKNESS: float = 150.0

    # 보 높이 (mm) — codex_beams_basement.json 40종 전체
    GIRDER_HEIGHT: float = 900.0

    # 기둥 높이 (mm) = 층고 - 슬라브 두께
    COLUMN_HEIGHT_B2F: float = 3300.0  # 3450 - 150
    COLUMN_HEIGHT_B1F: float = 5820.0  # 5970 - 150

    @classmethod
    def column_z_range(cls, floor: str) -> tuple[float, float]:
        """기둥 z 범위 (bottom, top)"""
        if floor == "B2F":
            return cls.SL_B2F, cls.SL_B1F - cls.SLAB_THICKNESS  # (-9050, -5750)
        if floor == "B1F":
            return cls.SL_B1F, cls.SL_1F - cls.SLAB_THICKNESS    # (-5600, 220)
        raise ValueError(f"Unknown floor: {floor}")

    @classmethod
    def girder_z_range(cls, floor: str) -> tuple[float, float]:
        """보 z 범위 (bottom, top)"""
        if floor == "B2F":
            z_top = cls.SL_B1F - cls.SLAB_THICKNESS               # -5750
            z_bottom = cls.SL_B1F - cls.GIRDER_HEIGHT              # -6500
            return z_bottom, z_top
        if floor == "B1F":
            z_top = cls.SL_1F - cls.SLAB_THICKNESS                 # 220
            z_bottom = cls.SL_1F - cls.GIRDER_HEIGHT               # -530
            return z_bottom, z_top
        raise ValueError(f"Unknown floor: {floor}")

    @classmethod
    def slab_z_range(cls, floor: str) -> tuple[float, float]:
        """슬라브 z 범위 (bottom, top)"""
        if floor == "B2F":
            z_top = cls.SL_B1F                                     # -5600 (B1F 바닥면)
            z_bottom = z_top - cls.SLAB_THICKNESS                  # -5750
            return z_bottom, z_top
        if floor == "B1F":
            z_top = cls.SL_1F                                      # 370 (1F 바닥면)
            z_bottom = z_top - cls.SLAB_THICKNESS                  # 220
            return z_bottom, z_top
        raise ValueError(f"Unknown floor: {floor}")


# ---------------------------------------------------------------------------
# 시트 데이터 클래스 (핵심 산출물)
# ---------------------------------------------------------------------------

@dataclass
class SheetData:
    """
    한 도면 시트의 완전한 구조 데이터.
    build 분리, BOQ 산정, 3D 스택 생성의 단일 진실 원천.
    """
    sheet_id: str                         # 시트 ID (e.g. 'B1', 'B2', 'S30-022')
    floor: int                            # 층 번호 (-2=B2F, -1=B1F, 1=1F)

    # 슬라브 레벨 (도면에서 읽은 값)
    z_floor_bottom: float                 # 해당 층 SL (바닥)
    z_floor_top: float                    # 다음 층 SL (천장)

    # 부재 두께 (도면에서 읽은 값)
    slab_thickness: float                 # 슬라브 두께
    girder_height: float                  # 보 높이

    # 부재 리스트 (좌표 포함)
    columns: list[ColumnData] = field(default_factory=list)
    girders: list[GirderData] = field(default_factory=list)
    walls: list[WallData] = field(default_factory=list)
    wall_segments: list[WallData] = field(default_factory=list)

    # 미매칭/전체 wall_pair (build 분리 핵심)
    unmatched_columns: list[ColumnData] = field(default_factory=list)
    wall_pairs_all: list[WallPair] = field(default_factory=list)

    # 메타
    source_dxf: str = ""                  # 원본 DXF 파일 경로
    extraction_date: str = ""

    # ---------------------------------------------------------------------------
    # 파생 속성 (도면값에서 계산)
    # ---------------------------------------------------------------------------

    @property
    def column_height(self) -> float:
        """기둥 높이 = 층고 - 슬라브 두께"""
        return (self.z_floor_top - self.z_floor_bottom) - self.slab_thickness

    @property
    def girder_z_bottom(self) -> float:
        """보 하단 z = 다음 층 SL - 보 높이"""
        return self.z_floor_top - self.girder_height

    @property
    def girder_z_top(self) -> float:
        """보 상단 z = 다음 층 SL - 슬라브 두께"""
        return self.z_floor_top - self.slab_thickness

    @property
    def slab_z_bottom(self) -> float:
        """슬라브 하단 z"""
        return self.z_floor_top - self.slab_thickness

    @property
    def slab_z_top(self) -> float:
        """슬라브 상단 z = 다음 층 SL"""
        return self.z_floor_top

    @property
    def total_column_count(self) -> int:
        return len(self.columns) + len(self.unmatched_columns)

    @property
    def match_rate(self) -> float:
        total = self.total_column_count
        if total == 0:
            return 0.0
        return len(self.columns) / total

    def summary(self) -> dict:
        """채굴 현황 요약"""
        return {
            "sheet_id": self.sheet_id,
            "floor": self.floor,
            "z_floor_bottom": self.z_floor_bottom,
            "z_floor_top": self.z_floor_top,
            "column_height_mm": self.column_height,
            "girder_z_bottom": self.girder_z_bottom,
            "girder_z_top": self.girder_z_top,
            "slab_z_bottom": self.slab_z_bottom,
            "slab_z_top": self.slab_z_top,
            "matched_columns": len(self.columns),
            "unmatched_columns": len(self.unmatched_columns),
            "match_rate_pct": round(self.match_rate * 100, 1),
            "girders": len(self.girders),
            "walls": len(self.walls),
            "wall_segments": len(self.wall_segments),
            "wall_pairs_all": len(self.wall_pairs_all),
        }


# ---------------------------------------------------------------------------
# 팩토리 함수
# ---------------------------------------------------------------------------

def make_sheet_b2f(sheet_id: str = "B2") -> SheetData:
    """B2F 시트 기본 인스턴스 (확정 치수 자동 주입)"""
    fd = FloorDimensions
    return SheetData(
        sheet_id=sheet_id,
        floor=-2,
        z_floor_bottom=fd.SL_B2F,
        z_floor_top=fd.SL_B1F,
        slab_thickness=fd.SLAB_THICKNESS,
        girder_height=fd.GIRDER_HEIGHT,
    )


def make_sheet_b1f(sheet_id: str = "B1") -> SheetData:
    """B1F 시트 기본 인스턴스 (확정 치수 자동 주입)"""
    fd = FloorDimensions
    return SheetData(
        sheet_id=sheet_id,
        floor=-1,
        z_floor_bottom=fd.SL_B1F,
        z_floor_top=fd.SL_1F,
        slab_thickness=fd.SLAB_THICKNESS,
        girder_height=fd.GIRDER_HEIGHT,
    )
