"""
/api/projects — 프로젝트 + Manifest 라우터 (Phase 1 Track D, P0)

api_contract.md P0 엔드포인트:
  POST /api/projects                    — YAML 업로드 + DB 저장
  POST /api/projects/{id}/calculate     — Manifest → BOQ 파이프라인 실행
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

import api.database as db
from api.models import BOQCalculateResponse, BOQItemDTO
from core.manifest_parser import parse_manifest
from core.grid_resolver import resolve_all
from pipeline.state import BOQState

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ─────────────────────────────────────────────────────────────
# 응답 모델
# ─────────────────────────────────────────────────────────────
class ProjectCreateResponse(BaseModel):
    project_id: str
    name: str
    member_count: int
    message: str


# ─────────────────────────────────────────────────────────────
# POST /api/projects — Manifest YAML 업로드
# ─────────────────────────────────────────────────────────────
@router.post("", response_model=ProjectCreateResponse, status_code=201)
async def create_project(file: UploadFile = File(..., description=".boq.yaml 파일")):
    """
    Member Manifest YAML 업로드 → 파싱 → DB 저장.

    검증 실패 시 422 반환 (파싱 오류 상세 포함).
    이미 같은 project_id 가 존재하면 409 반환.
    """
    raw_bytes = await file.read()
    yaml_text = raw_bytes.decode("utf-8")

    try:
        manifest = parse_manifest(yaml_text)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Manifest 파싱 오류: {exc}")

    project_id = manifest.project.id

    if db.get_project(project_id) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"project_id={project_id!r} 가 이미 존재합니다",
        )

    manifest_hash = hashlib.sha256(raw_bytes).hexdigest()
    grid_json = manifest.grid.model_dump_json() if manifest.grid else None
    floors_json = json.dumps([f.model_dump() for f in manifest.floors])

    db.create_project({
        "project_id": project_id,
        "name": manifest.project.name,
        "units": manifest.project.units,
        "manifest_yaml": yaml_text,
        "manifest_hash": manifest_hash,
        "grid_json": grid_json,
        "floors_json": floors_json,
    })

    instances = _build_instance_records(manifest)
    db.insert_member_instances(instances)

    return ProjectCreateResponse(
        project_id=project_id,
        name=manifest.project.name,
        member_count=len(manifest.members),
        message="프로젝트가 생성되었습니다",
    )


def _build_instance_records(manifest) -> list[dict]:
    floor_map = {f.id: f for f in manifest.floors}
    records = []
    for inst in manifest.members:
        floor = floor_map[inst.floor]
        z_base = floor.z_base + inst.z_offset

        placement: dict = {}
        if inst.at:
            placement = {"at": inst.at.model_dump()}
        elif inst.from_ and inst.to:
            placement = {
                "from": inst.from_.model_dump(),
                "to": inst.to.model_dump(),
            }
        elif inst.polygon:
            placement = {"polygon": [p.model_dump() for p in inst.polygon]}
        elif inst.vertices_2d:
            placement = {"vertices_2d": inst.vertices_2d}

        records.append({
            "instance_id": inst.id,
            "project_id": manifest.project.id,
            "spec_symbol": inst.spec,
            "member_type": inst.type.upper(),
            "subtype": inst.subtype,
            "floor_id": inst.floor,
            "placement_json": json.dumps(placement),
            "rotation": inst.rotation,
            "z_offset": inst.z_offset,
            "z_base": z_base,
        })
    return records


# ─────────────────────────────────────────────────────────────
# POST /api/projects/{id}/calculate — Manifest → BOQ 실행
# ─────────────────────────────────────────────────────────────
@router.post("/{project_id}/calculate", response_model=BOQCalculateResponse)
def calculate_project(project_id: str):
    """
    저장된 Manifest → MemberInput[] 생성 → 기존 BOQ 파이프라인 실행.

    Phase 1: BEAM, COLUMN 만 처리. 나머지는 스킵.
    """
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id={project_id!r} 없음")

    manifest_yaml = project.get("manifest_yaml")
    if not manifest_yaml:
        raise HTTPException(status_code=422, detail="저장된 Manifest YAML 없음")

    try:
        manifest = parse_manifest(manifest_yaml)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Manifest 재파싱 오류: {exc}")

    symbols = list({m.spec for m in manifest.members})
    spec_map = db.get_spec_map(symbols)

    member_inputs = resolve_all(manifest, spec_map)
    if not member_inputs:
        raise HTTPException(
            status_code=422,
            detail="처리 가능한 부재(BEAM/COLUMN)가 없습니다",
        )

    from api.models import MemberInputDTO
    from pipeline.state import BOQState

    dto_list = [MemberInputDTO(**m) for m in member_inputs]

    from agents.planner import run_planner
    from agents.executor import run_executor
    from agents.reviewer import run_reviewer

    state = BOQState(
        project_id=project_id,
        members=[m.model_dump() for m in dto_list],
    )
    state = run_planner(state)
    state = run_executor(state)
    state = run_reviewer(state)

    job_id = db.generate_job_id()
    boq_items = [BOQItemDTO(**item) for item in state.boq_items]
    db.save_boq_job(
        job_id=job_id,
        project_id=project_id,
        status=state.status,
        boq_items=boq_items,
        total_volume_m3=state.total_volume_m3,
        total_formwork_m2=state.total_formwork_m2,
    )

    return BOQCalculateResponse(
        job_id=job_id,
        project_id=project_id,
        status=state.status,
        boq_items=boq_items,
        total_volume_m3=state.total_volume_m3,
        total_formwork_m2=state.total_formwork_m2,
    )
