"""
walls.py — WALL 추출 (v4 P4 #5)
=================================
WALL 레이어 LINE 평행쌍 → 벽 centerline + thickness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from core.v2.io.dxf_loader import get_flattened_entities
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
    """WALL 레이어의 LINE/LWPOLYLINE 평행쌍 매칭 (블록 내부 포함, 폴리라인 분해)."""
    wall_layer_set = set(l.upper() for l in wall_layers)

    # 블록 내부까지 포함하여 LINE과 POLYLINE 수집
    all_ents = get_flattened_entities(
        doc, 
        target_layers=wall_layer_set, 
        target_types={"LINE", "LWPOLYLINE", "POLYLINE"}
    )

    # 레이어별 분류 (폴리라인은 선분으로 분해)
    by_layer: dict[str, List[Line]] = {}
    for e in all_ents:
        layer = e.dxf.layer
        et = e.dxftype()
        if et == "LINE":
            ln = Line(
                p0=(float(e.dxf.start.x), float(e.dxf.start.y)),
                p1=(float(e.dxf.end.x), float(e.dxf.end.y)),
            )
            by_layer.setdefault(layer, []).append(ln)
        elif et in ("LWPOLYLINE", "POLYLINE"):
            try:
                pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
                if len(pts) > 1:
                    for i in range(len(pts) - 1):
                        ln = Line(p0=pts[i], p1=pts[i+1])
                        by_layer.setdefault(layer, []).append(ln)
                    # 닫힌 폴리라인이면 마지막-첫번째 점 연결
                    if e.is_closed:
                        ln = Line(p0=pts[-1], p1=pts[0])
                        by_layer.setdefault(layer, []).append(ln)
            except Exception:
                pass

    walls: List[ExtractedWall] = []

    for layer, lines in by_layer.items():
        # 너무 짧은 선분 필터링 (노이즈 방지)
        valid_lines = [ln for ln in lines if ln.length > 50.0]
        
        # 자동 두께 임계값
        if auto_thresholds and len(valid_lines) > 10:
            dist_min, dist_max = auto_thickness_thresholds(valid_lines)
        else:
            dist_min, dist_max = 100.0, 600.0

        pairs = pair_lines(
            valid_lines,
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
