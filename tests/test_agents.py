"""
MAS 에이전트 단위 테스트 (Phase 4)

검증 항목:
- Planner: 기둥-보 교차 감지, plan_json 구조
- Executor: BOQItem 생성, 독립 연산
- Reviewer: 검증 로직, RETRY/HUMAN_REQUIRED 분기
- routing_function: 상태별 라우팅
"""

import pytest
from pipeline.state import (
    MemberInput, BOQItem, PipelineStatus,
    StateKey, initial_state,
)
from agents.planner import planner_node, _detect_beam_column_pairs
from agents.executor import executor_node
from agents.reviewer import reviewer_node, routing_function, _validate_boq_item


# ─────────────────────────────────────
# 공통 픽스처
# ─────────────────────────────────────

@pytest.fixture
def col_input():
    return MemberInput(
        member_id="C1",
        member_type="COLUMN",
        vertices_2d=[(-300, -300), (300, -300), (300, 300), (-300, 300)],
        height=3000.0,
    )

@pytest.fixture
def beam_through():
    """기둥 중앙 관통 보"""
    return MemberInput(
        member_id="B1",
        member_type="BEAM",
        vertices_2d=[(-1000, -150), (1000, -150), (1000, 150), (-1000, 150)],
        height=500.0,
    )

@pytest.fixture
def beam_no_overlap():
    """기둥과 겹치지 않는 보"""
    return MemberInput(
        member_id="B_FAR",
        member_type="BEAM",
        vertices_2d=[(500, 500), (1500, 500), (1500, 800), (500, 800)],
        height=500.0,
    )

@pytest.fixture
def state_with_inputs(col_input, beam_through):
    return initial_state([col_input, beam_through])

@pytest.fixture
def state_no_inputs():
    return initial_state([])


# ─────────────────────────────────────
# Planner 테스트
# ─────────────────────────────────────

class TestPlannerNode:
    def test_plan_json_structure(self, state_with_inputs):
        result = planner_node(state_with_inputs)
        plan = result[StateKey.PLAN_JSON]
        assert "version" in plan
        assert "pairs" in plan
        assert "algorithm" in plan
        assert plan["algorithm"] == "2D_POLYGON_CLIP_PRIORITY"

    def test_detects_intersecting_beam(self, state_with_inputs):
        result = planner_node(state_with_inputs)
        pairs = result[StateKey.PLAN_JSON]["pairs"]
        assert len(pairs) == 1
        assert pairs[0]["column_id"] == "C1"
        assert len(pairs[0]["beams"]) == 1
        assert pairs[0]["beams"][0]["beam_id"] == "B1"

    def test_no_beam_if_no_overlap(self, col_input, beam_no_overlap):
        state = initial_state([col_input, beam_no_overlap])
        result = planner_node(state)
        pairs = result[StateKey.PLAN_JSON]["pairs"]
        assert len(pairs) == 1
        assert len(pairs[0]["beams"]) == 0

    def test_empty_inputs_returns_failed(self, state_no_inputs):
        result = planner_node(state_no_inputs)
        assert result[StateKey.STATUS] == PipelineStatus.FAILED
        assert result[StateKey.ERROR] is not None

    def test_status_becomes_executing_on_success(self, state_with_inputs):
        result = planner_node(state_with_inputs)
        assert result[StateKey.STATUS] == PipelineStatus.EXECUTING

    def test_planner_does_not_mutate_input_state(self, state_with_inputs):
        """불변성: 입력 상태 변경 없음"""
        original_status = state_with_inputs[StateKey.STATUS]
        planner_node(state_with_inputs)
        assert state_with_inputs[StateKey.STATUS] == original_status

    def test_multiple_columns_each_get_pairs(self, beam_through):
        col2 = MemberInput(
            member_id="C2",
            member_type="COLUMN",
            vertices_2d=[(700, -300), (1300, -300), (1300, 300), (700, 300)],
            height=3000.0,
        )
        state = initial_state([
            MemberInput("C1", "COLUMN", [(-300,-300),(300,-300),(300,300),(-300,300)], 3000.0),
            col2,
            beam_through,
        ])
        result = planner_node(state)
        pairs = result[StateKey.PLAN_JSON]["pairs"]
        assert len(pairs) == 2


# ─────────────────────────────────────
# Executor 테스트
# ─────────────────────────────────────

