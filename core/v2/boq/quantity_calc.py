"""
quantity_calc.py — BOQ 수량 계산 (v4 P6)
==========================================
ResolvedMember → 체적 / 면적 / 거푸집.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from core.v2.build.manifest_resolver import ResolvedMember


@dataclass
class Quantity:
    """단일 부재 수량."""
    member_id: str
    type: str
    volume_m3: float = 0.0
    area_m2: float = 0.0
    formwork_m2: float = 0.0
    length_m: float = 0.0


def compute_quantity(m: ResolvedMember) -> Quantity:
    """타입별 수량 계산."""
    t = m.type.lower()

    if t == "column":
        return _column_qty(m)
    if t == "beam":
        return _beam_qty(m)
    if t == "wall":
        return _wall_qty(m)
    if t == "slab":
        return _slab_qty(m)
    if t == "foundation":
        return _foundation_qty(m)

    return Quantity(member_id=m.id, type=t)


def _column_qty(m: ResolvedMember) -> Quantity:
    w = (m.width_mm or 400) / 1000
    h = (m.height_mm or 400) / 1000
    height = (m.z_top - m.z_bottom) / 1000
    vol = w * h * height
    perimeter = 2 * (w + h)
    return Quantity(
        member_id=m.id, type="column",
        volume_m3=round(vol, 4),
        formwork_m2=round(perimeter * height, 3),
    )


def _beam_qty(m: ResolvedMember) -> Quantity:
    if m.from_xy is None or m.to_xy is None:
        return Quantity(member_id=m.id, type="beam")
    L = math.hypot(m.to_xy[0] - m.from_xy[0], m.to_xy[1] - m.from_xy[1]) / 1000
    bw = (m.width_mm or 400) / 1000
    bh = (m.height_mm or 800) / 1000
    vol = L * bw * bh
    return Quantity(
        member_id=m.id, type="beam",
        volume_m3=round(vol, 4),
        length_m=round(L, 3),
        formwork_m2=round((2 * bh + bw) * L, 3),    # 양옆 + 하부
    )


def _wall_qty(m: ResolvedMember) -> Quantity:
    if m.polygon_xy is None or len(m.polygon_xy) < 2:
        return Quantity(member_id=m.id, type="wall")
    p0, p1 = m.polygon_xy[0], m.polygon_xy[1]
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 1000
    thk = (m.thickness_mm or 200) / 1000
    height = (m.z_top - m.z_bottom) / 1000
    vol = L * thk * height
    area = L * height
    return Quantity(
        member_id=m.id, type="wall",
        volume_m3=round(vol, 4),
        area_m2=round(area, 3),
        length_m=round(L, 3),
        formwork_m2=round(2 * area, 3),    # 양면
    )


def _slab_qty(m: ResolvedMember) -> Quantity:
    if m.polygon_xy is None or len(m.polygon_xy) < 3:
        return Quantity(member_id=m.id, type="slab")
    pts = m.polygon_xy
    n = len(pts)
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    area = abs(s) / 2 / 1_000_000   # mm² → m²
    thk = (m.thickness_mm or 150) / 1000
    return Quantity(
        member_id=m.id, type="slab",
        area_m2=round(area, 3),
        volume_m3=round(area * thk, 4),
        formwork_m2=round(area, 3),    # 하부 면만
    )


def _foundation_qty(m: ResolvedMember) -> Quantity:
    return _column_qty(m)._replace(type="foundation") if hasattr(_column_qty(m), '_replace') else Quantity(
        member_id=m.id, type="foundation",
        volume_m3=_column_qty(m).volume_m3,
        formwork_m2=_column_qty(m).formwork_m2,
    )
