"""
LangGraph 파이프라인 통합 테스트 (Phase 4)

전체 그래프 실행: Planner → Executor → Reviewer → END
"""

import pytest
from pipeline.state import MemberInput, PipelineStatus, StateKey, BOQItem
from pipeline.graph import run_boq_pipeline, build_boq_graph


@pytest.fixture
def single_column():
    return [MemberInput(
        member_id="C1", member_type="COLUMN",
        vertices_2d=[(-300,-300),(300,-300),(300,300),(-300,300)],
        height=3000.0,
    )]

@pytest.fixture
def column_with_beam():
    return [
        MemberInput("C1", "COLUMN", [(-300,-300),(300,-300),(300,300),(-300,300)], 3000.0),
        MemberInput("B1", "BEAM",   [(-1000,-150),(1000,-150),(1000,150),(-1000,150)], 500.0),
    ]

@pytest.fixture
def two_columns_cross_beams():
    return [
        MemberInput("C1", "COLUMN", [(-300,-300),(300,-300),(300,300),(-300,300)], 3000.0),
        MemberInput("C2", "COLUMN", [(700,-300),(1300,-300),(1300,300),(700,300)], 3000.0),
        MemberInput("BX", "BEAM",   [(-1000,-150),(2000,-150),(2000,150),(-1000,150)], 500.0),
    ]


class TestBOQPipelineE2E:
    def test_single_column_approved(self, single_column):
        """기둥 단독 → APPROVED"""
        final = run_boq_pipeline(single_column)
        assert final[StateKey.STATUS] == PipelineStatus.APPROVED

    def test_column_beam_approved(self, column_with_beam):
        """기둥+보 교차 → APPROVED"""
        final = run_boq_pipeline(column_with_beam)
        assert final[StateKey.STATUS] == PipelineStatus.APPROVED

    def test_column_beam_volume_correct(self, column_with_beam):
        """전체 파이프라인 최종 체적 0.63 m³ ± 0.1%"""
        final = run_boq_pipeline(column_with_beam)
        items = final[StateKey.BOQ_ITEMS]
        assert len(items) == 1
        assert items[0].volume_m3 == pytest.approx(0.63, rel=0.001)

    def test_two_columns_both_processed(self, two_columns_cross_beams):
        """기둥 2개 → BOQItem 2개"""
        final = run_boq_pipeline(two_columns_cross_beams)
        assert final[StateKey.STATUS] == PipelineStatus.APPROVED
        assert len(final[StateKey.BOQ_ITEMS]) == 2

    def test_empty_inputs_fails(self):
        """입력 없음 → FAILED"""
        final = run_boq_pipeline([])
        assert final[StateKey.STATUS] == PipelineStatus.FAILED

    def test_review_report_exists_on_approval(self, column_with_beam):
        """APPROVED 시 ReviewReport 존재"""
        final = run_boq_pipeline(column_with_beam)
        assert final[StateKey.REVIEW_REPORT] is not None
        assert final[StateKey.REVIEW_REPORT].is_valid is True

    def test_no_error_on_success(self, column_with_beam):
        """성공 시 error=None"""
        final = run_boq_pipeline(column_with_beam)
        assert final[StateKey.ERROR] is None


class TestGraphStructure:
    def test_graph_builds_without_error(self):
        """그래프 빌드 시 예외 없음"""
        graph = build_boq_graph()
        assert graph is not None

    def test_graph_compiles(self):
        """그래프 컴파일 성공"""
        graph = build_boq_graph()
        app = graph.compile()
        assert app is not None
