"""
units_detector.py — DXF 단위 자동 검출 (v4 P1.1)
=================================================
$INSUNITS 헤더 우선 → 없으면 bbox 통계 폴백.

[규약]
  - 매직넘버 0건. 모든 thresholds 함수 인자.
  - INSUNITS_MAP은 KS·AutoCAD 표준 (사전지식 OK).
  - 폴백 기본값 'mm' (KS 표준).
"""
from __future__ import annotations

import math
from typing import Literal

# ─────────────────────────────────────────────────────────────
# AutoCAD $INSUNITS 표준 매핑 (사전지식, KS와 동일)
# 0=없음, 1=in, 2=ft, 4=mm, 5=cm, 6=m, 14=dm
# ─────────────────────────────────────────────────────────────

INSUNITS_MAP: dict[int, Literal["mm", "m", "in"]] = {
    1: "in",
    4: "mm",
    5: "mm",   # cm → mm 정규화
    6: "m",
    14: "mm",  # dm → mm 정규화
}

# bbox 폴백 임계값 — 함수 인자 기본값
DEFAULT_MAX_METER_DIAG = 10_000.0   # 10km까지는 m 단위로 본다
DEFAULT_FALLBACK_UNIT  = "mm"


# ─────────────────────────────────────────────────────────────
# bbox 폴백
# ─────────────────────────────────────────────────────────────

def detect_units_from_bbox(
    diag_value: float,
    max_meter_diag: float = DEFAULT_MAX_METER_DIAG,
) -> Literal["mm", "m"]:
    """bbox 대각값 → 단위 추정.

    Args:
        diag_value: bbox 대각 길이 (단위 미정).
        max_meter_diag: 이 이하면 'm', 초과면 'mm'으로 본다.
    """
    if diag_value <= max_meter_diag:
        return "m"
    return "mm"


# ─────────────────────────────────────────────────────────────
# 메인 검출
# ─────────────────────────────────────────────────────────────

def detect_units(doc) -> Literal["mm", "m", "in"]:
    """DXF 문서의 단위 자동 검출.

    우선순위:
        1. $INSUNITS 헤더 (값 ≠ 0)
        2. bbox 대각 통계 (modelspace 엔티티 있을 때)
        3. 기본값 'mm' (KS 표준)
    """
    # 1. $INSUNITS 헤더
    insunits = doc.header.get("$INSUNITS", 0)
    if insunits in INSUNITS_MAP:
        return INSUNITS_MAP[insunits]

    # 2. bbox 폴백
    diag = _model_bbox_diag(doc)
    if diag > 0:
        return detect_units_from_bbox(diag)

    # 3. 기본값
    return DEFAULT_FALLBACK_UNIT


def _model_bbox_diag(doc) -> float:
    """modelspace bbox 대각 길이. 엔티티 없으면 0."""
    msp = doc.modelspace()
    xs: list[float] = []
    ys: list[float] = []
    for e in msp:
        try:
            # LINE
            if e.dxftype() == "LINE":
                xs.extend([e.dxf.start.x, e.dxf.end.x])
                ys.extend([e.dxf.start.y, e.dxf.end.y])
            # POINT
            elif e.dxftype() == "POINT":
                xs.append(e.dxf.location.x)
                ys.append(e.dxf.location.y)
            # 그 외: bbox 추출 시도
            else:
                bbox = e.bbox()  # ezdxf 1.0+
                xs.extend([bbox.extmin.x, bbox.extmax.x])
                ys.extend([bbox.extmin.y, bbox.extmax.y])
        except Exception:
            continue

    if not xs or not ys:
        return 0.0

    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    return math.hypot(dx, dy)
