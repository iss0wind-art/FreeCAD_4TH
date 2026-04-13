"""
Planner Agent (설계자 에이전트)

역할:
- 입력 부재(MemberInput 목록)를 분석
- FreeCAD Executor가 소비할 '표준화된 JSON 발주서' 생성
- 기둥-보 관계 자동 감지 (교차 판별)
- 이 단계에서 LLM 자의적 코드 수정 금지 (규칙 기반 로직만)
"""

from __future__ import annotations

from shapely.geometry import Polygon
from pipeline.state import BOQState, StateKey, PipelineStatus, MemberInput


def _detect_beam_column_pairs(inputs: list[MemberInput]) -> list[dict]:
    """
    기둥-보 교차 쌍 자동 감지.
    기둥 폴리곤과 보 폴리곤이 교차(intersects)하면 쌍으로 묶음.
    """
    columns = [m for m in inputs if m.member_type == "COLUMN"]
    beams   = [m for m in inputs if m.member_type == "BEAM"]

    pairs = []
    for col in columns:
        col_poly = Polygon(col.vertices_2d)
        beam_list = []
        for beam in beams:
            beam_poly = Polygon(beam.vertices_2d)
            if col_poly.intersects(beam_poly):
                beam_list.append({
                    "beam_id":      beam.member_id,
                    "vertices_2d":  beam.vertices_2d,
                    "height":       beam.height,
                    "z_base":       beam.z_base,
                })
        pairs.append({
            "column_id":    col.member_id,
            "vertices_2d":  col.vertices_2d,
            "height":       col.height,
            "z_base":       col.z_base,
            "beams":        beam_list,
        })

    # 보 없는 단독 기둥도 포함 (beams=[])
    return pairs


def planner_node(state: BOQState) -> BOQState:
    """
    Planner 노드: inputs → plan_json 생성.
    에러 시 status=FAILED, error 메시지 기록.
    """
    try:
        inputs: list[MemberInput] = state[StateKey.INPUTS]

        if not inputs:
            return {
                **state,
                StateKey.STATUS: PipelineStatus.FAILED,
                StateKey.ERROR:  "입력 부재가 없습니다.",
            }

        pairs = _detect_beam_column_pairs(inputs)

        plan_json = {
            "version":     "1.0",
            "total_pairs": len(pairs),
            "pairs":       pairs,
            "algorithm":   "2D_POLYGON_CLIP_PRIORITY",
        }

        return {
            **state,
            StateKey.STATUS:    PipelineStatus.EXECUTING,
            StateKey.PLAN_JSON: plan_json,
            StateKey.ERROR:     None,
        }

    except Exception as exc:
        return {
            **state,
            StateKey.STATUS: PipelineStatus.FAILED,
            StateKey.ERROR:  f"Planner 오류: {exc}",
        }
