"""
Executor Agent (실행자 에이전트)

역할:
- Planner의 plan_json을 받아 기하학적 연산 수행
- polygon_clip(2D 분할) → freecad_mesh(3D Extrude) 파이프라인 실행
- LLM 자의적 코드 수정 엄격히 통제: 정해진 API만 호출
- FreeCAD 미설치 환경에서는 수학 계산만 수행 (graceful degradation)
"""

from __future__ import annotations

import os
from pathlib import Path
from shapely.geometry import Polygon, box

from core.polygon_clip import ColumnProfile, BeamProfile, compute_column_beam_joint, compute_multi_beam_joints
from core.freecad_mesh import FREECAD_AVAILABLE, ExtrudeRegion, regions_from_clip_result
from pipeline.state import BOQState, StateKey, PipelineStatus, BOQItem

GLTF_OUTPUT_DIR = Path("output/gltf")


def _execute_pair(pair: dict) -> BOQItem:
    """단일 기둥-보 쌍 연산 실행"""
    col_poly = Polygon(pair["vertices_2d"])
    col = ColumnProfile(
        polygon=col_poly,
        height=pair["height"],
        member_id=pair["column_id"],
    )

    beams_data = pair.get("beams", [])
    beams = [
        BeamProfile(
            polygon=Polygon(b["vertices_2d"]),
            height=b["height"],
            member_id=b["beam_id"],
        )
        for b in beams_data
    ]

    clip_result = compute_multi_beam_joints(col, beams)

    gltf_path = None
    if FREECAD_AVAILABLE and beams:
        try:
            from core.freecad_mesh import extrude_regions, export_gltf

            first_beam_poly = Polygon(beams_data[0]["vertices_2d"]) if beams_data else None
            first_beam_height = beams_data[0]["height"] if beams_data else 0.0

            if first_beam_poly:
                regions = regions_from_clip_result(
                    clip_result,
                    column_height=col.height,
                    beam_height=first_beam_height,
                    column_polygon=col_poly,
                    beam_polygon=first_beam_poly,
                )
                mesh_results = extrude_regions(regions)
                GLTF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                out_path = str(GLTF_OUTPUT_DIR / f"{col.member_id}.gltf")
                export_gltf(mesh_results, out_path)
                gltf_path = out_path
        except Exception:
            pass  # glTF 실패해도 물량 계산은 유지

    return BOQItem(
        member_id=clip_result.member_id,
        volume_m3=clip_result.volume_m3,
        formwork_area_m2=clip_result.formwork_area_m2,
        formwork_deduction_m2=clip_result.formwork_deduction_m2,
        gltf_path=gltf_path,
    )


def executor_node(state: BOQState) -> BOQState:
    """
    Executor 노드: plan_json → BOQItem 목록 + glTF 경로.
    각 기둥-보 쌍은 독립적으로 처리 (Boolean 연산 없음).
    """
    try:
        plan_json: dict = state[StateKey.PLAN_JSON]
        pairs: list[dict] = plan_json.get("pairs", [])

        if not pairs:
            return {
                **state,
                StateKey.STATUS: PipelineStatus.FAILED,
                StateKey.ERROR:  "plan_json에 처리할 쌍이 없습니다.",
            }

        boq_items = [_execute_pair(pair) for pair in pairs]
        gltf_paths = [item.gltf_path for item in boq_items if item.gltf_path]

        return {
            **state,
            StateKey.STATUS:     PipelineStatus.REVIEWING,
            StateKey.BOQ_ITEMS:  boq_items,
            StateKey.GLTF_PATHS: gltf_paths,
            StateKey.ERROR:      None,
        }

    except Exception as exc:
        return {
            **state,
            StateKey.STATUS: PipelineStatus.FAILED,
            StateKey.ERROR:  f"Executor 오류: {exc}",
        }
