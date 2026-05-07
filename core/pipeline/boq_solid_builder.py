"""
boq_solid_builder.py — FreeCAD 솔리드 통합 빌더
================================================
v7·v9·v11 빌드 스크립트에 흩어진 솔리드 함수를 단일화.

[설계]
  - 입력 검증 / 기하 계산 = 순수 Python (단위 테스트 가능)
  - FreeCAD 호출 = lazy import (freecadcmd 환경에서만 실행)
  - has_freecad() 로 환경 분기

[제공 함수]
  순수: validate_box_params, validate_prism_params, validate_beam_params
        beam_corner_points
  FreeCAD: box_solid, prism_solid, beam_solid, export_step
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

# ─────────────────────────────────────────────────────────────
# 환경 체크
# ─────────────────────────────────────────────────────────────

def has_freecad() -> bool:
    """FreeCAD 모듈 가용성 확인."""
    try:
        import FreeCAD  # noqa: F401
        import Part     # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────
# 입력 유효성 검증 (순수)
# ─────────────────────────────────────────────────────────────

MIN_DIM_MM = 10.0
MIN_BEAM_LEN_MM = 100.0


def validate_box_params(
    zb: float, zt: float, w: float, h: float
) -> Tuple[bool, str]:
    """기둥/벽 직육면체 파라미터 검증."""
    if zt - zb <= 0:
        return False, f"높이 0 이하 (zb={zb}, zt={zt})"
    if abs(w) < MIN_DIM_MM:
        return False, f"너비 < {MIN_DIM_MM}mm (w={w})"
    if abs(h) < MIN_DIM_MM:
        return False, f"깊이 < {MIN_DIM_MM}mm (h={h})"
    return True, "OK"


def validate_prism_params(
    pts: Sequence[Tuple[float, float]], zb: float, zt: float
) -> Tuple[bool, str]:
    """다각형 압출 파라미터 검증."""
    if zt - zb <= 0:
        return False, f"높이 0 이하"
    if len(pts) < 3:
        return False, f"점 < 3개 ({len(pts)}개)"
    return True, "OK"


def validate_beam_params(
    x0: float, y0: float, x1: float, y1: float,
    bw: float, bh: float, zb: float, zt: float,
) -> Tuple[bool, str]:
    """보 파라미터 검증."""
    length = math.hypot(x1 - x0, y1 - y0)
    if length < MIN_BEAM_LEN_MM:
        return False, f"길이 < {MIN_BEAM_LEN_MM}mm ({length:.1f})"
    if zt - zb <= 0:
        return False, f"높이 0 이하"
    if abs(bw) < MIN_DIM_MM or abs(bh) < MIN_DIM_MM:
        return False, f"단면 크기 부족 (bw={bw}, bh={bh})"
    return True, "OK"


# ─────────────────────────────────────────────────────────────
# 보 4코너 좌표 (순수 기하)
# ─────────────────────────────────────────────────────────────

def beam_corner_points(
    x0: float, y0: float, x1: float, y1: float, bw: float
) -> List[Tuple[float, float]]:
    """보 중심선 → 4코너 점 (단면 너비 bw, 양옆 ±bw/2)."""
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy)
    if ln <= 0:
        return []
    # 중심선의 법선 방향 단위 벡터
    ux, uy = -dy / ln, dx / ln
    half = bw / 2
    return [
        (x0 + ux * half, y0 + uy * half),
        (x1 + ux * half, y1 + uy * half),
        (x1 - ux * half, y1 - uy * half),
        (x0 - ux * half, y0 - uy * half),
    ]


# ─────────────────────────────────────────────────────────────
# FreeCAD 솔리드 함수 (lazy)
# ─────────────────────────────────────────────────────────────

def box_solid(
    cx: float, cy: float, zb: float, zt: float, w: float, h: float
):
    """기둥/벽 직육면체. 중심(cx,cy), 단면 w×h, 높이 zb→zt.

    Returns Part.Shape | None
    """
    if not has_freecad():
        raise RuntimeError("FreeCAD 환경 필요 — freecadcmd로 실행하라")
    ok, msg = validate_box_params(zb, zt, w, h)
    if not ok:
        return None

    import FreeCAD
    import Part

    w, h, ht = abs(w), abs(h), zt - zb
    s = Part.makeBox(w, h, ht, FreeCAD.Vector(cx - w / 2, cy - h / 2, zb))
    return s if s.isValid() else None


def prism_solid(
    pts: Sequence[Tuple[float, float]], zb: float, zt: float
):
    """다각형 압출 솔리드."""
    if not has_freecad():
        raise RuntimeError("FreeCAD 환경 필요 — freecadcmd로 실행하라")
    ok, msg = validate_prism_params(pts, zb, zt)
    if not ok:
        return None

    import FreeCAD
    import Part

    ht = zt - zb
    vv = [FreeCAD.Vector(x, y, zb) for x, y in pts]
    vv.append(FreeCAD.Vector(pts[0][0], pts[0][1], zb))
    try:
        face = Part.makeFace(Part.makePolygon(vv), "Part::FaceMakerBullseye")
        s = face.extrude(FreeCAD.Vector(0, 0, ht))
        return s if s.isValid() else None
    except Exception:
        return None


def beam_solid(
    x0: float, y0: float, x1: float, y1: float,
    bw: float, bh: float, zb: float, zt: float,
):
    """보 솔리드. 중심선(x0,y0)→(x1,y1), 단면 bw×bh, 높이 zb→zt."""
    ok, msg = validate_beam_params(x0, y0, x1, y1, bw, bh, zb, zt)
    if not ok:
        return None
    pts = beam_corner_points(x0, y0, x1, y1, bw)
    return prism_solid(pts, zb, zt)


# ─────────────────────────────────────────────────────────────
# STEP 내보내기 (FreeCAD)
# ─────────────────────────────────────────────────────────────

def export_step(
    shapes_with_names: List[Tuple[object, str]],
    out_path: Union[str, Path],
) -> Path:
    """솔리드 리스트 → STEP 파일.

    Args:
        shapes_with_names: [(Part.Shape, "이름"), ...]
        out_path: 출력 경로
    """
    if not has_freecad():
        raise RuntimeError("FreeCAD 환경 필요 — freecadcmd로 실행하라")

    import FreeCAD
    import Part

    out = Path(out_path)
    doc = FreeCAD.newDocument("BOQExport")
    for shape, name in shapes_with_names:
        if shape is None:
            continue
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
    doc.recompute()
    Part.export([o for o in doc.Objects], str(out))
    FreeCAD.closeDocument(doc.Name)
    return out
