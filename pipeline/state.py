"""
BOQ 파이프라인 공유 상태 (LangGraph State)

모든 에이전트가 읽고 쓰는 단일 진실 공급원(Single Source of Truth).
불변성 원칙: 각 노드는 새 상태 딕셔너리를 반환, 원본 변경 없음.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class PipelineStatus(str, Enum):
    PENDING   = "PENDING"
    PLANNING  = "PLANNING"
    EXECUTING = "EXECUTING"
    REVIEWING = "REVIEWING"
    APPROVED  = "APPROVED"
    FAILED    = "FAILED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


@dataclass
class MemberInput:
    """프론트엔드에서 수신하는 단일 부재 입력"""
    member_id: str
    member_type: str          # "COLUMN" / "BEAM"
    vertices_2d: list         # [(x, y), ...] mm 단위
    height: float             # mm
    z_base: float = 0.0


@dataclass
class BOQItem:
    """산출된 물량 단위"""
    member_id: str
    volume_m3: float
    formwork_area_m2: float
    formwork_deduction_m2: float
    gltf_path: Optional[str] = None


@dataclass
class ReviewReport:
    """Reviewer 검증 결과"""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retry_count: int = 0


# LangGraph State: TypedDict 스타일로 정의
BOQState = dict  # 아래 키를 사용하는 딕셔너리

# 상태 키 상수
class StateKey:
    STATUS         = "status"           # PipelineStatus
    INPUTS         = "inputs"           # list[MemberInput]
    PLAN_JSON      = "plan_json"        # dict (Planner 출력)
    BOQ_ITEMS      = "boq_items"        # list[BOQItem]
    GLTF_PATHS     = "gltf_paths"       # list[str]
    REVIEW_REPORT  = "review_report"    # ReviewReport
    ERROR          = "error"            # str | None
    RETRY_COUNT    = "retry_count"      # int
    HUMAN_APPROVAL = "human_approval"   # bool | None


def initial_state(inputs: list[MemberInput]) -> BOQState:
    """초기 상태 생성"""
    return {
        StateKey.STATUS:         PipelineStatus.PENDING,
        StateKey.INPUTS:         inputs,
        StateKey.PLAN_JSON:      {},
        StateKey.BOQ_ITEMS:      [],
        StateKey.GLTF_PATHS:     [],
        StateKey.REVIEW_REPORT:  None,
        StateKey.ERROR:          None,
        StateKey.RETRY_COUNT:    0,
        StateKey.HUMAN_APPROVAL: None,
    }
