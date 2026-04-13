"""
BOQ API 라우터 (Phase 5)

엔드포인트:
- POST /api/boq/calculate  — 물량 산출 요청
- GET  /api/boq/{job_id}   — 저장된 결과 조회
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.database import generate_job_id, save_boq_job, get_boq_job
from api.models import (
    BOQCalculateRequest, BOQCalculateResponse,
    BOQItemDTO, BOQJobResponse,
)
from pipeline.graph import run_boq_pipeline
from pipeline.state import MemberInput, PipelineStatus, StateKey

router = APIRouter(prefix="/api/boq", tags=["BOQ"])


def _dto_to_member_input(dto) -> MemberInput:
    return MemberInput(
        member_id=dto.member_id,
        member_type=dto.member_type,
        vertices_2d=[tuple(pt) for pt in dto.vertices_2d],
        height=dto.height,
        z_base=dto.z_base,
    )


@router.post("/calculate", response_model=BOQCalculateResponse)
def calculate_boq(request: BOQCalculateRequest) -> BOQCalculateResponse:
    """
    BOQ 물량 산출.
    1. 입력 검증 (Pydantic)
    2. MAS 파이프라인 실행 (Planner→Executor→Reviewer)
    3. 결과 DB 저장
    4. 응답 반환
    """
    job_id = generate_job_id()
    inputs = [_dto_to_member_input(m) for m in request.members]

    final_state = run_boq_pipeline(inputs)
    status = final_state[StateKey.STATUS]
    boq_items_raw = final_state.get(StateKey.BOQ_ITEMS, [])
    error = final_state.get(StateKey.ERROR)

    boq_dtos = [
        BOQItemDTO(
            member_id=item.member_id,
            volume_m3=item.volume_m3,
            formwork_area_m2=item.formwork_area_m2,
            formwork_deduction_m2=item.formwork_deduction_m2,
            gltf_url=item.gltf_path,
        )
        for item in boq_items_raw
    ]

    total_volume = round(sum(i.volume_m3 for i in boq_dtos), 6)
    total_formwork = round(sum(i.formwork_area_m2 for i in boq_dtos), 4)

    save_boq_job(
        job_id=job_id,
        project_id=request.project_id,
        status=status.value,
        boq_items=boq_dtos,
        total_volume_m3=total_volume,
        total_formwork_m2=total_formwork,
        error=error,
    )

    return BOQCalculateResponse(
        job_id=job_id,
        project_id=request.project_id,
        status=status.value,
        boq_items=boq_dtos,
        total_volume_m3=total_volume,
        total_formwork_m2=total_formwork,
        error=error,
    )


@router.get("/{job_id}", response_model=BOQJobResponse)
def get_boq_result(job_id: str) -> BOQJobResponse:
    """저장된 BOQ 결과 조회"""
    result = get_boq_job(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return result
