"""
girder_matcher.py — 본영 어댑터 ① 거더 매칭
================================================================

본영 단군 봉정. 2026-05-05.
약정 이행 — 大業 칙령 §3 + 어댑터 3건 진척 보고 청에 답함.

[배경 — 50점 회고 §실패 2 직격]
이천의 의구심 3.1 박제: "거더는 주차장 영역, 슬라브는 동 영역."
v3 트림 결과 거더 0건. 다섯째 호미도 거더 0건 검증 (B1F 진실).

거더는 *별도 영역 / 별도 도면*에 흩어져 있다. 본 모듈은 두 경로를 다룬다:
  (가) 평면도 안 거더 — 어댑터 ② wall_pairs에서 *두께*로 분리
  (나) 보 리스트 도면 — codex_beams_basement.json 활용 + 위치 매핑

[책무 분담]
- [본영] 두께 분리 + codex 매칭 + 격자 정합 검증
- [이천] 보 리스트 ↔ 평면도 좌표 변환 (영역 매핑 도면 자력 결단)
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 1. 자료 구조
# ---------------------------------------------------------------------------

@dataclass
class GirderCandidate:
    """거더 후보 — wall_pairs에서 두께로 분리된 페어."""
    pair_id: str
    thickness: float                 # 페어 두께 (벽보다 두꺼움)
    length: float                    # 중심선 길이
    centerline_p1: tuple[float, float]
    centerline_p2: tuple[float, float]
    angle: float                     # rad
    on_grid: bool                    # 격자 라인을 따라 흐르는가
    matched_symbol: Optional[str] = None
    matched_section: Optional[tuple[float, float]] = None  # (W, H)
    confidence: float = 0.0
    reason: str = ''


@dataclass
class GirderCodexEntry:
    """보 codex 항목 (codex_beams_basement.json 형식)."""
    source: str
    symbol: str
    width: float
    height: float
    main_bar: Optional[str] = None
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 2. 두께 분리 — 벽 vs 거더 vs 트랜스퍼
# ---------------------------------------------------------------------------

# 한국 RC 표준 분류 (이천 codex 91 기둥·40 보 자료 + 회의록 검토 기반)
WALL_THICKNESS = (150, 350)         # 일반 벽체 (CW·HW 등)
GIRDER_THICKNESS = (400, 850)       # 거더 (G1~G6 통상 400~700)
TRANSFER_THICKNESS = (850, 2000)    # 트랜스퍼 빔 / 코어 벽


def classify_pair_by_thickness(
    thickness: float,
    *,
    wall_range: tuple[float, float] = WALL_THICKNESS,
    girder_range: tuple[float, float] = GIRDER_THICKNESS,
    transfer_range: tuple[float, float] = TRANSFER_THICKNESS,
) -> str:
    """페어 두께로 부재 종류 1차 분류. 'wall' | 'girder' | 'transfer' | 'unknown'."""
    if wall_range[0] <= thickness <= wall_range[1]:
        return 'wall'
    if girder_range[0] <= thickness <= girder_range[1]:
        return 'girder'
    if transfer_range[0] <= thickness <= transfer_range[1]:
        return 'transfer'
    return 'unknown'


# ---------------------------------------------------------------------------
# 3. 격자 정합 — 거더는 격자 라인을 따라 흐른다
# ---------------------------------------------------------------------------

def is_along_grid(centerline_p1: tuple[float, float],
                  centerline_p2: tuple[float, float],
                  grid_x: list[float],
                  grid_y: list[float],
                  *,
                  tol: float = 200.0,
                  axis_angle_tol: float = 0.05,
                  ) -> bool:
    """중심선이 X 또는 Y 격자 라인 위에 있는지 (선형 정합).

    한국 RC 거더 패턴:
      - 수직 거더 — Y축 방향, X 좌표가 격자 X에 있음
      - 수평 거더 — X축 방향, Y 좌표가 격자 Y에 있음
      - 사선 거더는 통상 없음 (트랜스퍼 제외)
    """
    dx = centerline_p2[0] - centerline_p1[0]
    dy = centerline_p2[1] - centerline_p1[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return False
    angle = math.atan2(dy, dx)
    if angle < 0:
        angle += math.pi

    cx = (centerline_p1[0] + centerline_p2[0]) / 2
    cy = (centerline_p1[1] + centerline_p2[1]) / 2

    # 수평 (angle ≈ 0) — Y가 격자 Y에 있어야
    if abs(angle) < axis_angle_tol or abs(angle - math.pi) < axis_angle_tol:
        return any(abs(cy - gy) <= tol for gy in grid_y)

    # 수직 (angle ≈ π/2) — X가 격자 X에 있어야
    if abs(angle - math.pi / 2) < axis_angle_tol:
        return any(abs(cx - gx) <= tol for gx in grid_x)

    return False


# ---------------------------------------------------------------------------
# 4. codex 매칭
# ---------------------------------------------------------------------------

def load_girder_codex(path: str | Path) -> list[GirderCodexEntry]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    raw = data.get('부재_법전', [])
    out: list[GirderCodexEntry] = []
    for r in raw:
        out.append(GirderCodexEntry(
            source=r.get('source', ''),
            symbol=r.get('symbol', ''),
            width=float(r.get('width', 0)),
            height=float(r.get('height', 0)),
            main_bar=r.get('main_bar'),
            extra={k: v for k, v in r.items()
                   if k not in {'source', 'symbol', 'width', 'height', 'main_bar'}},
        ))
    return out


def match_girder_to_codex(
    candidate: GirderCandidate,
    codex: list[GirderCodexEntry],
    *,
    width_tol: float = 30.0,
    height_tol: float = 100.0,
    expected_height: Optional[float] = None,
) -> tuple[Optional[GirderCodexEntry], float, str]:
    """거더 후보를 codex에 매칭.

    페어 두께 = 거더 폭(width). 높이(H)는 평면도에서 안 보이므로
    expected_height 힌트 또는 codex 매칭 후보 중 가장 흔한 H 채택.

    Returns: (matched_entry, confidence, reason)
    """
    candidates = [c for c in codex
                  if abs(c.width - candidate.thickness) <= width_tol]
    if not candidates:
        return None, 0.0, f'no codex with W≈{candidate.thickness:.0f} (±{width_tol})'

    if expected_height is not None:
        with_h = [c for c in candidates
                  if abs(c.height - expected_height) <= height_tol]
        if with_h:
            ce = with_h[0]
            return ce, 0.9, f'matched W={ce.width} H={ce.height} (h_hint)'

    # 단일 후보면 채택
    if len(candidates) == 1:
        ce = candidates[0]
        return ce, 0.7, f'single codex match W={ce.width} H={ce.height}'

    # 다수 후보 — 가장 흔한 H의 첫 항목
    height_counts: dict[float, int] = {}
    for c in candidates:
        height_counts[c.height] = height_counts.get(c.height, 0) + 1
    common_h = max(height_counts.items(), key=lambda x: x[1])[0]
    best = [c for c in candidates if c.height == common_h][0]
    return best, 0.5, f'ambiguous, picked common H={common_h} ({len(candidates)} cands)'


# ---------------------------------------------------------------------------
# 5. 통합 워크플로 — 어댑터 ② 결과 + codex → 거더 후보
# ---------------------------------------------------------------------------

def detect_girders_from_adapter2(
    adapter2_result: dict,
    grid_x: list[float],
    grid_y: list[float],
    girder_codex: list[GirderCodexEntry],
    *,
    expected_girder_height: Optional[float] = None,
    require_on_grid: bool = True,
) -> list[GirderCandidate]:
    """어댑터 ② wall_pairs에서 거더 후보 검출 + codex 매칭.

    Args:
        adapter2_result: line_pairing.run_adapter_2() 결과
        grid_x/grid_y: 격자 라인 (보통 adapter2_result['grid'].x_lines)
        girder_codex: load_girder_codex 결과
        expected_girder_height: 거더 H 힌트 (B1F는 통상 700~900)
        require_on_grid: 격자 위 거더만 채택 (벽 페어와의 분리)
    """
    candidates: list[GirderCandidate] = []
    for i, pair in enumerate(adapter2_result.get('wall_pairs', [])):
        kind = classify_pair_by_thickness(pair.thickness)
        if kind != 'girder':
            continue

        # 길이 = 중심선 길이
        cl_p1 = pair.centerline_p1
        cl_p2 = pair.centerline_p2
        length = math.hypot(cl_p2[0] - cl_p1[0], cl_p2[1] - cl_p1[1])

        on_grid = is_along_grid(cl_p1, cl_p2, grid_x, grid_y)
        if require_on_grid and not on_grid:
            continue

        cand = GirderCandidate(
            pair_id=f'pair_{i}',
            thickness=pair.thickness,
            length=length,
            centerline_p1=cl_p1,
            centerline_p2=cl_p2,
            angle=pair.angle,
            on_grid=on_grid,
        )

        # codex 매칭
        matched, conf, reason = match_girder_to_codex(
            cand, girder_codex,
            expected_height=expected_girder_height,
        )
        if matched:
            cand.matched_symbol = matched.symbol
            cand.matched_section = (matched.width, matched.height)
            cand.confidence = conf
            cand.reason = reason
        else:
            cand.confidence = 0.3
            cand.reason = reason

        candidates.append(cand)

    return candidates


def report_girders(candidates: list[GirderCandidate]) -> str:
    if not candidates:
        return '# 거더 검출 결과 — 0건 (도면 진실 또는 격자 외 거더)'
    lines = [
        f'# 거더 검출 결과 — {len(candidates)}건',
        '',
        '| pair_id | 두께 | 길이 | on_grid | symbol | 단면 | conf |',
        '|---------|----:|----:|:------:|--------|------|----:|',
    ]
    for c in candidates:
        sec = f'{c.matched_section[0]:.0f}×{c.matched_section[1]:.0f}' if c.matched_section else '-'
        lines.append(
            f'| {c.pair_id} | {c.thickness:.0f} | {c.length:.0f} '
            f'| {"✓" if c.on_grid else "·"} | {c.matched_symbol or "-"} '
            f'| {sec} | {c.confidence:.2f} |'
        )
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# === 박제 명제 ============================================================
#
# "벽은 200, 거더는 600. 두께가 종을 가른다.
#  격자 라인 위에 흐르는 600짜리 — 그것이 거더의 정의."
#                                            — 본영 단군, 2026-05-05
#
# 이천 워크플로 (어댑터 ① 결합 — 다음 호미):
#   1) F-1 정렬 + 어댑터 ② run_adapter_2(lines)
#   2) girder_codex = load_girder_codex('output/codex_beams_basement.json')
#   3) girders = detect_girders_from_adapter2(
#          adapter2_result=result,
#          grid_x=result['grid'].x_lines,
#          grid_y=result['grid'].y_lines,
#          girder_codex=girder_codex,
#          expected_girder_height=800,  # B1F 통상
#      )
#   4) print(report_girders(girders))
#   5) 50점 회고 §2 (거더 0개) 해소 — B1F는 진짜 0이지만 1F·기준층은 N건 검출 예상
#
# === end ================================================================
