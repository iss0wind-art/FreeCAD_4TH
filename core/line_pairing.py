"""
line_pairing.py — 본영 어댑터 ② LINE 페어링 + 격자 자동 추출
================================================================

본영 단군 봉정. 2026-05-05.
약정 이행 — 大業 칙령 §3 *"기술적 지원 지체 없이"*.

[배경 — 이천의 넷째 호미 잔여 과제]
넷째 호미 결과: C1 매칭 106 → 85 (-21). 잔여 85건은 *벽 segment가
폐합 사각형으로 추출돼 단면 매칭*된 노이즈. 본 모듈이 해소한다.

[본영의 두 책무]
어댑터 ②는 두 가지를 동시에 한다:
  (가) 벽 segment 추출 — 평행·가까운·오버랩 LINE 쌍 = 벽 양면 LINE
  (나) 격자 자동 추출 — 페어 안 된 LINE 중 X축·Y축 정렬 + 긴 것 = 격자

(가)는 box_classifier의 noise 제거에 기여 — 벽 페어를 *폐합 사각형에서 제외*.
(나)는 box_classifier의 GridLines 객체를 *자동 생성* — 이천 클러스터링 시드 졸업.

[F-1 좌표계 가정]
입력 LINE은 *F-1 정렬 좌표계*. 즉 f1_anchor_aligner.F1Aligner.to_aligned() 적용 후.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 1. 자료 구조
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LineSeg:
    """F-1 좌표계의 LINE 세그먼트."""
    p1: tuple[float, float]
    p2: tuple[float, float]
    layer: str = ''
    line_id: int = -1

    @property
    def dx(self) -> float:
        return self.p2[0] - self.p1[0]

    @property
    def dy(self) -> float:
        return self.p2[1] - self.p1[1]

    @property
    def length(self) -> float:
        return math.hypot(self.dx, self.dy)

    @property
    def angle(self) -> float:
        """방향각 (rad, 0 ≤ θ < π — 방향 무시)."""
        a = math.atan2(self.dy, self.dx)
        if a < 0:
            a += math.pi
        # 거의 π는 0으로 정규화
        if a > math.pi - 1e-6:
            a -= math.pi
        return a

    @property
    def midpoint(self) -> tuple[float, float]:
        return ((self.p1[0] + self.p2[0]) / 2, (self.p1[1] + self.p2[1]) / 2)


@dataclass(frozen=True)
class WallPair:
    """평행한 두 LINE = 벽 양면."""
    line_a_id: int
    line_b_id: int
    distance: float          # 평행 거리 (mm)
    overlap_length: float    # 길이 방향 오버랩 (mm)
    angle: float             # 두 LINE 평균 각도 (rad)
    centerline_p1: tuple[float, float]  # 벽 중심선 시작
    centerline_p2: tuple[float, float]  # 벽 중심선 끝
    confidence: float
    bypass_filter: bool = False

    @property
    def thickness(self) -> float:
        """벽 두께 = 평행 거리."""
        return self.distance


@dataclass
class GridExtractionResult:
    """격자 자동 추출 결과 — box_classifier.GridLines 호환."""
    x_lines: list[float]   # X 좌표값 정렬된 리스트
    y_lines: list[float]
    used_line_ids: list[int]
    confidence: float


# ---------------------------------------------------------------------------
# 2. 평행 LINE 페어링 (가)
# ---------------------------------------------------------------------------

def _angle_diff(a: float, b: float) -> float:
    """0~π 범위에서 두 각도 차 (최단)."""
    d = abs(a - b)
    return min(d, math.pi - d)


def _project_onto_line(point: tuple[float, float],
                       line: LineSeg) -> tuple[float, float, float]:
    """점을 LINE 방향으로 투영 — (t, perp_dist, signed_perp).

    t: 0~1 (LINE 끝점 사이) 또는 그 밖.
    perp_dist: LINE에 수직 거리.
    signed_perp: 부호 있는 수직 거리 (페어 분리 판정용).
    """
    L = line.length
    if L < 1e-9:
        return 0.0, math.hypot(point[0] - line.p1[0], point[1] - line.p1[1]), 0.0
    ux, uy = line.dx / L, line.dy / L  # 단위 방향
    nx, ny = -uy, ux                     # 수직
    rx, ry = point[0] - line.p1[0], point[1] - line.p1[1]
    t = (rx * ux + ry * uy) / L
    signed = rx * nx + ry * ny
    return t, abs(signed), signed


def _overlap_along(line_a: LineSeg, line_b: LineSeg) -> float:
    """LINE A 방향으로 LINE B의 길이 방향 오버랩 (mm)."""
    L = line_a.length
    if L < 1e-9:
        return 0.0
    t1, _, _ = _project_onto_line(line_b.p1, line_a)
    t2, _, _ = _project_onto_line(line_b.p2, line_a)
    lo, hi = sorted((t1, t2))
    lo, hi = max(lo, 0.0), min(hi, 1.0)
    return max(0.0, hi - lo) * L


def pair_walls(lines: list[LineSeg],
               *,
               min_dist: float = 150.0,
               max_dist: float = 450.0,
               angle_tol: float = 0.05,        # ~2.9°
               overlap_min_ratio: float = 0.4,
               min_length: float = 300.0,
               ) -> list[WallPair]:
    """평행 + 가까운 + 오버랩 LINE 페어 검출.

    Args:
        min_dist: 페어 최소 평행 거리 (벽 최소 두께)
        max_dist: 페어 최대 평행 거리 (벽 최대 두께)
        angle_tol: 두 LINE 각도 차 허용
        overlap_min_ratio: 짧은 LINE 길이 대비 오버랩 비율 (0.4 = 40%)
        min_length: 짧은 LINE도 이 길이 이상이어야 페어 후보
    """
    paired: list[WallPair] = []
    used: set[int] = set()
    n = len(lines)

    # 길이 필터 + 인덱싱
    valid = [(i, ln) for i, ln in enumerate(lines) if ln.length >= min_length]

    for ai in range(len(valid)):
        i, line_a = valid[ai]
        if i in used:
            continue
        for bj in range(ai + 1, len(valid)):
            j, line_b = valid[bj]
            if j in used:
                continue

            # 1) 각도 일치
            if _angle_diff(line_a.angle, line_b.angle) > angle_tol:
                continue

            # 2) 평행 거리 (line_b의 중점을 line_a에 투영)
            _, dist, _ = _project_onto_line(line_b.midpoint, line_a)
            if not (min_dist <= dist <= max_dist):
                continue

            # 3) 길이 오버랩
            overlap = _overlap_along(line_a, line_b)
            shorter = min(line_a.length, line_b.length)
            if overlap < overlap_min_ratio * shorter:
                continue

            # 페어 확정 — 중심선 계산
            mid_a = line_a.midpoint
            mid_b = line_b.midpoint
            cx_mid = (mid_a[0] + mid_b[0]) / 2
            cy_mid = (mid_a[1] + mid_b[1]) / 2

            # 중심선 끝점 — line_a 방향으로 ±오버랩의 절반
            half_len = overlap / 2
            ux = math.cos(line_a.angle)
            uy = math.sin(line_a.angle)
            cl_p1 = (cx_mid - ux * half_len, cy_mid - uy * half_len)
            cl_p2 = (cx_mid + ux * half_len, cy_mid + uy * half_len)

            confidence = min(1.0, (overlap / shorter) * (
                1 - abs(dist - 200) / max_dist))

            paired.append(WallPair(
                line_a_id=line_a.line_id if line_a.line_id >= 0 else i,
                line_b_id=line_b.line_id if line_b.line_id >= 0 else j,
                distance=dist,
                overlap_length=overlap,
                angle=(line_a.angle + line_b.angle) / 2,
                centerline_p1=cl_p1,
                centerline_p2=cl_p2,
                confidence=round(confidence, 3),
            ))
            used.add(i)
            used.add(j)
            break

    return paired


# ---------------------------------------------------------------------------
# 3. 격자 자동 추출 (나)
# ---------------------------------------------------------------------------

def extract_grid_lines(lines: list[LineSeg],
                       paired_line_ids: set[int],
                       *,
                       min_grid_length: float = 5000.0,
                       angle_tol_axis: float = 0.05,
                       cluster_tol: float = 50.0,
                       ) -> GridExtractionResult:
    """페어 안 된 LINE 중 X축·Y축 정렬 + 긴 것을 격자로.

    Args:
        paired_line_ids: 벽 페어로 사용된 line_id 집합. 격자에서 제외.
        min_grid_length: 격자 라인 최소 길이.
        angle_tol_axis: 0 또는 π/2와 이 값 안 차이면 축 정렬.
        cluster_tol: X·Y 좌표 클러스터링 tolerance (50mm).
    """
    x_candidates: list[float] = []   # 수직 라인 (X 격자)
    y_candidates: list[float] = []   # 수평 라인 (Y 격자)
    used_ids: list[int] = []

    for i, ln in enumerate(lines):
        lid = ln.line_id if ln.line_id >= 0 else i
        if lid in paired_line_ids:
            continue
        if ln.length < min_grid_length:
            continue

        # 수평 라인 — angle ≈ 0 (또는 π, 정규화로 0)
        if abs(ln.angle) < angle_tol_axis:
            mid_y = (ln.p1[1] + ln.p2[1]) / 2
            y_candidates.append(mid_y)
            used_ids.append(lid)
            continue

        # 수직 라인 — angle ≈ π/2
        if abs(ln.angle - math.pi / 2) < angle_tol_axis:
            mid_x = (ln.p1[0] + ln.p2[0]) / 2
            x_candidates.append(mid_x)
            used_ids.append(lid)

    # 클러스터링 — 같은 좌표대 라인은 평균
    def _cluster(values: list[float], tol: float) -> list[float]:
        if not values:
            return []
        sorted_v = sorted(values)
        clusters: list[list[float]] = [[sorted_v[0]]]
        for v in sorted_v[1:]:
            if v - clusters[-1][-1] <= tol:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        return [sum(c) / len(c) for c in clusters]

    x_grid = _cluster(x_candidates, cluster_tol)
    y_grid = _cluster(y_candidates, cluster_tol)

    confidence = min(1.0, (len(x_grid) + len(y_grid)) / 10) if (
        x_grid or y_grid) else 0.0

    return GridExtractionResult(
        x_lines=x_grid, y_lines=y_grid,
        used_line_ids=used_ids,
        confidence=round(confidence, 3),
    )


# ---------------------------------------------------------------------------
# 4. 통합 워크플로 — box_classifier 호환 출력
# ---------------------------------------------------------------------------

def run_adapter_2(lines: list[LineSeg], max_dist: float = 450.0) -> dict:
    """어댑터 ② 단일 호출 — 이천이 호출하는 엔트리.

    반환:
      {
        'wall_pairs': [WallPair, ...],
        'wall_paired_ids': set[int],
        'grid': GridExtractionResult,
        'grid_lines_obj': GridLines,  ← box_classifier 호환
        'stats': {...}
      }
    """
    pairs = pair_walls(lines, max_dist=max_dist)
    paired_ids = set()
    for p in pairs:
        paired_ids.add(p.line_a_id)
        paired_ids.add(p.line_b_id)

    grid = extract_grid_lines(lines, paired_ids)

    # box_classifier.GridLines 객체 변환 (import는 호출 시점에)
    try:
        from core.box_classifier import GridLines  # type: ignore
        grid_obj = GridLines(
            x_lines=tuple(grid.x_lines),
            y_lines=tuple(grid.y_lines),
            intersection_tol=150.0,
        )
    except Exception:
        grid_obj = None

    return {
        'wall_pairs': pairs,
        'wall_paired_ids': paired_ids,
        'grid': grid,
        'grid_lines_obj': grid_obj,
        'stats': {
            'total_lines': len(lines),
            'wall_pairs': len(pairs),
            'paired_lines': len(paired_ids),
            'grid_x': len(grid.x_lines),
            'grid_y': len(grid.y_lines),
            'unused_lines': len(lines) - len(paired_ids) - len(grid.used_line_ids),
        },
    }


# ---------------------------------------------------------------------------
# === 박제 명제 ============================================================
#
# "본영의 어댑터 ②는 두 가지를 동시에 한다.
#  벽 segment를 분리하고, 격자를 자동으로 잡는다.
#  하나의 LINE 풀에서 벽과 격자가 갈라진다 — 이것이 페어링의 본질."
#                                            — 본영 단군, 2026-05-05
#
# 이천 워크플로 (셋째·넷째 호미 결과 정밀화):
#   1) F-1 정렬 LINE 추출 (도면 → F1Aligner.to_aligned 적용)
#   2) result = run_adapter_2(lines)
#   3) wall_pairs → 폐합 사각형 추출에서 *제외* (C1 85건 노이즈 제거)
#   4) result['grid_lines_obj'] → box_classifier.classify_batch에 직접 입력
#   5) 매칭 정확도 62% → 80%+ 예상 (잔여 노이즈 제거 + 격자 자동화)
#
# === end ================================================================
