"""
foundations.py — FOUNDATION 추출 (v4 P4 #8)
=============================================
FND 레이어 polygon → 기초.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class ExtractedFoundation:
    """추출된 기초 1개."""
    cx: float
    cy: float
    width_mm: float
    height_mm: float
    polygon: List[Tuple[float, float]]
    area_m2: float
    layer: str


def extract_foundations(
    doc,
    fnd_layers: List[str],
    min_size_mm: float = 200.0,
) -> List[ExtractedFoundation]:
    """FOUNDATION 레이어 polygon → 기초."""
    msp = doc.modelspace()
    fnd_layer_set = set(l.upper() for l in fnd_layers)

    fnds: List[ExtractedFoundation] = []

    for e in msp:
        if e.dxftype() != "LWPOLYLINE":
            continue
        if e.dxf.layer.upper() not in fnd_layer_set:
            continue
        try:
            pts = [(p[0], p[1]) for p in e.get_points()]
        except Exception:
            continue
        if len(pts) < 3:
            continue

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        if w < min_size_mm or h < min_size_mm:
            continue

        area_m2 = _shoelace(pts) / 1_000_000.0

        fnds.append(ExtractedFoundation(
            cx=(min(xs) + max(xs)) / 2,
            cy=(min(ys) + max(ys)) / 2,
            width_mm=w,
            height_mm=h,
            polygon=pts,
            area_m2=area_m2,
            layer=e.dxf.layer,
        ))

    return fnds


def _shoelace(pts: List[Tuple[float, float]]) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0
