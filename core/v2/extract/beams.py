"""
beams.py — BEAM 추출 (v4 P4 #6)
=================================
BEAM 레이어 LINE → 보 centerline + 단면 라벨 매칭.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class ExtractedBeam:
    """추출된 보 1개."""
    p0: Tuple[float, float]
    p1: Tuple[float, float]
    length_mm: float
    angle_deg: float
    layer: str
    section_symbol: Optional[str] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None


def extract_beams(
    doc,
    beam_layers: List[str],
    section_specs: Optional[Dict] = None,    # {symbol: SectionSpec}
    section_label_positions: Optional[List[Tuple[str, float, float]]] = None,
    label_match_radius_mm: float = 1500.0,
    min_length_mm: float = 300.0,
) -> List[ExtractedBeam]:
    """BEAM 레이어 LINE → 보."""
    msp = doc.modelspace()
    beam_layer_set = set(l.upper() for l in beam_layers)

    beams: List[ExtractedBeam] = []
    section_specs = section_specs or {}
    label_positions = section_label_positions or []

    for e in msp:
        if e.dxftype() != "LINE":
            continue
        if e.dxf.layer.upper() not in beam_layer_set:
            continue

        x0 = float(e.dxf.start.x)
        y0 = float(e.dxf.start.y)
        x1 = float(e.dxf.end.x)
        y1 = float(e.dxf.end.y)
        L = math.hypot(x1 - x0, y1 - y0)

        if L < min_length_mm:
            continue

        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))

        # 단면 라벨 매칭 (보 중점에서 가장 가까운 라벨)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        symbol = _find_nearest_label(cx, cy, label_positions, label_match_radius_mm)
        spec = section_specs.get(symbol) if symbol else None

        beams.append(ExtractedBeam(
            p0=(x0, y0),
            p1=(x1, y1),
            length_mm=L,
            angle_deg=ang,
            layer=e.dxf.layer,
            section_symbol=symbol,
            width_mm=spec.width_mm if spec else None,
            height_mm=spec.height_mm if spec else None,
        ))

    return beams


def _find_nearest_label(
    x: float, y: float,
    label_positions: List[Tuple[str, float, float]],
    radius_mm: float,
) -> Optional[str]:
    """주어진 점에서 radius 내 가장 가까운 라벨."""
    best_label = None
    best_d2 = radius_mm ** 2
    for text, lx, ly in label_positions:
        d2 = (x - lx) ** 2 + (y - ly) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_label = text
    return best_label
