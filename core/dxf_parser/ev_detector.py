"""
ev_detector.py — E/V 코어 기준점 실제 검출기
=============================================
f1_anchor_aligner.EVDetector 프로토콜 구현체.

[F-1 패턴 핵심]
방부장 친전: "동의 경우 E/V는 꼭대기까지 변하지 않는 곳이라,
 거기 모서리 중 하나를 기준점으로 잡는다."

[검출 전략 (우선순위 순)]
  a. TEXT 라벨: 'EV', 'ELEV', '엘리베이터', '승강기'
  b. 레이어 패턴: 'A-EV', 'CORE', 'S-CORE'
  c. 격자 교점 (Grid): X1·Y1 교점 = 건물 SW 모서리
  d. 수동 지정 (Manual): 폴백

[좌표계 규약]
SW(좌하단) 모서리를 기준점으로 — CAD 관습과 동일.
모든 변환은 이 점이 (0,0)이 되도록 평행이동.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple

import ezdxf

from core.f1_anchor_aligner import EVAnchor
from core.dxf_parser.entity_scanner import iter_all


# ─────────────────────────────────────────────────────────────
# 패턴 상수
# ─────────────────────────────────────────────────────────────

_EV_TEXT = re.compile(
    r'E/?V\b|ELEV|승강기|엘리베이터|ELEVATOR|LIFT|계단실|STAIR\s*HALL',
    re.IGNORECASE,
)
_EV_LAYER = re.compile(
    r'A[-_]?EV|EV[-_]CORE|S[-_]?CORE|승강|STAIR|ELEV|E_V',
    re.IGNORECASE,
)
_GRID_X1 = re.compile(r'^X\s*1$|^[Aa]\s*$|^①$', re.IGNORECASE)
_GRID_Y1 = re.compile(r'^Y\s*1$|^1\s*$|^①$', re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# 기준점 자료구조
# ─────────────────────────────────────────────────────────────

@dataclass
class AnchorPoint:
    """단일 기준점."""
    x: float
    y: float
    label: str = ""
    strategy: str = ""
    confidence: float = 1.0


# ─────────────────────────────────────────────────────────────
# E/V 코어 TEXT 기반 검출기
# ─────────────────────────────────────────────────────────────

class TextLabelEVDetector:
    """전략 a+b: TEXT 라벨 + 레이어 패턴 조합.

    1. EV TEXT 또는 EV 레이어 엔티티에서 후보점 수집
    2. 후보점 클러스터링 → 중심
    3. 중심 주변 HATCH/SOLID/LWPOLYLINE BBox → SW 모서리 = 기준점
    """

    def __init__(self,
                 dong_clip: Optional[Tuple[float,float,float,float]] = None,
                 search_radius_mm: float = 8000.0):
        """
        dong_clip: (xmin,ymin,xmax,ymax) 동 영역 제한 (None=전체 도면)
        search_radius_mm: EV TEXT 주변 BBox 검색 반경 (기본 8m)
        """
        self.clip = dong_clip
        self.radius = search_radius_mm

    def detect(self, dxf_doc, dong: str = '', floor: object = 0,
               sheet_id: str = '') -> Optional[EVAnchor]:
        """EVAnchor 반환. 검출 실패 시 None."""
        msp = dxf_doc.modelspace()
        candidates: List[Tuple[float, float, float]] = []  # (x, y, conf)

        for e in iter_all(msp):
            t = e.dxftype()
            conf = 0.0
            px = py = None

            if t in ('TEXT', 'MTEXT'):
                try:
                    txt = (e.dxf.text if t == 'TEXT' else e.text).strip()
                    if _EV_TEXT.search(txt):
                        pos = e.dxf.insert
                        px, py = pos.x, pos.y
                        conf = 0.85
                except Exception:
                    pass

            if px is None:
                try:
                    layer = e.dxf.layer
                    if _EV_LAYER.search(layer):
                        bbox = _entity_bbox(e)
                        if bbox:
                            px = (bbox[0] + bbox[2]) / 2
                            py = (bbox[1] + bbox[3]) / 2
                            conf = 0.65
                except Exception:
                    pass

            if px is not None and conf > 0 and self._in_clip(px, py):
                candidates.append((px, py, conf))

        if not candidates:
            return None

        cx, cy, confidence = _cluster_center(candidates, self.radius)
        ev_box = _find_solid_bbox_near(msp, cx, cy, self.radius * 2)
        if ev_box is None:
            ev_box = (cx - 3000, cy - 3000, cx + 3000, cy + 3000)
            confidence *= 0.5

        sw = (ev_box[0], ev_box[1])
        return EVAnchor(
            ev_box=ev_box, sw_corner=sw,
            dong=dong, floor=floor, sheet_id=sheet_id,
            confidence=round(confidence, 3),
        )

    def _in_clip(self, x: float, y: float) -> bool:
        if self.clip is None:
            return True
        xmin, ymin, xmax, ymax = self.clip
        return xmin <= x <= xmax and ymin <= y <= ymax


# ─────────────────────────────────────────────────────────────
# 격자 교점 기반 검출기
# ─────────────────────────────────────────────────────────────

class GridAnchorDetector:
    """전략 c: X1·Y1 격자선 교점 = 건물 SW 모서리 근사.

    한국 구조도면은 격자를 X1~Xn / Y1~Yn (또는 가나다/ABC)로 표기.
    X1(가장 왼쪽 격자)과 Y1(가장 아래 격자) 교점이 건물 SW 모서리.
    같은 건물의 모든 도엽이 같은 격자를 공유 → 다중 도면 통일 가능.
    """

    def __init__(self, dong_clip: Optional[Tuple[float,float,float,float]] = None):
        self.clip = dong_clip

    def detect(self, dxf_doc, dong: str = '', floor: object = 0,
               sheet_id: str = '') -> Optional[AnchorPoint]:
        """격자 X1·Y1 교점 반환. None if not found."""
        msp = dxf_doc.modelspace()
        x_coords: List[float] = []
        y_coords: List[float] = []

        for e in iter_all(msp):
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            try:
                txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
                pos = e.dxf.insert
                if self.clip:
                    xmin,ymin,xmax,ymax = self.clip
                    if not (xmin <= pos.x <= xmax and ymin <= pos.y <= ymax):
                        continue
                if _GRID_X1.match(txt):
                    x_coords.append(pos.x)
                elif _GRID_Y1.match(txt):
                    y_coords.append(pos.y)
            except Exception:
                pass

        if not (x_coords and y_coords):
            return None

        return AnchorPoint(
            x=min(x_coords),
            y=min(y_coords),
            label=f'grid_X1Y1_{dong}',
            strategy='grid_intersection',
            confidence=0.75,
        )

    def detect_all_grid_labels(self, dxf_doc) -> Dict[str, List[float]]:
        """모든 격자 라벨과 좌표 수집 (디버그/시각화용)."""
        msp = dxf_doc.modelspace()
        grid_x: Dict[str, List[float]] = {}  # 라벨 → X 좌표 목록
        grid_y: Dict[str, List[float]] = {}  # 라벨 → Y 좌표 목록

        x_pat = re.compile(r'^X\s*(\d+)$|^([A-Z])\s*$', re.IGNORECASE)
        y_pat = re.compile(r'^Y\s*(\d+)$|^(\d+)\s*$', re.IGNORECASE)

        for e in iter_all(msp):
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            try:
                txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
                pos = e.dxf.insert
                mx = x_pat.match(txt)
                my = y_pat.match(txt)
                if mx:
                    label = txt
                    grid_x.setdefault(label, []).append(pos.x)
                elif my:
                    label = txt
                    grid_y.setdefault(label, []).append(pos.y)
            except Exception:
                pass

        return {'x': grid_x, 'y': grid_y}


# ─────────────────────────────────────────────────────────────
# 수동 앵커 (폴백)
# ─────────────────────────────────────────────────────────────

def manual_anchor(x: float, y: float, label: str = 'manual') -> AnchorPoint:
    """사용자가 직접 지정하는 기준점. 자동 검출 실패 시 폴백."""
    return AnchorPoint(x=x, y=y, label=label, strategy='manual', confidence=1.0)


# ─────────────────────────────────────────────────────────────
# 내부 유틸
# ─────────────────────────────────────────────────────────────

def _entity_bbox(e) -> Optional[Tuple[float,float,float,float]]:
    """엔티티 BBox (xmin,ymin,xmax,ymax). 실패 시 None."""
    t = e.dxftype()
    try:
        if t == 'LINE':
            x0, y0 = e.dxf.start.x, e.dxf.start.y
            x1, y1 = e.dxf.end.x, e.dxf.end.y
            return (min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1))
        elif t in ('LWPOLYLINE', 'POLYLINE'):
            pts = [(p[0], p[1]) for p in e.get_points()]
            if not pts:
                return None
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
        elif t == 'HATCH':
            for path in e.paths:
                try:
                    pts = list(path.vertices)
                    if pts:
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        return (min(xs), min(ys), max(xs), max(ys))
                except Exception:
                    pass
        elif t in ('CIRCLE', 'ARC'):
            cx, cy = e.dxf.center.x, e.dxf.center.y
            r = e.dxf.radius
            return (cx-r, cy-r, cx+r, cy+r)
        elif t in ('TEXT', 'MTEXT'):
            pos = e.dxf.insert
            return (pos.x, pos.y, pos.x, pos.y)
    except Exception:
        pass
    return None


def _cluster_center(candidates: List[Tuple[float,float,float]],
                    radius: float) -> Tuple[float, float, float]:
    """후보점 중 가장 밀집된 클러스터 중심 반환."""
    if len(candidates) == 1:
        return candidates[0]

    best_x, best_y, best_score = 0.0, 0.0, -1.0
    for cx, cy, _ in candidates:
        cluster = [(x, y, c) for x, y, c in candidates
                   if abs(x-cx) < radius and abs(y-cy) < radius]
        score = sum(c for _, _, c in cluster)
        if score > best_score:
            best_score = score
            total = sum(c for _, _, c in cluster)
            best_x = sum(x*c for x, y, c in cluster) / total
            best_y = sum(y*c for x, y, c in cluster) / total

    conf = min(best_score / max(1, len(candidates)), 1.0)
    return best_x, best_y, conf


def _find_solid_bbox_near(msp, cx: float, cy: float,
                          radius: float) -> Optional[Tuple[float,float,float,float]]:
    """cx,cy 근처에서 가장 큰 닫힌 다각형 BBox (E/V 코어 외곽)."""
    best: Optional[Tuple[float,float,float,float]] = None
    best_area = 0.0

    for e in iter_all(msp):
        if e.dxftype() not in ('LWPOLYLINE', 'HATCH', 'SOLID'):
            continue
        bbox = _entity_bbox(e)
        if bbox is None:
            continue
        bx = (bbox[0] + bbox[2]) / 2
        by = (bbox[1] + bbox[3]) / 2
        if abs(bx - cx) > radius or abs(by - cy) > radius:
            continue
        area = (bbox[2]-bbox[0]) * (bbox[3]-bbox[1])
        # 너무 작으면 단면 → 스킵, 너무 크면 외벽 → 스킵
        if area < 1_000_000 or area > 1_000_000_000:
            continue
        if area > best_area:
            best_area = area
            best = bbox

    return best