class TestExecutorNode:
    def _plan_state(self, state_with_inputs):
        return planner_node(state_with_inputs)

    def test_executor_produces_boq_items(self, state_with_inputs):
        planned = planner_node(state_with_inputs)
        result = executor_node(planned)
        items = result[StateKey.BOQ_ITEMS]
        assert len(items) == 1
        assert isinstance(items[0], BOQItem)

    def test_boq_item_volume_correct(self, state_with_inputs):
        """기둥+보 관통 시 체적 ≈ 0.63 m³"""
        planned = planner_node(state_with_inputs)
        result = executor_node(planned)
        item = result[StateKey.BOQ_ITEMS][0]
        assert item.volume_m3 == pytest.approx(0.63, rel=0.001)

    def test_boq_item_member_id(self, state_with_inputs):
        planned = planner_node(state_with_inputs)
        result = executor_node(planned)
        assert result[StateKey.BOQ_ITEMS][0].member_id == "C1"

    def test_status_becomes_reviewing(self, state_with_inputs):
        planned = planner_node(state_with_inputs)
        result = executor_node(planned)
        assert result[StateKey.STATUS] == PipelineStatus.REVIEWING

    def test_executor_no_pairs_returns_failed(self, state_with_inputs):
        state = {
            **state_with_inputs,
            StateKey.PLAN_JSON: {"pairs": [], "version": "1.0"},
            StateKey.STATUS: PipelineStatus.EXECUTING,
        }
        result = executor_node(state)
        assert result[StateKey.STATUS] == PipelineStatus.FAILED

    def test_executor_column_only_no_beams(self, col_input):
        state = initial_state([col_input])
        planned = planner_node(state)
        result = executor_node(planned)
        items = result[StateKey.BOQ_ITEMS]
        assert len(items) == 1
        # 단독 기둥 체적 = 0.6×0.6×3.0 = 1.08 m³
        assert items[0].volume_m3 == pytest.approx(1.08, rel=0.001)


# ─────────────────────────────────────
# Reviewer 테스트
# ─────────────────────────────────────

class TestReviewerNode:
    def _valid_boq_state(self, state_with_inputs):
        planned = planner_node(state_with_inputs)
        return executor_node(planned)

    def test_valid_result_approved(self, state_with_inputs):
        executed = self._valid_boq_state(state_with_inputs)
        result = reviewer_node(executed)
        assert result[StateKey.STATUS] == PipelineStatus.APPROVED

    def test_negative_volume_triggers_retry(self, state_with_inputs):
        executed = self._valid_boq_state(state_with_inputs)
        # 강제로 음수 체적 주입
        bad_item = BOQItem("C1", volume_m3=-1.0, formwork_area_m2=5.0, formwork_deduction_m2=0.5)
        state = {**executed, StateKey.BOQ_ITEMS: [bad_item]}
        result = reviewer_node(state)
        assert result[StateKey.STATUS] == PipelineStatus.PLANNING
        assert result[StateKey.RETRY_COUNT] == 1

    def test_max_retry_triggers_human_required(self, state_with_inputs):
        executed = self._valid_boq_state(state_with_inputs)
        bad_item = BOQItem("C1", volume_m3=-1.0, formwork_area_m2=5.0, formwork_deduction_m2=0.5)
        state = {
            **executed,
            StateKey.BOQ_ITEMS: [bad_item],
            StateKey.RETRY_COUNT: 3,  # MAX_RETRY 도달
        }
        result = reviewer_node(state)
        assert result[StateKey.STATUS] == PipelineStatus.HUMAN_REQUIRED

    def test_empty_boq_items_is_invalid(self, state_with_inputs):
        executed = self._valid_boq_state(state_with_inputs)
        state = {**executed, StateKey.BOQ_ITEMS: []}
        result = reviewer_node(state)
        assert result[StateKey.STATUS] != PipelineStatus.APPROVED

    def test_review_report_populated(self, state_with_inputs):
        executed = self._valid_boq_state(state_with_inputs)
        result = reviewer_node(executed)
        assert result[StateKey.REVIEW_REPORT] is not None


class TestValidateBOQItem:
    def test_valid_item_no_errors(self):
        item = BOQItem("C1", 1.08, 7.2, 0.6)
        errors = _validate_boq_item(item)
        assert errors == []

    def test_negative_volume_error(self):
        item = BOQItem("C1", -0.1, 7.2, 0.6)
        errors = _validate_boq_item(item)
        assert any("음수" in e for e in errors)

    def test_negative_formwork_error(self):
        item = BOQItem("C1", 1.08, -1.0, 0.6)
        errors = _validate_boq_item(item)
        assert any("음수" in e for e in errors)

    def test_excessive_volume_error(self):
        item = BOQItem("C1", 9999.0, 7.2, 0.6)
        errors = _validate_boq_item(item)
        assert any("큼" in e for e in errors)


# ─────────────────────────────────────
# 라우팅 함수 테스트
# ─────────────────────────────────────

class TestRoutingFunction:
    def _state(self, status):
        return {StateKey.STATUS: status}

    def test_approved_routes_to_end(self):
        assert routing_function(self._state(PipelineStatus.APPROVED)) == "approved"

    def test_human_required_routes_correctly(self):
        assert routing_function(self._state(PipelineStatus.HUMAN_REQUIRED)) == "human_required"

    def test_planning_routes_to_retry(self):
        assert routing_function(self._state(PipelineStatus.PLANNING)) == "retry"

    def test_failed_routes_to_retry(self):
        assert routing_function(self._state(PipelineStatus.FAILED)) == "retry"
