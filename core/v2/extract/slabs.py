"""
slabs.py — SLAB 추출 (v4 P4 #7)
=================================
SLAB 레이어 LWPOLYLINE 닫힌 polygon → 슬라브.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class ExtractedSlab:
    """추출된 슬라브 1개."""
    polygon: List[Tuple[float, float]]
    area_m2: float
    thickness_mm: float       # 폴백 또는 추정
    layer: str


def extract_slabs(
    doc,
    slab_layers: List[str],
    default_thickness_mm: float = 150.0,
    min_area_m2: float = 0.1,
) -> List[ExtractedSlab]:
    """SLAB 레이어 LWPOLYLINE → 슬라브.

    self-crossing 폴리곤은 각도 정렬로 보정.
    """
    msp = doc.modelspace()
    slab_layer_set = set(l.upper() for l in slab_layers)

    slabs: List[ExtractedSlab] = []

    for e in msp:
        if e.dxftype() != "LWPOLYLINE":
            continue
        if e.dxf.layer.upper() not in slab_layer_set:
            continue
        try:
            pts = [(p[0], p[1]) for p in e.get_points()]
        except Exception:
            continue
        if len(pts) < 3:
            continue

        # Shoelace 면적 (절대값)
        area = _shoelace_area(pts)

        # self-crossing이면 각도 정렬
        if area < 100.0:    # mm² 단위, 비정상적으로 작음
            pts = _reorder_by_angle(pts)
            area = _shoelace_area(pts)

        area_m2 = area / 1_000_000.0
        if area_m2 < min_area_m2:
            continue

        slabs.append(ExtractedSlab(
            polygon=pts,
            area_m2=area_m2,
            thickness_mm=default_thickness_mm,
            layer=e.dxf.layer,
        ))

    return slabs


def _shoelace_area(pts: List[Tuple[float, float]]) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _reorder_by_angle(pts: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
