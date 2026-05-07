"""
walls.py — WALL 추출 (v4 P4 #5)
=================================
WALL 레이어 LINE 평행쌍 → 벽 centerline + thickness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from core.v2.algorithms.parallel_pair import (
    Line,
    auto_thickness_thresholds,
    pair_lines,
)


@dataclass
class ExtractedWall:
    """추출된 벽 1개."""
    p0: Tuple[float, float]
    p1: Tuple[float, float]
    thickness_mm: float
    length_mm: float
    layer: str


def extract_walls(
    doc,
    wall_layers: List[str],
    angle_tol_deg: float = 2.0,
    overlap_min_ratio: float = 0.3,
    auto_thresholds: bool = True,
) -> List[ExtractedWall]:
    """WALL 레이어의 LINE 평행쌍 매칭."""
    msp = doc.modelspace()
    wall_layer_set = set(l.upper() for l in wall_layers)

    # 레이어별 LINE 수집
    by_layer: dict[str, List[Line]] = {}
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        layer = e.dxf.layer
        if layer.upper() not in wall_layer_set:
            continue
        ln = Line(
            p0=(float(e.dxf.start.x), float(e.dxf.start.y)),
            p1=(float(e.dxf.end.x), float(e.dxf.end.y)),
        )
        by_layer.setdefault(layer, []).append(ln)

    walls: List[ExtractedWall] = []

    for layer, lines in by_layer.items():
        # 자동 두께 임계값
        if auto_thresholds and len(lines) > 10:
            dist_min, dist_max = auto_thickness_thresholds(lines)
        else:
            dist_min, dist_max = 100.0, 600.0

        pairs = pair_lines(
            lines,
            angle_tol_deg=angle_tol_deg,
            dist_min=dist_min,
            dist_max=dist_max,
            overlap_min_ratio=overlap_min_ratio,
        )

        for pair in pairs:
            cl = pair.centerline
            walls.append(ExtractedWall(
                p0=cl.p0,
                p1=cl.p1,
                thickness_mm=pair.distance,
                length_mm=cl.length,
                layer=layer,
            ))

    return walls
