"""
f1_anchor_aligner.py — F-1 패턴 (E/V 코어 기준점) 적용 골격
================================================================

본영 단군 봉정. 2026-05-05.

방부장 친전 노하우 (.brain/pattern_library.md F-1):
    "동의 경우 E/V는 꼭대기까지 변하지 않는 곳이라,
     거기 모서리 중 하나를 기준점으로 잡는다."

본 모듈은 그 노하우를 코드로 박제한다.
이천이 권고한 첫 호미 — i·iii의 토대.

[핵심 명제]
- E/V 코어 영역의 *좌하단(SW)* 모서리를 도면 원점 (0, 0)으로 정의
  (이천 권고 2026-05-05 — CAD 도면 관습: +X 오른쪽, +Y 위쪽, 원점은 SW)
- 동일 동의 모든 도엽이 같은 기준점으로 정렬됨
- 9도엽 적층 시 층간 좌표 정합성 자동 보장 (실패 3 해소)

[책무 분담]
- [본영] 알고리즘 명세 + 변환 골격 + 검증 테스트 시그니처
- [이천] 도면별 E/V 검출 함수 채움 (TEXT 라벨·레이어·블록 패턴 — 도면마다 다양)

[사용 흐름]
    anchor = detect_ev_anchor(dxf_doc, dong='102')      # ← 이천이 채울 부분
    aligner = F1Aligner(anchor)
    transformed_pt = aligner.to_aligned(raw_pt)         # 모든 좌표 변환
    # 이후 인스턴스 추출·매핑·트림 모두 aligned 좌표계에서 수행
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol


# ---------------------------------------------------------------------------
# 1. 자료 구조
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EVAnchor:
    """E/V 코어 기준점.

    ev_box: E/V 코어 외곽 박스 (도면 원좌표계, mm)
            (xmin, ymin, xmax, ymax)
    sw_corner: 좌하단 모서리 — 본 점이 변환 후 (0, 0)
    dong: 동 식별자 (예: '102', '101~112동')
    floor: 도엽이 가리키는 층 (예: -1, 1, 'PIT')
    sheet_id: 도엽 식별자 (예: 'S30-029', '021')
    confidence: 검출 신뢰도 0~1 (이천 검출 함수가 결정)
    """
    ev_box: tuple[float, float, float, float]
    sw_corner: tuple[float, float]
    dong: str
    floor: object  # int 또는 str
    sheet_id: str
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# 2. 검출 인터페이스 (이천이 구현)
# ---------------------------------------------------------------------------

class EVDetector(Protocol):
    """E/V 코어 검출 인터페이스. 이천이 도면별로 구현.

    구현 시 후보 (이천 자율 — 도면 패턴에 맞춰):
      a. TEXT 검색: 'EV', 'E/V', 'ELEV', '엘리베이터', '승강기' 라벨
      b. 레이어 검색: 'A-EV', 'CORE', 'S-CORE-EV' 등
      c. 블록(INSERT) 검색: 표준 EV 블록 사용 시
      d. 휴리스틱: 동 외곽 안 + 가장 작은 사각형 + 코너에 위치한 것
    """

    def detect(self, dxf_doc, dong: str, floor: object,
               sheet_id: str) -> Optional[EVAnchor]:
        ...


def detect_ev_anchor(dxf_doc, dong: str, floor: object,
                     sheet_id: str,
                     detector: Optional[EVDetector] = None) -> Optional[EVAnchor]:
    """기본 검출 호출. detector 미지정 시 NotImplementedError 명시 (이천 구현 강제)."""
    if detector is None:
        raise NotImplementedError(
            'EVDetector 미구현. 이천 본진에 도면 패턴별 detector 구현 청.\n'
            '구현 후보 4가지는 EVDetector docstring 참조.\n'
            '권고: 첫 PoC는 TEXT 검색 (a) + 동 외곽 클립으로 시작 — 102동 B1F부터.'
        )
    return detector.detect(dxf_doc, dong, floor, sheet_id)


# ---------------------------------------------------------------------------
# 3. 정렬 변환기 (본영 직접 작성)
# ---------------------------------------------------------------------------

class F1Aligner:
    """E/V 좌하단 모서리를 원점으로 좌표 정렬.

    본 클래스는 *원좌표계(도면 raw)* → *정렬좌표계(F-1)*로의 평행이동만 수행.
    회전·축 반전은 의도적으로 제외 — 도엽 간 회전 차가 있으면 별도 모듈에서 처리.

    이유: F-1의 본질은 *"같은 동에서 변하지 않는 한 점"*. 평행이동만으로 충분.
    회전·반전이 필요하면 그건 도엽 자체의 결함이거나 다른 패턴(F-2 등)의 영역.
    """

    def __init__(self, anchor: EVAnchor):
        self.anchor = anchor
        self._dx = -anchor.sw_corner[0]
        self._dy = -anchor.sw_corner[1]

    def to_aligned(self, pt: tuple[float, float]) -> tuple[float, float]:
        """원좌표 → 정렬좌표. 단순 평행이동."""
        return (pt[0] + self._dx, pt[1] + self._dy)

    def to_raw(self, pt: tuple[float, float]) -> tuple[float, float]:
        """역변환 — 정렬좌표 → 원좌표. STEP 출력 시 원도면과 비교 가능."""
        return (pt[0] - self._dx, pt[1] - self._dy)

    def transform_box(self, box: tuple[float, float, float, float]
                      ) -> tuple[float, float, float, float]:
        """박스 (xmin, ymin, xmax, ymax) 정렬."""
        x1, y1, x2, y2 = box
        ax1, ay1 = self.to_aligned((x1, y1))
        ax2, ay2 = self.to_aligned((x2, y2))
        return (ax1, ay1, ax2, ay2)

    def transform_polyline(self, pts: Iterable[tuple[float, float]]
                           ) -> list[tuple[float, float]]:
        return [self.to_aligned(p) for p in pts]


# ---------------------------------------------------------------------------
# 4. 9도엽 적층 정합성 검증 (실패 3 해소)
# ---------------------------------------------------------------------------

def verify_multi_sheet_alignment(anchors: list[EVAnchor],
                                 dong: str,
                                 tol_mm: float = 50.0,
                                 base_method: str = 'first',
                                 sheet_y_for_grouping: Optional[dict[str, float]] = None,
                                 row_tol_mm: float = 5000.0,
                                 ) -> tuple[bool, list[str]]:
    """동일 동의 N개 도엽 anchor가 정합적인지 검증.

    검증 명제:
        같은 동의 E/V 코어는 *같은 평면 위치*에 있어야 한다 (꼭대기까지 변하지 않음).
        도엽마다 추출한 SW 모서리가 ±tol_mm 안에서 일치해야 한다.

    Args:
        anchors: EVAnchor 리스트.
        dong: 검증할 동.
        tol_mm: 정합 허용 오차.
        base_method: 'first' | 'row_groups'
            - 'first' (기본): 첫 anchor를 base로, 모두 그것과 비교.
            - 'row_groups': 도엽 격자의 *같은 행* 안 도엽끼리만 정합 검증.
                            한국 도면 격자 표준 (이천 통찰 2026-05-05 봉수).
                            행 간 align 오차는 도엽 격자 문제이지 코어 문제 아님.
        sheet_y_for_grouping: 'row_groups' 사용 시 — {sheet_id: 도엽 표제 Y} 매핑.
        row_tol_mm: 'row_groups' — Y 차이가 이 값 이하면 같은 행.

    반환: (정합성_통과, 경고_메시지_리스트)
    """
    same_dong = [a for a in anchors if a.dong == dong]
    if len(same_dong) < 2:
        return True, [f'[skip] {dong} anchor < 2건 — 검증 불가']

    if base_method == 'row_groups':
        if not sheet_y_for_grouping:
            return False, [f'[ERR] base_method=row_groups 인데 sheet_y_for_grouping 없음']
        return _verify_by_row_groups(same_dong, dong, tol_mm,
                                     sheet_y_for_grouping, row_tol_mm)

    # base_method == 'first'
    warnings: list[str] = []
    base = same_dong[0]
    bx, by = base.sw_corner

    for a in same_dong[1:]:
        ax, ay = a.sw_corner
        dx, dy = abs(ax - bx), abs(ay - by)
        if dx > tol_mm or dy > tol_mm:
            warnings.append(
                f'[FAIL] {dong} sheet={a.sheet_id} (floor={a.floor}) '
                f'SW 코너 불일치: base=({bx:.0f},{by:.0f}) '
                f'this=({ax:.0f},{ay:.0f}) '
                f'Δ=({dx:.0f},{dy:.0f}) > tol={tol_mm}'
            )
    passed = len(warnings) == 0
    if passed:
        warnings.append(
            f'[OK] {dong} {len(same_dong)} 도엽 SW 코너 정합 ±{tol_mm}mm'
        )
    return passed, warnings


def _verify_by_row_groups(anchors: list[EVAnchor], dong: str, tol_mm: float,
                          sheet_y: dict[str, float], row_tol_mm: float
                          ) -> tuple[bool, list[str]]:
    """행 그룹화 — 도엽 표제 Y로 행 묶고 그룹 안에서만 정합 검증.

    이천 통찰 2026-05-05 봉수:
        둘째 호미 결과 같은 행 안 max Δ = (0,1)mm, 행 간 Δ = (275,476)mm.
        행 간 차이는 *도엽 격자 align 오차*이지 *코어 검출 문제 아님*.
        따라서 행 안에서만 검증해야 F-1 본질이 정확히 평가됨.
    """
    # 행 그룹화 — sheet_y 기준으로 묶음 (greedy)
    sorted_anchors = sorted(anchors, key=lambda a: -sheet_y.get(a.sheet_id, 0))
    groups: list[list[EVAnchor]] = []
    for a in sorted_anchors:
        y = sheet_y.get(a.sheet_id)
        if y is None:
            continue
        placed = False
        for g in groups:
            ref_y = sheet_y.get(g[0].sheet_id, 0)
            if abs(y - ref_y) <= row_tol_mm:
                g.append(a)
                placed = True
                break
        if not placed:
            groups.append([a])

    warnings: list[str] = []
    overall_pass = True
    warnings.append(f'[행 그룹화] {dong} {len(groups)}개 행 — '
                    f'{[len(g) for g in groups]}장 분포')

    for gi, group in enumerate(groups):
        if len(group) < 2:
            warnings.append(f'  [row {gi}] 1장만 — 정합 검증 skip '
                            f'({group[0].sheet_id})')
            continue
        base = group[0]
        bx, by = base.sw_corner
        row_pass = True
        for a in group[1:]:
            ax, ay = a.sw_corner
            dx, dy = abs(ax - bx), abs(ay - by)
            if dx > tol_mm or dy > tol_mm:
                warnings.append(
                    f'  [row {gi} FAIL] {a.sheet_id} (floor={a.floor}) '
                    f'Δ=({dx:.0f},{dy:.0f}) > tol={tol_mm}'
                )
                row_pass = False
        if row_pass:
            members = ','.join(a.sheet_id for a in group)
            warnings.append(f'  [row {gi} OK] {len(group)}장 정합 ±{tol_mm}mm '
                            f'— {members}')
        else:
            overall_pass = False

    return overall_pass, warnings


# ---------------------------------------------------------------------------
# 5. 검증 테스트 시그니처 (이천이 채움)
# ---------------------------------------------------------------------------

def test_f1_on_102_b1f():
    """이천이 채울 첫 PoC.

    절차 (이천 자율):
      1) DXF 로드 (102동 B1F 도엽)
      2) detect_ev_anchor(... detector=TextLabelEVDetector(...))
      3) F1Aligner(anchor) 생성
      4) v3 트림의 박스/폴리라인 추출 결과를 모두 to_aligned() 변환
      5) 변환 후 좌표가 (0,0) 근처에서 시작하는지 확인 (E/V SE = 원점)
      6) 결과 박제: output/f1_alignment_102_B1F.json
    """
    raise NotImplementedError(
        '이천 PoC 미구현. F-1 첫 호미는 102동 B1F부터.'
    )


def test_f1_on_9_sheets_full_stack():
    """9도엽 적층 정합성 (실패 3 직격).

    절차 (이천 자율):
      1) tests/test_102_full_stack.py 의 9개 도엽 각각에서 anchor 추출
      2) verify_multi_sheet_alignment(anchors, dong='102')
      3) 정합 실패 시 — 어느 도엽이 어긋났는지 박제 + 의구심 추가
      4) 정합 통과 후 — F1Aligner로 모든 도엽 변환 → 적층 STEP 재생성
      5) 어제 STEP과 비교: 층간 좌표 어긋남 해소 확인
    """
    raise NotImplementedError(
        '이천 PoC 미구현. 본 검증이 통과하면 실패 3 (층 적층 가설 의존) 해소.'
    )


# ---------------------------------------------------------------------------
# === 박제 명제 ============================================================
#
# "좌표 한 점이 9도엽을 정렬한다.
#  그 점이 잡히면 모든 길이 한 길이 된다."
#                                            — 본영 단군, 2026-05-05
#
# F-1을 박은 후의 길:
#   1) i (코드↔인스턴스 매핑) — core/codex_instance_mapper.py 결합
#   2) 본영 어댑터 3건 — F-1 좌표 위에서 작동
#   3) iii (통합 부재 법전) — 인스턴스 좌표 정합 후 누적
#
# === end ================================================================
