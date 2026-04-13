"""
LangGraph 워크플로우 그래프 (BOQ MAS 오케스트레이션)

노드:       planner → executor → reviewer
엣지:       reviewer → (approved | retry→planner | human_required)
제어 방식:  노드-엣지 State Machine (자유 채팅 루프 금지)
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from agents.planner import planner_node
from agents.executor import executor_node
from agents.reviewer import reviewer_node, routing_function
from pipeline.state import BOQState, StateKey, PipelineStatus, MemberInput, initial_state


def _after_planner(state: BOQState) -> str:
    """Planner 후 라우팅: FAILED 즉시 종료, 그 외 executor 진행"""
    if state[StateKey.STATUS] == PipelineStatus.FAILED:
        return "end"
    return "executor"


def build_boq_graph() -> StateGraph:
    """BOQ MAS 그래프 빌드 (실행은 .compile() 후 .invoke() 호출)"""
    graph = StateGraph(dict)

    # 노드 등록
    graph.add_node("planner",  planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reviewer", reviewer_node)

    # 엣지 정의: Planner 실패 시 즉시 종료
    graph.set_entry_point("planner")
    graph.add_conditional_edges(
        "planner",
        _after_planner,
        {"executor": "executor", "end": END},
    )
    graph.add_edge("executor", "reviewer")

    # Reviewer 조건부 엣지
    graph.add_conditional_edges(
        "reviewer",
        routing_function,
        {
            "approved":       END,
            "retry":          "planner",    # 최대 3회 재시도
            "human_required": END,          # HITL: 외부에서 처리
        },
    )

    return graph


def run_boq_pipeline(inputs: list[MemberInput]) -> BOQState:
    """
    BOQ 파이프라인 실행 진입점.
    inputs: 프론트엔드에서 수신한 부재 목록
    반환:   최종 BOQState (status, boq_items, gltf_paths 포함)
    """
    graph = build_boq_graph()
    app = graph.compile()

    state = initial_state(inputs)
    final_state = app.invoke(state)
    return final_state
