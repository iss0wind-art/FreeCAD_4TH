"""
slabs.py — SLAB 추출 (v4 P4 #7)
=================================
SLAB 레이어 LWPOLYLINE 닫힌 polygon → 슬라브.

[라벨 매칭]
  평면도 슬라브 영역 안에 'A', 'B', 'S1' 같은 라벨이 있으면
  슬라브 일람표(catalog)에서 두께 lookup. 없으면 default 폴백.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


_SLAB_LABEL_PAT = re.compile(r"^([A-H]|S\d+|SL\d+|F\d+)$", re.IGNORECASE)


@dataclass
class ExtractedSlab:
    """추출된 슬라브 1개."""
    polygon: List[Tuple[float, float]]
    area_m2: float
    thickness_mm: float       # 폴백 또는 카탈로그 매칭값
    layer: str
    section_symbol: Optional[str] = None   # 매칭된 라벨 (e.g., 'A', 'S1')
    matched_from_catalog: bool = False     # True면 두께가 카탈로그 출처


def extract_slabs(
    doc,
    slab_layers: List[str],
    default_thickness_mm: float = 150.0,
    min_area_m2: float = 0.1,
    label_positions: Optional[List[Tuple[str, float, float]]] = None,
    slab_catalog: Optional[Dict[str, float]] = None,
) -> List[ExtractedSlab]:
    """SLAB 레이어 LWPOLYLINE → 슬라브.

    Args:
        slab_layers: 슬라브 레이어 목록
        default_thickness_mm: 라벨 매칭 실패 시 폴백 두께
        min_area_m2: 최소 면적 (m²)
        label_positions: 평면도 텍스트 [(text, x, y), ...] — 슬라브 라벨 후보
        slab_catalog: {label: thickness_mm} — 일람표 카탈로그
    """
    msp = doc.modelspace()
    slab_layer_set = set(l.upper() for l in slab_layers)

    # 슬라브 라벨 후보 필터링
    slab_label_candidates: List[Tuple[str, float, float]] = []
    if label_positions:
        for text, x, y in label_positions:
            t = (text or "").strip()
            if _SLAB_LABEL_PAT.match(t):
                slab_label_candidates.append((t, x, y))

    catalog = slab_catalog or {}

    slabs: List[ExtractedSlab] = []

    for e in msp:
        if e.dxftype() != "LWPOLYLINE":
            continue
        if e.dxf.layer.upper() not in slab_layer_set:
            continue
        try:
            pts = [(p[0], p[1]) for p in e.get_points()]
        except Exception:
            continue
        if len(pts) < 3:
            continue

        # Shoelace 면적 (절대값)
        area = _shoelace_area(pts)

        # self-crossing이면 각도 정렬
        if area < 100.0:    # mm² 단위, 비정상적으로 작음
            pts = _reorder_by_angle(pts)
            area = _shoelace_area(pts)

        area_m2 = area / 1_000_000.0
        if area_m2 < min_area_m2:
            continue

        # 라벨 매칭 — polygon 안의 라벨 중 카탈로그 매칭이 우선
        symbol, thickness, matched = _match_label_for_slab(
            pts, slab_label_candidates, catalog,
        )

        slabs.append(ExtractedSlab(
            polygon=pts,
            area_m2=area_m2,
            thickness_mm=thickness if matched else default_thickness_mm,
            layer=e.dxf.layer,
            section_symbol=symbol,
            matched_from_catalog=matched,
        ))

    return slabs


def _match_label_for_slab(
    polygon: List[Tuple[float, float]],
    label_candidates: List[Tuple[str, float, float]],
    catalog: Dict[str, float],
) -> Tuple[Optional[str], float, bool]:
    """폴리곤 안의 라벨 중 카탈로그 매칭 우선 선택.

    Returns:
        (symbol, thickness_mm, matched_from_catalog)
        매칭 실패 시 (None, 0.0, False)
    """
    inside = [
        (lab, lx, ly) for (lab, lx, ly) in label_candidates
        if _point_in_polygon(lx, ly, polygon)
    ]
    if not inside:
        return None, 0.0, False

    # 카탈로그 매칭 우선
    for lab, _, _ in inside:
        if lab in catalog:
            return lab, float(catalog[lab]), True
        upper = lab.upper()
        if upper in catalog:
            return upper, float(catalog[upper]), True

    # 카탈로그 미매칭이지만 라벨은 있음 → 심볼만 반환
    return inside[0][0], 0.0, False


def _point_in_polygon(x: float, y: float,
                      polygon: List[Tuple[float, float]]) -> bool:
    """ray casting (홀수 교차 → 내부)."""
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)):
            xint = xi + (y - yi) * (xj - xi) / (yj - yi + 1e-12)
            if x < xint:
                inside = not inside
        j = i
    return inside


def _shoelace_area(pts: List[Tuple[float, float]]) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _reorder_by_angle(pts: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
