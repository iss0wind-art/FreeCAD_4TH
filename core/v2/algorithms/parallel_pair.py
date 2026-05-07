"""
parallel_pair.py — 평행선 페어링 (v4 P4 algorithms)
=====================================================
LINE 두 개가 평행하면 벽/보의 양면일 수 있음.

[3단 필터]
  1. 방향각 차 < angle_tol_deg
  2. 수직거리 dist_min ≤ d ≤ dist_max
  3. 길이 오버랩 ratio ≥ overlap_min_ratio

[규약]
  매직넘버 0건. 모든 thresholds 함수 인자.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

Point = Tuple[float, float]


@dataclass
class Line:
    p0: Point
    p1: Point

    @property
    def length(self) -> float:
        return math.hypot(self.p1[0] - self.p0[0], self.p1[1] - self.p0[1])

    @property
    def angle_deg(self) -> float:
        a = math.degrees(math.atan2(self.p1[1] - self.p0[1],
                                    self.p1[0] - self.p0[0]))
        # 0~180 정규화 (180/360 등가)
        return a % 180


@dataclass
class ParallelPair:
    a: Line
    b: Line
    distance: float           # 수직거리 (단면 두께 추정)
    overlap_ratio: float      # 길이 방향 오버랩 비율
    centerline: Line          # 두 선 중심선


def pair_lines(
    lines: List[Line],
    angle_tol_deg: float,
    dist_min: float,
    dist_max: float,
    overlap_min_ratio: float,
) -> List[ParallelPair]:
    """평행쌍 매칭.

    Args:
        lines: LINE 리스트
        angle_tol_deg: 방향각 차 허용 (도)
        dist_min, dist_max: 수직거리 범위 (mm)
        overlap_min_ratio: 길이 오버랩 최소 (0.0~1.0)
    """
    pairs: List[ParallelPair] = []
    used = set()
    n = len(lines)

    for i in range(n):
        if i in used:
            continue
        for j in range(i + 1, n):
            if j in used:
                continue
            a, b = lines[i], lines[j]

            # 1. 방향각
            da = abs(a.angle_deg - b.angle_deg)
            da = min(da, 180 - da)
            if da > angle_tol_deg:
                continue

            # 2. 수직거리
            d = _perp_distance(a, b)
            if d < dist_min or d > dist_max:
                continue

            # 3. 길이 오버랩
            overlap = _projection_overlap(a, b)
            if overlap < overlap_min_ratio:
                continue

            cl = _centerline(a, b)
            pairs.append(ParallelPair(
                a=a, b=b,
                distance=d,
                overlap_ratio=overlap,
                centerline=cl,
            ))
            used.add(i)
            used.add(j)
            break

    return pairs


def _perp_distance(a: Line, b: Line) -> float:
    """선 a → 선 b 의 수직거리 (가까운 방향)."""
    # a를 무한선으로 보고 b의 두 점에서 거리 계산 평균
    ax, ay = a.p0
    bx, by = a.p1
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    if L == 0:
        return float("inf")
    nx, ny = -dy / L, dx / L
    d0 = abs((b.p0[0] - ax) * nx + (b.p0[1] - ay) * ny)
    d1 = abs((b.p1[0] - ax) * nx + (b.p1[1] - ay) * ny)
    return (d0 + d1) / 2


def _projection_overlap(a: Line, b: Line) -> float:
    """길이 방향 오버랩 비율 (0~1)."""
    ax, ay = a.p0
    bx, by = a.p1
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    if L == 0:
        return 0.0
    ux, uy = dx / L, dy / L
    # b의 두 점을 a 방향으로 투영
    t0 = (b.p0[0] - ax) * ux + (b.p0[1] - ay) * uy
    t1 = (b.p1[0] - ax) * ux + (b.p1[1] - ay) * uy
    tmin, tmax = min(t0, t1), max(t0, t1)
    overlap_min = max(0.0, tmin)
    overlap_max = min(L, tmax)
    overlap_len = max(0.0, overlap_max - overlap_min)
    return overlap_len / L


def _centerline(a: Line, b: Line) -> Line:
    """두 평행선 중간 라인."""
    p0 = ((a.p0[0] + b.p0[0]) / 2, (a.p0[1] + b.p0[1]) / 2)
    p1 = ((a.p1[0] + b.p1[0]) / 2, (a.p1[1] + b.p1[1]) / 2)
    return Line(p0=p0, p1=p1)


def auto_thickness_thresholds(
    lines: List[Line],
    target_dist_count: int = 100,
) -> Tuple[float, float]:
    """도면 통계에서 자동 dist_min/dist_max 산출.

    근사: 가까운 선들의 수직거리 분포 → median ± k·MAD.
    매직넘버 회피용 helper.
    """
    if not lines:
        return 100.0, 600.0

    # 단순 polling: 같은 각도(±5도) 가까운 쌍만
    dists = []
    for i, a in enumerate(lines):
        for j in range(i + 1, len(lines)):
            b = lines[j]
            da = abs(a.angle_deg - b.angle_deg)
            da = min(da, 180 - da)
            if da > 5:
                continue
            d = _perp_distance(a, b)
            if 50 < d < 1000:    # 합리적 벽/보 두께 범위
                dists.append(d)
            if len(dists) >= target_dist_count:
                break
        if len(dists) >= target_dist_count:
            break

    if not dists:
        return 100.0, 600.0

    dists.sort()
    median = dists[len(dists) // 2]
    mad = sorted(abs(d - median) for d in dists)[len(dists) // 2]
    return max(50.0, median - 3 * mad), median + 3 * mad
