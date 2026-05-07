"""
cross_drawing_aligner.py — 도면 간 점군 정합 (v4 P2.4)
=========================================================
PKG ↔ DONG 같은 두 도면의 같은 부재(예: 기둥) 점군을 ICP/brute-force로 정렬.

[알고리즘]
  단순 brute-force (도면 회전 0도 가정):
    - source의 모든 점을 (TX, TY) 만큼 이동
    - target과 nearest matching → 잔차 측정
    - bin search로 (TX, TY) 최적값
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

# 검증 임계값 — 함수 인자 기본값
DEFAULT_MATCH_TOLERANCE_MM = 300.0
DEFAULT_BRUTE_BIN_MM = 100_000.0   # 1차 brute search 격자 크기


@dataclass
class AlignResult:
    """정합 결과."""
    tx: float
    ty: float
    matched_pairs: int
    total_source: int
    match_rate: float           # matched / total_source
    error_median_mm: float
    error_max_mm: float
    derivation: List[str] = field(default_factory=list)


def align_point_clouds(
    source_pts: List[Tuple[float, float]],
    target_pts: List[Tuple[float, float]],
    tolerance_mm: float = DEFAULT_MATCH_TOLERANCE_MM,
    brute_bin_mm: float = DEFAULT_BRUTE_BIN_MM,
    refine_steps: int = 3,
) -> AlignResult:
    """source_pts에 (TX, TY)를 적용하면 target_pts와 정합되는 최적값.

    Returns:
        AlignResult
    """
    if not source_pts or not target_pts:
        return AlignResult(0, 0, 0, len(source_pts), 0.0, 0.0, 0.0)

    # 1차: 모든 (src, tgt) 쌍에서 후보 (TX, TY) 생성 → 가장 빈번한 bucket
    from collections import Counter
    candidates: Counter = Counter()
    bucket_size = max(brute_bin_mm / 100, tolerance_mm)
    for sx, sy in source_pts:
        for tx_p, ty_p in target_pts:
            cand_tx = tx_p - sx
            cand_ty = ty_p - sy
            bx = round(cand_tx / bucket_size) * bucket_size
            by = round(cand_ty / bucket_size) * bucket_size
            candidates[(bx, by)] += 1

    if candidates:
        (tx0, ty0), _ = candidates.most_common(1)[0]
    else:
        tx0, ty0 = 0.0, 0.0

    # 2차 refine: bin search (점점 작은 격자)
    best_tx, best_ty = tx0, ty0
    best_score = _score_alignment(source_pts, target_pts, tx0, ty0, tolerance_mm)

    bin_size = brute_bin_mm
    for _ in range(refine_steps):
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                tx = best_tx + dx * bin_size
                ty = best_ty + dy * bin_size
                score = _score_alignment(source_pts, target_pts, tx, ty, tolerance_mm)
                if score[0] > best_score[0]:
                    best_score = score
                    best_tx, best_ty = tx, ty
        bin_size /= 5.0   # 격자 축소

    matched_count, errors = best_score
    match_rate = matched_count / len(source_pts) if source_pts else 0.0
    median_err = sorted(errors)[len(errors) // 2] if errors else 0.0
    max_err = max(errors) if errors else 0.0

    return AlignResult(
        tx=best_tx,
        ty=best_ty,
        matched_pairs=matched_count,
        total_source=len(source_pts),
        match_rate=match_rate,
        error_median_mm=median_err,
        error_max_mm=max_err,
        derivation=["brute+refine"],
    )


def _score_alignment(
    source_pts: List[Tuple[float, float]],
    target_pts: List[Tuple[float, float]],
    tx: float,
    ty: float,
    tolerance_mm: float,
) -> Tuple[int, List[float]]:
    """source에 (tx,ty) 적용 후 target과 nearest 매칭.

    Returns:
        (matched_count, errors)
    """
    matched = 0
    errors = []
    tol2 = tolerance_mm ** 2
    used_target = set()

    for sx, sy in source_pts:
        tsx, tsy = sx + tx, sy + ty
        # nearest target
        best_d2 = float("inf")
        best_t = -1
        for j, (tx_p, ty_p) in enumerate(target_pts):
            if j in used_target:
                continue
            d2 = (tx_p - tsx) ** 2 + (ty_p - tsy) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_t = j
        if best_d2 <= tol2:
            matched += 1
            errors.append(best_d2 ** 0.5)
            used_target.add(best_t)

    return matched, errors
