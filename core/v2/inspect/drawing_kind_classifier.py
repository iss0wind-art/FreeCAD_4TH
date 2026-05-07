"""
drawing_kind_classifier.py — DXF 종류 자동 추정 (v4 P1.6)
==========================================================
DONG (한 동 다층) / PKG (다동 평면) / SECTION (단면도) / UNKNOWN.
"""
from __future__ import annotations

from enum import Enum
from typing import List

from core.v2.inspect.sheet_segmenter import SheetMeta


class DrawingKind(str, Enum):
    DONG    = "dong"        # 한 동 다층 평면도
    PKG     = "pkg"         # 다동 평면도 (주차장 등)
    SECTION = "section"     # 단면도
    UNKNOWN = "unknown"


def classify_drawing_kind(
    sheets: List[SheetMeta],
    pitch_x: float = 0.0,
    pitch_y: float = 0.0,
    grid_x_count: int = 0,
    grid_y_count: int = 0,
    sl_value_count: int = 0,
    pkg_pitch_threshold: float = 200_000.0,
) -> DrawingKind:
    """판단 (도면-내재 신호만):

    - 시트 ≥ 2 AND pitch_x > pkg_pitch_threshold → PKG (큰 점프)
    - 시트 ≥ 3 AND grid 풍부 + pitch 일관 → DONG
    - SL 풍부 + 격자 적음 → SECTION
    - 그 외 UNKNOWN
    """
    n = len(sheets)

    if n >= 2 and pitch_x > pkg_pitch_threshold:
        return DrawingKind.PKG

    if n >= 3 and (grid_x_count + grid_y_count) > n:
        return DrawingKind.DONG

    if sl_value_count > 5 and grid_x_count < 5:
        return DrawingKind.SECTION

    if n >= 1:
        return DrawingKind.DONG  # 단일 시트 도면 기본

    return DrawingKind.UNKNOWN
