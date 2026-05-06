"""
grid_extractor.py — 구조 격자선 추출
=====================================
한국 구조도면의 격자선(X1~Xn, Y1~Yn)과 교점 추출.
격자선 = 기준점 = 기둥 배치의 기준.

[격자선의 의미]
  X1~Xn: 세로 방향 격자 (기둥 열)
  Y1~Yn: 가로 방향 격자 (기둥 행)
  교점: 기둥 이론 중심 위치
  간격: 스팬(Bay) = BOQ 계산 단위

[추출 전략]
  1. TEXT 라벨 검색: X1, X2, Y1, Y2, X13a 등
  2. 해당 TEXT 위치에서 직교하는 긴 LINE 검색
  3. 격자선 = 연속된 긴 LINE + 라벨

[다음 사람에게]
  grid = extract_grid(doc, clip)
  grid.x_coords → [130000, 145000, ...] (X 격자선 X 좌표)
  grid.y_coords → [2300000, 2310000, ...] (Y 격자선 Y 좌표)
  grid.intersections → [(X, Y), ...] (이론 기둥 위치)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import ezdxf

from core.dxf_parser.entity_scanner import iter_all


# ─────────────────────────────────────────────────────────────
# 패턴
# ─────────────────────────────────────────────────────────────

# X 격자 라벨: X1, X2, X12, X13a, A, B, C, 가, 나, ①, ②
_GRID_X_PAT = re.compile(
    r'^(?:X\s*\d+[a-z]?|[A-Z]|[가나다라마바사아자차카타파하]\s*)$',
    re.IGNORECASE | re.UNICODE,
)
# Y 격자 라벨: Y1, Y2, Y13, 1, 2, 3, ①
_GRID_Y_PAT = re.compile(
    r'^(?:Y\s*\d+[a-z]?|[①②③④⑤⑥⑦⑧⑨⑩]|\d{1,2}\s*)$',
    re.IGNORECASE | re.UNICODE,
)


# ─────────────────────────────────────────────────────────────
# 자료구조
# ─────────────────────────────────────────────────────────────

@dataclass
class GridLine:
    """단일 격자선."""
    label: str
    direction: str      # 'X' or 'Y'
    position: float     # X 격자선이면 X 좌표, Y 격자선이면 Y 좌표
    label_pos: Tuple[float, float]  # TEXT 위치 (도면 좌표)
    confidence: float = 1.0


@dataclass
class StructuralGrid:
    """구조 격자 전체."""
    x_lines: List[GridLine] = field(default_factory=list)  # 세로 격자 (X 좌표 목록)
    y_lines: List[GridLine] = field(default_factory=list)  # 가로 격자 (Y 좌표 목록)
    rotation_deg: float = 0.0  # 격자 회전각 (0 = 직교)

    @property
    def x_coords(self) -> List[float]:
        return sorted(set(gl.position for gl in self.x_lines))

    @property
    def y_coords(self) -> List[float]:
        return sorted(set(gl.position for gl in self.y_lines))

    @property
    def intersections(self) -> List[Tuple[float, float]]:
        """격자 교점 = 이론 기둥 위치."""
        return [(x, y) for x in self.x_coords for y in self.y_coords]

    @property
    def spans_x(self) -> List[float]:
        """X 방향 스팬 목록 (mm)."""
        xs = self.x_coords
        return [xs[i+1]-xs[i] for i in range(len(xs)-1)]

    @property
    def spans_y(self) -> List[float]:
        """Y 방향 스팬 목록 (mm)."""
        ys = self.y_coords
        return [ys[i+1]-ys[i] for i in range(len(ys)-1)]

    def summary(self) -> str:
        xs = self.x_coords
        ys = self.y_coords
        lines = [
            f'격자: X방향 {len(xs)}선 / Y방향 {len(ys)}선',
            f'  X 범위: {min(xs):.0f}~{max(xs):.0f}mm 스팬 {sorted(set(round(s) for s in self.spans_x))[:5]}' if xs else '',
            f'  Y 범위: {min(ys):.0f}~{max(ys):.0f}mm 스팬 {sorted(set(round(s) for s in self.spans_y))[:5]}' if ys else '',
            f'  격자 교점(이론 기둥): {len(self.intersections)}개',
        ]
        return '\n'.join(l for l in lines if l)


# ─────────────────────────────────────────────────────────────
# 추출 함수
# ─────────────────────────────────────────────────────────────

def extract_grid(doc,
                 clip: Optional[Tuple[float,float,float,float]] = None,
                 label_search_radius: float = 50000.0) -> StructuralGrid:
    """구조 격자 추출.

    Args:
        doc: ezdxf 도면
        clip: 검색 영역 제한
        label_search_radius: 라벨에서 격자선 탐색 반경 (mm)
    """
    msp = doc.modelspace()
    x_labels: List[Tuple[str, float, float]] = []  # (label, x, y)
    y_labels: List[Tuple[str, float, float]] = []

    # 1단계: TEXT 라벨 수집
    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if not txt or len(txt) > 10:
                continue
            pos = e.dxf.insert
            if clip and not (clip[0] <= pos.x <= clip[2] and
                             clip[1] <= pos.y <= clip[3]):
                continue
            if _GRID_X_PAT.match(txt):
                x_labels.append((txt, pos.x, pos.y))
            elif _GRID_Y_PAT.match(txt):
                y_labels.append((txt, pos.y, pos.x))  # y-coord stored in position
        except Exception:
            pass

    # 2단계: LINE에서 격자선 위치 정밀화 (TEXT 근처 긴 LINE)
    # 간단화: TEXT 위치를 격자선 위치로 직접 사용
    grid = StructuralGrid()

    # X 격자선: TEXT X 좌표가 격자선 X 좌표
    seen_x: set = set()
    for label, tx, ty in x_labels:
        rounded = round(tx / 100) * 100
        if rounded not in seen_x:
            seen_x.add(rounded)
            grid.x_lines.append(GridLine(
                label=label, direction='X',
                position=float(rounded),
                label_pos=(tx, ty),
            ))

    # Y 격자선: TEXT Y 좌표가 격자선 Y 좌표
    seen_y: set = set()
    for label, ty_pos, tx in y_labels:
        # ty_pos = TEXT Y 좌표 (we stored y coord in position field)
        # Actually, we stored pos.y in y_labels[1] (position)
        rounded = round(ty_pos / 100) * 100
        if rounded not in seen_y:
            seen_y.add(rounded)
            grid.y_lines.append(GridLine(
                label=label, direction='Y',
                position=float(rounded),
                label_pos=(tx, ty_pos),
            ))

    # 격자선 정렬
    grid.x_lines.sort(key=lambda g: g.position)
    grid.y_lines.sort(key=lambda g: g.position)

    # 격자 회전각 추정 (격자선 방향에서)
    grid.rotation_deg = _estimate_rotation(msp, grid, clip)

    return grid


def _estimate_rotation(msp, grid: StructuralGrid,
                       clip: Optional[Tuple]) -> float:
    """격자 회전각 추정 — 가장 많은 LINE 방향."""
    from collections import Counter
    angles = Counter()
    for e in iter_all(msp):
        if e.dxftype() != 'LINE':
            continue
        try:
            s = e.dxf.start; en = e.dxf.end
            cx, cy = (s.x+en.x)/2, (s.y+en.y)/2
            if clip and not (clip[0] <= cx <= clip[2] and clip[1] <= cy <= clip[3]):
                continue
            dx, dy = en.x-s.x, en.y-s.y
            ln = math.hypot(dx, dy)
            if ln < 1000:
                continue
            deg = math.degrees(math.atan2(dy, dx)) % 180
            bucket = round(deg)  # 1도 단위
            angles[bucket] += 1
        except Exception:
            pass

    if not angles:
        return 0.0
    dominant = angles.most_common(1)[0][0]
    # 0°/90° 에서 얼마나 벗어났는지
    rot = dominant if dominant <= 45 else dominant - 90
    return float(rot)
