"""
solid_factory.py — ResolvedMember → FreeCAD Solid (v4 P5)
============================================================
부재 타입별 표준 솔리드 생성.

[규약]
  - FreeCAD lazy import (freecadcmd 환경에서만)
  - 입력 검증 분리 (validate_*)
  - 매직넘버 0건
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from core.v2.build.manifest_resolver import ResolvedMember

# 폴백 단면 (단면 정보 없을 때) — 함수 인자로 노출
DEFAULT_COL_SECTION = (400.0, 400.0)
DEFAULT_BEAM_SECTION = (400.0, 800.0)
DEFAULT_WALL_THICKNESS = 200.0
DEFAULT_SLAB_THICKNESS = 150.0


def has_freecad() -> bool:
    try:
        import FreeCAD  # noqa: F401
        import Part     # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────
# 입력 검증 (순수)
# ─────────────────────────────────────────────────────────────

def validate_column(m: ResolvedMember) -> Tuple[bool, str]:
    if m.at_xy is None:
        return False, "COLUMN: at_xy 누락"
    if m.z_top - m.z_bottom <= 0:
        return False, "COLUMN: 높이 0"
    return True, "OK"


def validate_beam(m: ResolvedMember) -> Tuple[bool, str]:
    if m.from_xy is None or m.to_xy is None:
        return False, "BEAM: from_xy/to_xy 누락"
    L = math.hypot(m.to_xy[0] - m.from_xy[0], m.to_xy[1] - m.from_xy[1])
    if L < 100:
        return False, f"BEAM: 길이 < 100mm ({L:.0f})"
    return True, "OK"


def validate_wall(m: ResolvedMember) -> Tuple[bool, str]:
    if m.polygon_xy is None or len(m.polygon_xy) < 2:
        return False, "WALL: polygon 부족"
    return True, "OK"


def validate_slab(m: ResolvedMember) -> Tuple[bool, str]:
    if m.polygon_xy is None or len(m.polygon_xy) < 3:
        return False, "SLAB: polygon < 3"
    return True, "OK"


# ─────────────────────────────────────────────────────────────
# 솔리드 빌더 (FreeCAD)
# ─────────────────────────────────────────────────────────────

def build_column(m: ResolvedMember,
                 default_section: Tuple[float, float] = DEFAULT_COL_SECTION):
    """COLUMN: at_xy + section → 직육면체."""
    if not has_freecad():
        raise RuntimeError("FreeCAD 환경 필요")
    ok, _ = validate_column(m)
    if not ok:
        return None

    import FreeCAD
    import Part

    w = m.width_mm or default_section[0]
    h = m.height_mm or default_section[1]
    cx, cy = m.at_xy
    ht = m.z_top - m.z_bottom

    s = Part.makeBox(w, h, ht,
                     FreeCAD.Vector(cx - w / 2, cy - h / 2, m.z_bottom))
    return s if s.isValid() else None


def build_beam(m: ResolvedMember,
               default_section: Tuple[float, float] = DEFAULT_BEAM_SECTION):
    """BEAM: from_xy → to_xy + section → 압출."""
    if not has_freecad():
        raise RuntimeError("FreeCAD 환경 필요")
    ok, _ = validate_beam(m)
    if not ok:
        return None

    import FreeCAD
    import Part

    bw = m.width_mm or default_section[0]
    bh = m.height_mm or default_section[1]

    x0, y0 = m.from_xy
    x1, y1 = m.to_xy
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = -dy / L, dx / L

    pts = [
        (x0 + ux * bw / 2, y0 + uy * bw / 2),
        (x1 + ux * bw / 2, y1 + uy * bw / 2),
        (x1 - ux * bw / 2, y1 - uy * bw / 2),
        (x0 - ux * bw / 2, y0 - uy * bw / 2),
    ]
    z_top = m.z_top
    z_bot = m.z_top - bh    # 보 단면 위→아래

    return _prism(pts, z_bot, z_top)


def build_wall(m: ResolvedMember,
               default_thickness: float = DEFAULT_WALL_THICKNESS):
    """WALL: polygon[2] = centerline + thickness → 직육면체."""
    if not has_freecad():
        raise RuntimeError("FreeCAD 환경 필요")
    ok, _ = validate_wall(m)
    if not ok:
        return None

    import FreeCAD
    import Part

    thickness = m.thickness_mm or default_thickness

    p0 = m.polygon_xy[0]
    p1 = m.polygon_xy[1]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < 100:
        return None
    ux, uy = -dy / L, dx / L

    pts = [
        (p0[0] + ux * thickness / 2, p0[1] + uy * thickness / 2),
        (p1[0] + ux * thickness / 2, p1[1] + uy * thickness / 2),
        (p1[0] - ux * thickness / 2, p1[1] - uy * thickness / 2),
        (p0[0] - ux * thickness / 2, p0[1] - uy * thickness / 2),
    ]
    return _prism(pts, m.z_bottom, m.z_top)


def build_slab(m: ResolvedMember,
               default_thickness: float = DEFAULT_SLAB_THICKNESS):
    """SLAB: polygon → extrude."""
    if not has_freecad():
        raise RuntimeError("FreeCAD 환경 필요")
    ok, _ = validate_slab(m)
    if not ok:
        return None

    thickness = m.thickness_mm or default_thickness
    z_top = m.z_top
    z_bot = m.z_top - thickness    # 슬라브 두께만큼 아래로

    return _prism(m.polygon_xy, z_bot, z_top)


def build_foundation(m: ResolvedMember,
                     default_section: Tuple[float, float] = DEFAULT_COL_SECTION):
    """FOUNDATION: column과 동일 방식."""
    return build_column(m, default_section)


def _prism(pts, zb, zt):
    """다각형 압출."""
    import FreeCAD
    import Part

    ht = zt - zb
    if ht <= 0 or len(pts) < 3:
        return None

    vv = [FreeCAD.Vector(x, y, zb) for x, y in pts]
    vv.append(FreeCAD.Vector(pts[0][0], pts[0][1], zb))
    try:
        face = Part.makeFace(Part.makePolygon(vv), "Part::FaceMakerBullseye")
        s = face.extrude(FreeCAD.Vector(0, 0, ht))
        return s if s.isValid() else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# 디스패처
# ─────────────────────────────────────────────────────────────

def build_member_solid(m: ResolvedMember):
    """타입별 디스패처."""
    t = m.type.lower()
    if t == "column":
        return build_column(m)
    if t == "beam":
        return build_beam(m)
    if t == "wall":
        return build_wall(m)
    if t == "slab":
        return build_slab(m)
    if t == "foundation":
        return build_foundation(m)
    return None
