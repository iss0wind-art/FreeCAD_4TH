"""
anchor_finder.py — 시트 정규화 앵커 자동 검출 (v4 P2.2)
=========================================================
우선순위:
  1. (X1, Y1) 격자 교점 — 신뢰도 0.9
  2. EV 코어 중심 (TextLabelEVDetector 패턴)
  3. 시트 SW 모서리 — 신뢰도 0.5
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from core.v2.coords.grid_resolver import SheetGrid
from core.v2.inspect.meta_pipeline import DrawingMeta
from core.v2.inspect.sheet_segmenter import SheetMeta


@dataclass
class Anchor:
    sheet_id: str
    x: float
    y: float
    method: str           # "grid_x1y1" / "ev_core" / "sw_corner"
    confidence: float


def find_canonical_anchors(
    meta: DrawingMeta,
    grids: Dict[str, SheetGrid],
) -> Dict[str, Anchor]:
    """시트별 정규화 앵커 (가장 신뢰도 높은 것)."""
    result: Dict[str, Anchor] = {}

    for sheet in meta.sheets:
        anchor = _find_one(sheet, grids)
        result[sheet.sheet_id] = anchor

    return result


def _find_one(sheet: SheetMeta, grids: Dict[str, SheetGrid]) -> Anchor:
    grid = grids.get(sheet.sheet_id)

    # 1. X1·Y1 교점 (격자 origin)
    if grid is not None:
        return Anchor(
            sheet_id=sheet.sheet_id,
            x=grid.origin[0],
            y=grid.origin[1],
            method="grid_x1y1",
            confidence=0.9,
        )

    # 2. SW 모서리 폴백
    return Anchor(
        sheet_id=sheet.sheet_id,
        x=sheet.sw_corner[0],
        y=sheet.sw_corner[1],
        method="sw_corner",
        confidence=0.5,
    )
