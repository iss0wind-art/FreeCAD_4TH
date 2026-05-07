"""
manifest_resolver.py — Manifest → 절대좌표 부재 (v4 P5)
=========================================================
Manifest의 GridRef → 절대 xy로 변환 + spec lookup.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.manifest_parser import (
    FloorDef,
    GridConfig,
    GridRef,
    ManifestModel,
    MemberInstance,
)


@dataclass
class ResolvedMember:
    """절대좌표 + 사양 채워진 부재."""
    id: str
    type: str             # column / beam / wall / slab / foundation
    spec: str
    floor_id: str
    z_bottom: float       # mm
    z_top: float          # mm

    # 배치 (타입별)
    at_xy: Optional[Tuple[float, float]] = None
    from_xy: Optional[Tuple[float, float]] = None
    to_xy: Optional[Tuple[float, float]] = None
    polygon_xy: Optional[List[Tuple[float, float]]] = None

    # 단면 (spec lookup으로 채움)
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    thickness_mm: Optional[float] = None


def resolve_grid_ref(ref: GridRef, grid: Optional[GridConfig]) -> Tuple[float, float]:
    """GridRef → 절대 xy.

    grid: ["A", "1"] → grid.x_lines["A"] + origin
    xy: [x, y]      → 그대로
    """
    if ref.xy is not None:
        return float(ref.xy[0]), float(ref.xy[1])
    if ref.grid is not None and grid is not None:
        x_key, y_key = ref.grid
        gx = grid.x_lines.get(x_key, 0.0) + grid.origin[0]
        gy = grid.y_lines.get(y_key, 0.0) + grid.origin[1]
        return float(gx), float(gy)
    raise ValueError(f"Cannot resolve {ref}")


def resolve(
    manifest: ManifestModel,
    spec_lookup: Optional[Dict[str, dict]] = None,
) -> List[ResolvedMember]:
    """Manifest → ResolvedMember[].

    Args:
        spec_lookup: {symbol: {width_mm, height_mm, thickness_mm}}
    """
    spec_lookup = spec_lookup or {}

    # 층별 z_base 인덱스
    floor_z: Dict[str, FloorDef] = {f.id: f for f in manifest.floors}

    out: List[ResolvedMember] = []
    for m in manifest.members:
        floor = floor_z.get(m.floor)
        if floor is None:
            continue

        z_bot = floor.z_base + m.z_offset
        z_top = floor.z_base + floor.height + m.z_offset

        # spec 룩업
        spec_dims = spec_lookup.get(m.spec, {})

        rm = ResolvedMember(
            id=m.id,
            type=str(m.type),
            spec=m.spec,
            floor_id=m.floor,
            z_bottom=z_bot,
            z_top=z_top,
            width_mm=spec_dims.get("width_mm"),
            height_mm=spec_dims.get("height_mm"),
            thickness_mm=spec_dims.get("thickness_mm"),
        )

        # 배치
        if m.at is not None:
            rm.at_xy = resolve_grid_ref(m.at, manifest.grid)
        if m.from_ is not None:
            rm.from_xy = resolve_grid_ref(m.from_, manifest.grid)
        if m.to is not None:
            rm.to_xy = resolve_grid_ref(m.to, manifest.grid)
        if m.polygon is not None:
            rm.polygon_xy = [
                resolve_grid_ref(p, manifest.grid) for p in m.polygon
            ]

        out.append(rm)

    return out
