"""
transform_pipeline.py — 좌표 시스템 통합 (v4 P2.5)
====================================================
DrawingMeta → grids + anchors + transforms.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.v2.coords.anchor_finder import Anchor, find_canonical_anchors
from core.v2.coords.grid_resolver import SheetGrid, resolve_grid_per_sheet
from core.v2.coords.sheet_alignment import (
    SheetTransform,
    align_sheets_within_drawing,
)
from core.v2.inspect.meta_pipeline import DrawingMeta


@dataclass
class CoordSystem:
    """도면 1장의 좌표 시스템 통합 결과."""
    drawing_path: str
    grids: Dict[str, SheetGrid]
    anchors: Dict[str, Anchor]
    transforms: Dict[str, SheetTransform]
    has_grid: bool


def build_coord_system(meta: DrawingMeta) -> CoordSystem:
    """모든 좌표 분석 한 번에."""
    grids = resolve_grid_per_sheet(meta)
    anchors = find_canonical_anchors(meta, grids)
    transforms = align_sheets_within_drawing(anchors)

    return CoordSystem(
        drawing_path=meta.path,
        grids=grids,
        anchors=anchors,
        transforms=transforms,
        has_grid=len(grids) > 0,
    )
