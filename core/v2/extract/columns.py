"""
columns.py — COLUMN 추출 (v4 P4 #4)
=====================================
LWPOLYLINE 닫힌 작은 polygon → bbox → COLUMN 인스턴스.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from core.v2.classify.ks_lexicon import MemberType
from core.v2.extract.section_text import SectionSpec


@dataclass
class ExtractedColumn:
    """추출된 기둥 1개."""
    cx: float
    cy: float
    width_mm: float
    height_mm: float
    layer: str
    section_symbol: Optional[str] = None


def extract_columns(
    doc,
    column_layers: List[str],
    min_size_mm: float = 100.0,
    max_size_mm: float = 2500.0,
) -> List[ExtractedColumn]:
    """COLUMN 레이어의 닫힌 LWPOLYLINE → 기둥.

    Args:
        column_layers: 분류기가 COLUMN으로 판별한 레이어 목록
        min_size_mm/max_size_mm: 단면 크기 필터
    """
    msp = doc.modelspace()
    column_layer_set = set(l.upper() for l in column_layers)
    columns: List[ExtractedColumn] = []

    for e in msp:
        if e.dxftype() != "LWPOLYLINE":
            continue
        if not e.is_closed:
            continue
        if e.dxf.layer.upper() not in column_layer_set:
            continue

        try:
            pts = [(p[0], p[1]) for p in e.get_points()]
        except Exception:
            continue
        if len(pts) < 3:
            continue

        xmin = min(p[0] for p in pts)
        xmax = max(p[0] for p in pts)
        ymin = min(p[1] for p in pts)
        ymax = max(p[1] for p in pts)
        w = xmax - xmin
        h = ymax - ymin

        if not (min_size_mm <= w <= max_size_mm and
                min_size_mm <= h <= max_size_mm):
            continue

        columns.append(ExtractedColumn(
            cx=(xmin + xmax) / 2,
            cy=(ymin + ymax) / 2,
            width_mm=w,
            height_mm=h,
            layer=e.dxf.layer,
        ))

    return columns
