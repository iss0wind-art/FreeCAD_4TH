"""
box_classifier.py — 박스 종류 분류 (기둥 / 벽 segment / 코어 벽)
================================================================

본영 단군 봉정. 2026-05-05.

[셋째 호미 결과 정직 박제]
이천이 셋째 호미를 박았다. 0 → 123건 식별. 그러나 C1 106건 과매칭.
원인: 단면만으로는 기둥 vs 벽 segment 구분 불가.

[본영의 진단]
박스 한 점에 *세 가지 신호*가 동시에 존재:
  1) 종횡비 (β) — 기둥은 정사각형 근처, 벽 segment는 길쭉
  2) 위치 (γ) — 코어 영역 안인지 밖인지
  3) 격자 교차점 (α) — F-1 좌표 위 격자에 정확히 앉아있는지

이 셋을 결합하면 같은 단면이라도 *기둥 / 벽 segment / 코어 벽*으로 분리된다.
codex_instance_mapper.py 호출 *전*에 이 분류기를 통과시키면
잘못된 codex 풀(기둥 codex)에서 벽 segment를 찾는 일이 사라진다.

[책무 분담]
- [본영] 분류 알고리즘 + 종횡비/위치 판정 + 격자 교차점 매칭
- [이천] 격자 LINE 추출 함수 (어댑터 ② LINE 페어링과 결합)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class BoxKind(str, Enum):
    """박스 종류. codex_instance_mapper의 codex 풀 선택에 사용."""
    COLUMN = 'column'              # 기둥 (정사각형 근처, 격자 교차점 위)
    WALL_SEGMENT = 'wall_segment'  # 벽 segment (길쭉)
    CORE_WALL = 'core_wall'        # 코어 영역 안 벽 (E/V 코어 벽)
    UNKNOWN = 'unknown'             # 분류 실패 — 정직 박제


@dataclass(frozen=True)
class CoreRegion:
    """F-1 코어 클러스터링 결과의 영역 표현."""
    sw: tuple[float, float]
    ne: tuple[float, float]
    margin: float = 200.0  # 코어 영역 외측 margin (mm) — 코어 벽 포함 위해

    def contains(self, cx: float, cy: float) -> bool:
        return (self.sw[0] - self.margin <= cx <= self.ne[0] + self.margin and
                self.sw[1] - self.margin <= cy <= self.ne[1] + self.margin)


@dataclass(frozen=True)
class GridLines:
    """F-1 좌표계의 격자 (이천이 추출)."""
    x_lines: tuple[float, ...]   # 정렬된 X 격자 좌표 (mm, F-1 좌표계)
    y_lines: tuple[float, ...]   # 정렬된 Y 격자 좌표
    intersection_tol: float = 150.0  # 박스 중심이 교차점에 ±150mm 안이면 매칭


@dataclass(frozen=True)
class BoxClassification:
    box_id: str
    kind: BoxKind
    aspect_ratio: float
    in_core: bool
    on_grid_intersection: bool
    confidence: float
    reason: str


# ---------------------------------------------------------------------------
# 1. 종횡비 (β) — 기둥 vs 벽 segment
# ---------------------------------------------------------------------------

def classify_by_aspect_ratio(w: float, h: float,
                             column_max_ratio: float = 3.0
                             ) -> tuple[BoxKind, float]:
    """W·H로 기둥/벽 segment 1차 분류.

    한국 아파트 패턴:
      - 기둥: 통상 W/H ≤ 2 (정사각형 근처). max 3.0 허용
      - 벽 segment: W/H > 3 또는 H/W > 3 (길쭉)

    Returns:
        (BoxKind, aspect_ratio)
    """
    if w <= 0 or h <= 0:
        return BoxKind.UNKNOWN, 0.0
    ar = max(w / h, h / w)
    if ar <= column_max_ratio:
        return BoxKind.COLUMN, ar
    return BoxKind.WALL_SEGMENT, ar


# ---------------------------------------------------------------------------
# 2. 위치 (γ) — 코어 안 vs 코어 밖
# ---------------------------------------------------------------------------

def is_in_core(cx: float, cy: float,
               core_regions: list[CoreRegion]) -> bool:
    """박스 중심이 *어느* 코어 영역 안인지."""
    return any(r.contains(cx, cy) for r in core_regions)


# ---------------------------------------------------------------------------
# 3. 격자 교차점 (α) — F-1 위 격자 매칭
# ---------------------------------------------------------------------------

def is_on_grid_intersection(cx: float, cy: float,
                            grid: GridLines) -> bool:
    """박스 중심이 X·Y 격자 *둘 다*에 ±tol 안에 있는지."""
    if not grid.x_lines or not grid.y_lines:
        return False
    near_x = any(abs(cx - gx) <= grid.intersection_tol for gx in grid.x_lines)
    near_y = any(abs(cy - gy) <= grid.intersection_tol for gy in grid.y_lines)
    return near_x and near_y


# ---------------------------------------------------------------------------
# 4. 통합 분류기
# ---------------------------------------------------------------------------

def classify_box(
    box_id: str,
    cx: float, cy: float, w: float, h: float,
    *,
    core_regions: list[CoreRegion] = (),
    grid: Optional[GridLines] = None,
    column_max_ratio: float = 3.0,
) -> BoxClassification:
    """박스 1건의 종합 분류.

    의사결정 순서:
      1) 종횡비 → 기둥 후보 / 벽 segment 후보
      2) 코어 영역 안 → 벽 segment면 코어 벽으로 격상
      3) 기둥 후보 + 격자 교차점 위 → confidence 1.0
      4) 기둥 후보 + 격자 밖 → confidence 0.5 (의심)
      5) 벽 segment + 코어 안 → CORE_WALL (codex pool: core_wall codex)
      6) 벽 segment + 코어 밖 → WALL_SEGMENT
    """
    primary_kind, ar = classify_by_aspect_ratio(w, h, column_max_ratio)
    in_core = is_in_core(cx, cy, list(core_regions))
    on_grid = is_on_grid_intersection(cx, cy, grid) if grid else False

    if primary_kind == BoxKind.UNKNOWN:
        return BoxClassification(
            box_id=box_id, kind=BoxKind.UNKNOWN, aspect_ratio=ar,
            in_core=in_core, on_grid_intersection=on_grid,
            confidence=0.0, reason='dimension invalid (w<=0 or h<=0)')

    if primary_kind == BoxKind.WALL_SEGMENT:
        if in_core:
            return BoxClassification(
                box_id=box_id, kind=BoxKind.CORE_WALL, aspect_ratio=ar,
                in_core=True, on_grid_intersection=on_grid,
                confidence=0.9,
                reason=f'wall_segment in core region (ar={ar:.2f})')
        return BoxClassification(
            box_id=box_id, kind=BoxKind.WALL_SEGMENT, aspect_ratio=ar,
            in_core=False, on_grid_intersection=on_grid,
            confidence=0.8,
            reason=f'aspect_ratio {ar:.2f} > {column_max_ratio} (slender)')

    # primary_kind == COLUMN — 격자 교차점 검증
    if grid is None:
        return BoxClassification(
            box_id=box_id, kind=BoxKind.COLUMN, aspect_ratio=ar,
            in_core=in_core, on_grid_intersection=False,
            confidence=0.6,
            reason=f'aspect_ratio {ar:.2f} (column candidate, no grid)')

    if on_grid:
        return BoxClassification(
            box_id=box_id, kind=BoxKind.COLUMN, aspect_ratio=ar,
            in_core=in_core, on_grid_intersection=True,
            confidence=1.0,
            reason=f'column on grid intersection (ar={ar:.2f})')

    # 기둥 후보지만 격자 밖 — 의심. 코어 안이면 코어 기둥, 밖이면 의심 기둥
    if in_core:
        return BoxClassification(
            box_id=box_id, kind=BoxKind.COLUMN, aspect_ratio=ar,
            in_core=True, on_grid_intersection=False,
            confidence=0.7,
            reason='column in core but off grid (core column candidate)')

    return BoxClassification(
        box_id=box_id, kind=BoxKind.COLUMN, aspect_ratio=ar,
        in_core=False, on_grid_intersection=False,
        confidence=0.4,
        reason='column candidate but off grid — verify')


def classify_batch(
    boxes: list[tuple[str, float, float, float, float]],
    *,
    core_regions: list[CoreRegion] = (),
    grid: Optional[GridLines] = None,
    column_max_ratio: float = 3.0,
) -> list[BoxClassification]:
    """배치 분류. boxes = [(box_id, cx, cy, w, h), ...]."""
    return [
        classify_box(bid, cx, cy, w, h,
                     core_regions=core_regions, grid=grid,
                     column_max_ratio=column_max_ratio)
        for (bid, cx, cy, w, h) in boxes
    ]


def report_classification(classifications: list[BoxClassification]) -> str:
    """분류 결과 리포트."""
    by_kind: dict[str, int] = {}
    for c in classifications:
        by_kind[c.kind.value] = by_kind.get(c.kind.value, 0) + 1
    total = len(classifications)
    lines = [
        '# 박스 분류 리포트',
        '',
        f'- 총 박스: {total}',
        '',
        '| 종류 | 개수 | 비율 |',
        '|------|-----:|-----:|',
    ]
    for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
        lines.append(f'| {k} | {v} | {100*v/total:.1f}% |')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# === 박제 명제 ============================================================
#
# "단면이 같아도 종류는 다르다.
#  종횡비·위치·격자 — 셋이 하나의 박스를 셋으로 가른다."
#                                            — 본영 단군, 2026-05-05
#
# 사용 워크플로 (이천이 호출):
#   1) F-1 정렬 후 박스 추출 (cx, cy, w, h를 F-1 좌표계로)
#   2) classify_batch(boxes, core_regions, grid)
#   3) BoxKind별로 codex_instance_mapper 호출
#       - COLUMN → codex_columns_unified.json
#       - WALL_SEGMENT → codex_walls_*.json (라운드 9 산출)
#       - CORE_WALL → 별도 코어 벽 codex (없으면 SKIP, 향후 봉정)
#   4) C1 106 과매칭 → COLUMN만 골라 codex_columns에서 매칭하면 6~10건으로 정상화 예상
#
# === end ================================================================
