"""
step_zone.py — 단차(SL 변화) 구역 파싱 + 3D 적용
====================================================
도면에 표기된 "B2F SL +1600", "B2F SL-1.8" 등을
3D 모델의 실제 바닥 높이 변화로 반영한다.

[단차의 의미]
  "B2F SL +1600" = 이 구역의 B2F 바닥이 B2F 기준 SL보다 1600mm 높음
  절대 SL = -9050 + 1600 = -7450mm

[사용]
  zones = parse_step_zones(dong_dxf, clip)
  zone_at = StepZoneMap(zones)
  actual_z = zone_at.slab_z(x, y, 'B2F')  # 해당 위치의 실제 SL
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

import ezdxf

from core.dxf_parser.entity_scanner import iter_all


# ─────────────────────────────────────────────────────────────
# 자료구조
# ─────────────────────────────────────────────────────────────

@dataclass
class StepZone:
    """단차 구역 — 특정 위치의 SL 변화 (기존 점/반경 기반)."""
    x: float
    y: float
    floor_label: str        # 'B2F', 'B1F' 등
    delta_mm: float         # 기준 SL 대비 변화량 (mm)
    text: str = ''          # 원본 텍스트
    radius_mm: float = 5000.0  # 영향 반경 (기본 5m)

    def absolute_sl(self, base_sl: dict) -> Optional[float]:
        """절대 SL = 기준 SL + delta."""
        base = base_sl.get(self.floor_label)
        if base is None:
            return None
        return base + self.delta_mm


@dataclass
class PolygonStepZone:
    """다각형 영역 기반 단차 구역 (위상수학적 센트로이드 바인딩)."""
    pts: List[Tuple[float, float]]  # 다각형 꼭짓점 좌표 목록
    floor_label: str
    delta_mm: float
    text: str = ''

    def absolute_sl(self, base_sl: dict) -> Optional[float]:
        """절대 SL = 기준 SL + delta."""
        base = base_sl.get(self.floor_label)
        if base is None:
            return None
        return base + self.delta_mm


@dataclass
class StepZoneMap:
    """단차 구역 집합 — 임의 점의 SL 조회."""
    zones: List[StepZone] = field(default_factory=list)
    polygon_zones: List[PolygonStepZone] = field(default_factory=list)
    base_sl: dict = field(default_factory=dict)  # 층 기준 SL

    def slab_z(self, x: float, y: float, floor_label: str) -> float:
        """(x, y) 위치의 실제 SL. 단차 구역 없으면 기준 SL 반환."""
        best_z = self.base_sl.get(floor_label, 0.0)
        best_dist = float('inf')

        # 1. 다각형 영역 검사 (위상수학적 Centroid-in-Polygon 매핑 우선)
        from shapely.geometry import Polygon, Point
        pt = Point(x, y)
        for pzone in self.polygon_zones:
            if pzone.floor_label != floor_label:
                continue
            try:
                poly = Polygon(pzone.pts)
                if poly.contains(pt):
                    abs_sl = pzone.absolute_sl(self.base_sl)
                    if abs_sl is not None:
                        return abs_sl
            except Exception:
                pass

        # 2. 폴백: 기존 점/반경 기반 매핑 검사
        for zone in self.zones:
            if zone.floor_label != floor_label:
                continue
            dist = ((x - zone.x)**2 + (y - zone.y)**2) ** 0.5
            if dist < zone.radius_mm and dist < best_dist:
                abs_sl = zone.absolute_sl(self.base_sl)
                if abs_sl is not None:
                    best_z = abs_sl
                    best_dist = dist

        return best_z

    def summary(self) -> str:
        by_floor: dict = {}
        for z in self.zones:
            by_floor.setdefault(z.floor_label, []).append(z.delta_mm)
        for pz in self.polygon_zones:
            by_floor.setdefault(pz.floor_label, []).append(pz.delta_mm)
            
        lines = [f'[StepZoneMap] 다각형 구역 {len(self.polygon_zones)}개 · 점 구역 {len(self.zones)}개']
        for fl, deltas in sorted(by_floor.items()):
            unique = sorted(set(round(d) for d in deltas))
            lines.append(f'  {fl}: {unique}mm 변화 ({len(deltas)}건)')
        return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────
# 파싱 패턴
# ─────────────────────────────────────────────────────────────

_STEP_TEXT_PAT = re.compile(
    r'(B[123]?F)\s+SL\s*([+\-][\d\.]+)',
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────
# 파싱
# ─────────────────────────────────────────────────────────────

def parse_step_zones(dxf_path: str, encoding: str = 'cp949',
                     clip: Optional[Tuple[float,float,float,float]] = None,
                     base_sl: Optional[dict] = None) -> StepZoneMap:
    """도면에서 단차 구역 파싱.

    Args:
        dxf_path: DXF 파일 경로
        clip: 검색 영역 제한
        base_sl: 층별 기준 SL (예: {'B2F': -9050, 'B1F': -5600})

    Returns:
        StepZoneMap
    """
    if base_sl is None:
        base_sl = {'B2F': -9050.0, 'B1F': -5600.0, '1F': 370.0}

    from core.dxf_parser.encoding_helper import safe_read_dxf
    doc = safe_read_dxf(dxf_path, default_encoding=encoding)
    msp = doc.modelspace()
    
    zones = []
    polygon_zones = []
    
    # 1. 닫힌 LWPOLYLINE (단차 영역 경계선) 수집
    from shapely.geometry import Polygon, Point
    step_layer_pat = re.compile(r'STEP|단차|LEVEL|SLAB', re.IGNORECASE)
    boundaries = []
    
    for e in iter_all(msp):
        if e.dxftype() == 'LWPOLYLINE':
            try:
                layer = e.dxf.layer
                if not step_layer_pat.search(layer):
                    continue
                pts = [(p[0], p[1]) for p in e.get_points()]
                if not pts:
                    continue
                if clip:
                    if not all(clip[0] <= p[0] <= clip[2] and clip[1] <= p[1] <= clip[3] for p in pts):
                        continue
                if e.is_closed and len(pts) >= 3:
                    boundaries.append((Polygon(pts), pts))
            except Exception:
                pass

    # 2. 텍스트 파싱하여 텍스트 위치를 다각형 영역과 센트로이드 바인딩 검사
    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if not txt or len(txt) > 60:
                continue
            pos = e.dxf.insert
            if clip and not (clip[0] <= pos.x <= clip[2] and
                             clip[1] <= pos.y <= clip[3]):
                continue
            m = _STEP_TEXT_PAT.search(txt)
            if not m:
                continue
            floor_label = m.group(1).upper()
            raw_delta = m.group(2).replace(' ', '')
            try:
                delta_val = float(raw_delta)
                if abs(delta_val) < 100 and '.' in raw_delta:
                    delta_mm = delta_val * 1000
                else:
                    delta_mm = delta_val
            except ValueError:
                continue

            if abs(delta_mm) < 50:
                continue

            # (x, y) 좌표가 어떤 경계 폴리곤에 포함되는지 확인 (Centroid-in-Polygon 검증)
            pt = Point(pos.x, pos.y)
            matched_poly_pts = None
            for poly, pts in boundaries:
                if poly.contains(pt):
                    matched_poly_pts = pts
                    break
            
            if matched_poly_pts:
                # 다각형 기반 단차 구역으로 등록
                polygon_zones.append(PolygonStepZone(
                    pts=matched_poly_pts,
                    floor_label=floor_label,
                    delta_mm=delta_mm,
                    text=txt
                ))
            else:
                # 폴리곤 매칭 실패 시 기존의 점 기반(반경) 단차 구역으로 등록
                zones.append(StepZone(
                    x=pos.x, y=pos.y,
                    floor_label=floor_label,
                    delta_mm=delta_mm,
                    text=txt,
                ))
        except Exception:
            pass

    return StepZoneMap(zones=zones, polygon_zones=polygon_zones, base_sl=base_sl)
