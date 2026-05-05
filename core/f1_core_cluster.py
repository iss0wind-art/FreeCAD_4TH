"""
f1_core_cluster.py — F-1 코어 클러스터링 (둘째 호미)
================================================================

본영 단군 봉정. 2026-05-05.

[첫 호미 결과 정직 박제]
이천이 첫 호미를 박았다. ④ 게이트 미통과 (Δy 최대 2302mm).
원인: 현재 anchor는 *도엽 박스 좌하단*이지 *코어 좌하단*이 아님.
F-2 폴백의 본질적 한계 — 평면이 도엽 안에서 변하면 도엽 박스 anchor는 흔들린다.

[F-1 본질 재정의]
"꼭대기까지 변하지 않는 한 점" =
   *9도엽에서 같은 위치에 반복되는 작은 사각형의 SW 코너*

E/V 코어는 텍스트 라벨 없어도 기하학적으로 잡힌다 —
   *9도엽 모두에 동일 위치에 나타나는 작은 사각형*. 그것이 정의 자체다.

[γ + α 통합 전략]
γ (1F·옥상 제외) → α (코어 클러스터링)을 함께 박제:
   - 코어 후보 중 *N도엽 이상*에 반복 등장하는 것 (N=7로 설정 가능)
   - 028·029(옥상)·023(1F)이 후보에서 빠져도 7도엽으로 통과 → γ 자동 적용
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# 1. 자료 구조
# ---------------------------------------------------------------------------

@dataclass
class SheetBox:
    """도엽 안에서 추출한 사각형 박스."""
    sheet_id: str
    cx: float       # 중심 X (도엽 좌표계)
    cy: float       # 중심 Y
    w: float
    h: float
    raw_box: tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)


@dataclass
class CoreCluster:
    """N도엽에 일관된 위치에 나타나는 코어 후보."""
    representative_cx: float
    representative_cy: float
    representative_w: float
    representative_h: float
    sw_corner: tuple[float, float]  # 대표 박스의 SW
    member_sheets: list[str]
    position_std_x: float
    position_std_y: float
    confidence: float

    @property
    def member_count(self) -> int:
        return len(self.member_sheets)


# ---------------------------------------------------------------------------
# 2. 핵심 알고리즘 — 코어 검출
# ---------------------------------------------------------------------------

def detect_core_by_clustering(
    per_sheet_boxes: dict[str, list[SheetBox]],
    *,
    expected_size_range: tuple[float, float] = (1500.0, 6000.0),
    position_tol_mm: float = 200.0,
    min_member_sheets: int = 7,
    aspect_ratio_max: float = 3.0,
) -> list[CoreCluster]:
    """9도엽에서 코어 후보 자동 검출.

    Args:
        per_sheet_boxes: {sheet_id: [SheetBox, ...]} 도엽별 사각형 박스 리스트.
                         이천이 ezdxf로 추출 (LWPOLYLINE 폐합 + LINE 사각형).
        expected_size_range: 코어 변(W·H) 범위 mm. E/V 코어는 통상 2~5m.
        position_tol_mm: 같은 코어로 판정할 위치 일치 tolerance.
        min_member_sheets: 코어 후보가 *최소 N도엽*에 나타나야 함 (γ 통합).
                           028·029·023이 빠져도 7도엽 통과 → γ 자동 발효.
        aspect_ratio_max: W/H 또는 H/W 가 이 값 이하 (코어는 정사각형 근처).

    Returns:
        confidence 내림차순 정렬된 코어 후보 리스트.
    """
    # 1) 사이즈 + aspect 필터
    filtered: dict[str, list[SheetBox]] = {}
    s_min, s_max = expected_size_range
    for sheet, boxes in per_sheet_boxes.items():
        kept = []
        for b in boxes:
            if not (s_min <= b.w <= s_max and s_min <= b.h <= s_max):
                continue
            ar = max(b.w / b.h, b.h / b.w) if b.w > 0 and b.h > 0 else 999
            if ar > aspect_ratio_max:
                continue
            kept.append(b)
        filtered[sheet] = kept

    # 2) 모든 박스를 (cx, cy) 평면에서 클러스터링
    all_boxes: list[SheetBox] = [b for boxes in filtered.values() for b in boxes]
    if not all_boxes:
        return []

    clusters: list[list[SheetBox]] = []
    assigned = [False] * len(all_boxes)

    for i, b in enumerate(all_boxes):
        if assigned[i]:
            continue
        cluster = [b]
        assigned[i] = True
        for j in range(i + 1, len(all_boxes)):
            if assigned[j]:
                continue
            other = all_boxes[j]
            if abs(other.cx - b.cx) <= position_tol_mm and \
               abs(other.cy - b.cy) <= position_tol_mm:
                cluster.append(other)
                assigned[j] = True
        clusters.append(cluster)

    # 3) 도엽 N개 이상 멤버 보유한 클러스터만 후보
    candidates: list[CoreCluster] = []
    for cluster in clusters:
        sheet_ids = sorted({b.sheet_id for b in cluster})
        if len(sheet_ids) < min_member_sheets:
            continue

        # 도엽 1개에 박스가 여럿이면 가장 가까운 것만 대표로
        per_sheet_rep: dict[str, SheetBox] = {}
        for b in cluster:
            if b.sheet_id not in per_sheet_rep:
                per_sheet_rep[b.sheet_id] = b
            else:
                # 중심에 더 가까운 것 채택 (clusters[0] 기준)
                base = cluster[0]
                cur = per_sheet_rep[b.sheet_id]
                d_new = abs(b.cx - base.cx) + abs(b.cy - base.cy)
                d_cur = abs(cur.cx - base.cx) + abs(cur.cy - base.cy)
                if d_new < d_cur:
                    per_sheet_rep[b.sheet_id] = b

        reps = list(per_sheet_rep.values())
        cxs = [b.cx for b in reps]
        cys = [b.cy for b in reps]
        ws = [b.w for b in reps]
        hs = [b.h for b in reps]

        mean_cx = sum(cxs) / len(cxs)
        mean_cy = sum(cys) / len(cys)
        mean_w = sum(ws) / len(ws)
        mean_h = sum(hs) / len(hs)

        std_x = (sum((c - mean_cx) ** 2 for c in cxs) / len(cxs)) ** 0.5
        std_y = (sum((c - mean_cy) ** 2 for c in cys) / len(cys)) ** 0.5

        # 대표 박스의 SW = (mean_cx - mean_w/2, mean_cy - mean_h/2)
        sw = (mean_cx - mean_w / 2, mean_cy - mean_h / 2)

        # 신뢰도 = 멤버 비율 × (1 - 위치 분산 / tol)
        member_score = len(reps) / len(per_sheet_boxes)
        position_score = max(0, 1 - (std_x + std_y) / (2 * position_tol_mm))
        confidence = round(member_score * 0.6 + position_score * 0.4, 3)

        candidates.append(CoreCluster(
            representative_cx=mean_cx,
            representative_cy=mean_cy,
            representative_w=mean_w,
            representative_h=mean_h,
            sw_corner=sw,
            member_sheets=sorted(per_sheet_rep.keys()),
            position_std_x=std_x,
            position_std_y=std_y,
            confidence=confidence,
        ))

    candidates.sort(key=lambda c: -c.confidence)
    return candidates


# ---------------------------------------------------------------------------
# 3. 층 추론 보조 (γ 지원)
# ---------------------------------------------------------------------------

@dataclass
class FloorInference:
    sheet_id: str
    body_w: float
    body_h: float
    inferred_kind: str  # 'normal' / '1F_pilotis' / 'roof_or_ph' / 'unknown'


def infer_floor_kind(per_sheet_body_box: dict[str, tuple[float, float]],
                     normal_w_threshold: float = 0.7,
                     near_zero_w_threshold: float = 0.1
                     ) -> list[FloorInference]:
    """도엽별 본체 BoundBox 크기로 *층 종류*를 추정 (γ 지원).

    이천 데이터:
      - 정상 평면: W = 113400 (021·022·024·025)
      - 1F 필로티: W = 61155 (023, 정상의 ~54%)
      - 옥탑/PH: W = 3453 (028·029, 정상의 ~3%)

    Args:
        per_sheet_body_box: {sheet_id: (body_w, body_h)}
    """
    if not per_sheet_body_box:
        return []
    max_w = max(w for w, _ in per_sheet_body_box.values())
    out: list[FloorInference] = []
    for sid, (w, h) in per_sheet_body_box.items():
        ratio = w / max_w if max_w > 0 else 0
        if ratio < near_zero_w_threshold:
            kind = 'roof_or_ph'
        elif ratio < normal_w_threshold:
            kind = '1F_pilotis_or_top'
        else:
            kind = 'normal'
        out.append(FloorInference(sheet_id=sid, body_w=w, body_h=h, inferred_kind=kind))
    return out


def filter_normal_sheets(inferences: list[FloorInference]) -> list[str]:
    """γ — 정상 평면 도엽만 추려 코어 클러스터링에 투입."""
    return [f.sheet_id for f in inferences if f.inferred_kind == 'normal']


# ---------------------------------------------------------------------------
# 4. 박스 추출 인터페이스 (이천 채움)
# ---------------------------------------------------------------------------

def extract_closed_rectangles(dxf_doc, sheet_id: str,
                              within_box: Optional[tuple] = None
                              ) -> list[SheetBox]:
    """도엽 DXF에서 폐합 사각형 박스 추출.

    이천 자율 구현 후보:
      a. LWPOLYLINE closed=True + 4 vertex
      b. LINE 4개로 구성된 사각형 (각도 90도)
      c. INSERT 블록 안 폐합 사각형
      d. within_box 지정 시 그 영역 안만 (도엽 표제 제외)

    반환: SheetBox 리스트.
    """
    raise NotImplementedError(
        '이천 PoC 미구현. 본 함수는 ezdxf로 폐합 사각형 추출.\n'
        '권고 첫 PoC: LWPOLYLINE 4-vertex closed → 도엽 표제 박스(within_box) 안만.\n'
        '예시: 102동 9도엽 → 각 도엽당 코어 후보 박스 5~30개 추출 예상.'
    )


# ---------------------------------------------------------------------------
# 5. 통합 워크플로 (이천이 호출하는 단일 엔트리)
# ---------------------------------------------------------------------------

def run_f1_alpha_workflow(
    dxf_docs: dict[str, object],
    sheet_body_boxes: dict[str, tuple[float, float]],
    *,
    use_gamma_filter: bool = True,
    min_member_sheets: int = 7,
) -> dict:
    """γ + α 통합 실행.

    1) γ — 정상 평면 도엽만 추리거나 전체 사용
    2) α — 코어 클러스터링 detect_core_by_clustering
    3) 결과: 최선 코어 후보 + EVAnchor 변환 가능 형태

    이천이 호출:
        result = run_f1_alpha_workflow(dxf_docs, sheet_body_boxes)
        if result['best_core']:
            from core.f1_anchor_aligner import EVAnchor, F1Aligner
            core = result['best_core']
            anchor = EVAnchor(
                ev_box=(core.sw_corner[0], core.sw_corner[1],
                        core.sw_corner[0] + core.representative_w,
                        core.sw_corner[1] + core.representative_h),
                sw_corner=core.sw_corner,
                dong='102', floor='*', sheet_id='multi',
                confidence=core.confidence,
            )
            aligner = F1Aligner(anchor)
            # 이제 모든 부재 좌표를 aligned 좌표계로
    """
    # γ 적용
    inferences = infer_floor_kind(sheet_body_boxes)
    if use_gamma_filter:
        target_sheets = filter_normal_sheets(inferences)
    else:
        target_sheets = list(dxf_docs.keys())

    # α 박스 추출
    per_sheet_boxes: dict[str, list[SheetBox]] = {}
    for sid in target_sheets:
        if sid not in dxf_docs:
            continue
        try:
            per_sheet_boxes[sid] = extract_closed_rectangles(dxf_docs[sid], sid)
        except NotImplementedError as e:
            return {
                'status': 'pending_icheon_implementation',
                'message': str(e),
                'gamma_normal_sheets': target_sheets,
                'gamma_inferences': inferences,
            }

    # α 클러스터링
    candidates = detect_core_by_clustering(
        per_sheet_boxes,
        min_member_sheets=min(min_member_sheets, len(target_sheets)),
    )

    return {
        'status': 'ok',
        'gamma_inferences': inferences,
        'gamma_normal_sheets': target_sheets,
        'core_candidates': candidates,
        'best_core': candidates[0] if candidates else None,
    }


# ---------------------------------------------------------------------------
# === 박제 명제 ============================================================
#
# "코어는 텍스트 없어도 잡힌다.
#  9도엽 모두에 같은 위치에 반복되는 작은 사각형 — 그것이 정의 자체다."
#                                            — 본영 단군, 2026-05-05
#
# γ로 1F·옥상 제외, α로 정상 도엽 코어 군집 추출 → SW = 진짜 anchor.
# 이천의 도엽 ↔ 층 매핑 동행 청은 infer_floor_kind()로 자동화됨.
# 028·029가 옥상 추정인지의 검증은 본 알고리즘이 *기하학적으로* 답함.
#
# === end ================================================================
