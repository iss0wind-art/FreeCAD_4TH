"""
그리드 → 절대 좌표 어댑터 — Phase 1 Track E

ManifestModel의 각 MemberInstance를 기존 MemberInputDTO 형식으로 변환.
그리드 참조 → mm 절대 좌표 → 단면 폴리곤 생성.
"""

from __future__ import annotations

import math
from typing import Optional

from core.manifest_parser import (
    FloorDef,
    GridConfig,
    GridRef,
    ManifestModel,
    MemberInstance,
)


# ─────────────────────────────────────────────────────────────
# 그리드 참조 → 절대 좌표
# ─────────────────────────────────────────────────────────────
def resolve_at(ref: GridRef, grid: Optional[GridConfig]) -> tuple[float, float]:
    """GridRef → (x, y) mm 절대 좌표."""
    if ref.xy is not None:
        return float(ref.xy[0]), float(ref.xy[1])

    if grid is None:
        raise ValueError("grid 참조를 사용하려면 ManifestModel에 grid 설정이 필요합니다")

    x_key, y_key = ref.grid  # type: ignore[misc]
    local_x = grid.x_lines[x_key]
    local_y = grid.y_lines[y_key]

    if grid.rotation == 0:
        ox, oy = grid.origin
        return ox + local_x, oy + local_y

    rad = math.radians(grid.rotation)
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    ox, oy = grid.origin
    rx = cos_r * local_x - sin_r * local_y
    ry = sin_r * local_x + cos_r * local_y
    return ox + rx, oy + ry


# ─────────────────────────────────────────────────────────────
# 단면 폴리곤 생성
# ─────────────────────────────────────────────────────────────
def _column_polygon(cx: float, cy: float, width: float, height: float,
                    rotation: float) -> list[list[float]]:
    """기둥 중심 + 단면 치수 → 4점 사각형 (회전 반영)."""
    hw, hh = width / 2, height / 2
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]

    if rotation != 0:
        rad = math.radians(rotation)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        corners = [
            (cos_r * x - sin_r * y, sin_r * x + cos_r * y)
            for x, y in corners
        ]

    return [[cx + dx, cy + dy] for dx, dy in corners]


def _beam_polygon(x0: float, y0: float, x1: float, y1: float,
                  width: float) -> list[list[float]]:
    """보 시작-끝점 + 폭 → 4점 사각형 (보 방향 수직으로 폭 분배)."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError("보의 from/to 좌표가 동일합니다 (길이 0)")

    ux, uy = dx / length, dy / length  # 단위 벡터
    px, py = -uy * width / 2, ux * width / 2  # 수직 오프셋

    return [
        [x0 + px, y0 + py],
        [x1 + px, y1 + py],
        [x1 - px, y1 - py],
        [x0 - px, y0 - py],
    ]


# ─────────────────────────────────────────────────────────────
# MemberInstance → MemberInputDTO dict
# ─────────────────────────────────────────────────────────────
_COLUMN_SPEC_DEFAULTS = {"width": 500.0, "height": 500.0, "depth": 4000.0}
_BEAM_SPEC_DEFAULTS = {"width": 300.0, "height": 600.0}


def resolve_member_to_input(
    instance: MemberInstance,
    floors: list[FloorDef],
    grid: Optional[GridConfig],
    spec_map: Optional[dict[str, dict]] = None,
) -> dict:
    """
    MemberInstance → MemberInputDTO 호환 dict.

    spec_map: {symbol: {width, height, depth, thickness, ...}} — DB 조회 결과.
    None 이면 기본값 사용.
    """
    floor = _find_floor(instance.floor, floors)
    spec = (spec_map or {}).get(instance.spec, {})
    z_base = floor.z_base + instance.z_offset

    if instance.type == "column":
        return _resolve_column(instance, spec, z_base, grid)
    elif instance.type == "beam":
        return _resolve_beam(instance, spec, z_base, grid, floor)
    else:
        raise NotImplementedError(
            f"Phase 1 미지원 부재 타입: {instance.type!r} (Phase 2+)"
        )


def _find_floor(floor_id: str, floors: list[FloorDef]) -> FloorDef:
    for f in floors:
        if f.id == floor_id:
            return f
    raise KeyError(f"floor_id={floor_id!r} 를 찾을 수 없습니다")


def _resolve_column(
    inst: MemberInstance,
    spec: dict,
    z_base: float,
    grid: Optional[GridConfig],
) -> dict:
    assert inst.at is not None
    cx, cy = resolve_at(inst.at, grid)
    width = float(spec.get("width") or _COLUMN_SPEC_DEFAULTS["width"])
    depth = float(spec.get("height") or _COLUMN_SPEC_DEFAULTS["height"])
    height_mm = float(spec.get("depth") or _COLUMN_SPEC_DEFAULTS["depth"])

    vertices = _column_polygon(cx, cy, width, depth, inst.rotation)

    return {
        "member_id": inst.id,
        "member_type": "COLUMN",
        "vertices_2d": vertices,
        "height": height_mm,
        "z_base": z_base,
    }


def _resolve_beam(
    inst: MemberInstance,
    spec: dict,
    z_base: float,
    grid: Optional[GridConfig],
    floor: FloorDef,
) -> dict:
    assert inst.from_ is not None and inst.to is not None
    x0, y0 = resolve_at(inst.from_, grid)
    x1, y1 = resolve_at(inst.to, grid)
    width = float(spec.get("width") or _BEAM_SPEC_DEFAULTS["width"])
    depth = float(spec.get("height") or _BEAM_SPEC_DEFAULTS["height"])

    vertices = _beam_polygon(x0, y0, x1, y1, width)

    return {
        "member_id": inst.id,
        "member_type": "BEAM",
        "vertices_2d": vertices,
        "height": depth,
        "z_base": z_base,
    }


# ─────────────────────────────────────────────────────────────
# 매니페스트 전체 → MemberInputDTO list
# ─────────────────────────────────────────────────────────────
def resolve_all(
    manifest: ManifestModel,
    spec_map: Optional[dict[str, dict]] = None,
) -> list[dict]:
    """지원 부재(column, beam)만 변환. 나머지는 스킵 + 경고."""
    results = []
    for inst in manifest.members:
        if inst.type not in ("column", "beam"):
            continue
        results.append(
            resolve_member_to_input(inst, manifest.floors, manifest.grid, spec_map)
        )
    return results
