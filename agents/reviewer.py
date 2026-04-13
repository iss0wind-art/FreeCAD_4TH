"""
Reviewer Agent (감리자 에이전트)

역할:
- Executor 산출물(BOQItem 목록) 논리 검증
- 음수 체적, 과도한 공제 등 물리적 불가능 값 감지
- 오류 시 RETRY (최대 3회) → Planner 재작업 지시
- 임계 초과 시 HUMAN_REQUIRED → Human-in-the-loop
"""

from __future__ import annotations

from pipeline.state import (
    BOQState, StateKey, PipelineStatus,
    BOQItem, ReviewReport,
)

MAX_RETRY = 3
MAX_VOLUME_M3 = 1000.0          # 단일 부재 최대 체적 (현실적 상한)
MAX_FORMWORK_M2 = 10000.0       # 단일 부재 최대 거푸집 면적


def _validate_boq_item(item: BOQItem) -> list[str]:
    """단일 BOQItem 검증 → 에러 메시지 목록"""
    errors = []

    if item.volume_m3 < 0:
        errors.append(f"{item.member_id}: 체적 음수 ({item.volume_m3:.6f} m³)")

    if item.volume_m3 > MAX_VOLUME_M3:
        errors.append(f"{item.member_id}: 체적 비정상적으로 큼 ({item.volume_m3:.2f} m³ > {MAX_VOLUME_M3})")

    if item.formwork_area_m2 < 0:
        errors.append(f"{item.member_id}: 거푸집 면적 음수 ({item.formwork_area_m2:.4f} m²)")

    if item.formwork_deduction_m2 < 0:
        errors.append(f"{item.member_id}: 거푸집 공제량 음수 ({item.formwork_deduction_m2:.4f} m²)")

    if item.formwork_area_m2 > MAX_FORMWORK_M2:
        errors.append(f"{item.member_id}: 거푸집 면적 비정상적으로 큼 ({item.formwork_area_m2:.2f} m²)")

    return errors


def _validate_all(boq_items: list[BOQItem]) -> ReviewReport:
    """전체 BOQItem 목록 검증"""
    all_errors = []
    warnings = []

    if not boq_items:
        all_errors.append("산출된 물량이 없습니다.")
        return ReviewReport(is_valid=False, errors=all_errors)

    for item in boq_items:
        all_errors.extend(_validate_boq_item(item))

    # 경고: 체적이 0인 항목
    zero_vol = [i.member_id for i in boq_items if i.volume_m3 == 0.0]
    if zero_vol:
        warnings.append(f"체적 0 부재: {zero_vol}")

    return ReviewReport(
        is_valid=len(all_errors) == 0,
        errors=all_errors,
        warnings=warnings,
    )


def reviewer_node(state: BOQState) -> BOQState:
    """
    Reviewer 노드: BOQItem 목록 검증 → APPROVED / RETRY / HUMAN_REQUIRED.
    """
    boq_items: list[BOQItem] = state[StateKey.BOQ_ITEMS]
    retry_count: int = state.get(StateKey.RETRY_COUNT, 0)

    report = _validate_all(boq_items)

    if report.is_valid:
        return {
            **state,
            StateKey.STATUS:        PipelineStatus.APPROVED,
            StateKey.REVIEW_REPORT: report,
            StateKey.ERROR:         None,
        }

    # 검증 실패: 재시도 여부 결정
    if retry_count >= MAX_RETRY:
        return {
            **state,
            StateKey.STATUS:        PipelineStatus.HUMAN_REQUIRED,
            StateKey.REVIEW_REPORT: report,
            StateKey.ERROR:         f"최대 재시도 초과 ({MAX_RETRY}회). 인간 감리자 개입 필요.",
        }

    return {
        **state,
        StateKey.STATUS:        PipelineStatus.PLANNING,  # Planner 재작업
        StateKey.REVIEW_REPORT: report,
        StateKey.RETRY_COUNT:   retry_count + 1,
        StateKey.ERROR:         f"검증 실패 (시도 {retry_count + 1}/{MAX_RETRY}): {report.errors}",
    }


def routing_function(state: BOQState) -> str:
    """
    Reviewer 후 라우팅 결정.
    LangGraph conditional_edges 에서 사용.
    """
    status = state[StateKey.STATUS]
    if status == PipelineStatus.APPROVED:
        return "approved"
    if status == PipelineStatus.HUMAN_REQUIRED:
        return "human_required"
    return "retry"  # PLANNING 으로 돌아감
