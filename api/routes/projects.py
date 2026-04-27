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

from fastapi import APIRouter, HTTPException, Path, UploadFile, File
from pydantic import BaseModel

import api.database as db
from agents.executor import executor_node
from agents.planner import planner_node
from agents.reviewer import reviewer_node
from api.models import BOQCalculateResponse, BOQItemDTO, MemberInputDTO
from core.grid_resolver import resolve_all
from core.manifest_parser import ManifestModel, parse_manifest
from pipeline.state import BOQState

router = APIRouter(prefix="/api/projects", tags=["projects"])

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


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
async def create_project(
    file: UploadFile = File(..., description=".boq.yaml 파일"),
) -> ProjectCreateResponse:
    raw_bytes = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"파일 크기 제한 초과 (최대 {_MAX_UPLOAD_BYTES // 1024 // 1024}MB)")

    try:
        yaml_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="파일 인코딩 오류: UTF-8 만 허용합니다")

    try:
        manifest = parse_manifest(yaml_text)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Manifest 파싱 오류: {exc}")

    project_id = manifest.project.id
    if db.get_project(project_id) is not None:
        raise HTTPException(status_code=409, detail=f"project_id={project_id!r} 가 이미 존재합니다")

    _save_project(manifest, yaml_text, raw_bytes)
    return ProjectCreateResponse(
        project_id=project_id,
        name=manifest.project.name,
        member_count=len(manifest.members),
        message="프로젝트가 생성되었습니다",
    )


def _save_project(manifest: ManifestModel, yaml_text: str, raw_bytes: bytes) -> None:
    db.create_project({
        "project_id": manifest.project.id,
        "name": manifest.project.name,
        "units": manifest.project.units,
        "manifest_yaml": yaml_text,
        "manifest_hash": hashlib.sha256(raw_bytes).hexdigest(),
        "grid_json": manifest.grid.model_dump_json() if manifest.grid else None,
        "floors_json": json.dumps([f.model_dump() for f in manifest.floors]),
    })
    db.insert_member_instances(_build_instance_records(manifest))


def _extract_placement(inst) -> dict:
    if inst.at:
        return {"at": inst.at.model_dump()}
    if inst.from_ and inst.to:
        return {"from": inst.from_.model_dump(), "to": inst.to.model_dump()}
    if inst.polygon:
        return {"polygon": [p.model_dump() for p in inst.polygon]}
    return {"vertices_2d": inst.vertices_2d}


def _build_instance_records(manifest: ManifestModel) -> list[dict]:
    floor_map = {f.id: f for f in manifest.floors}
    return [
        {
            "instance_id": inst.id,
            "project_id": manifest.project.id,
            "spec_symbol": inst.spec,
            "member_type": inst.type.upper(),
            "subtype": inst.subtype,
            "floor_id": inst.floor,
            "placement_json": json.dumps(_extract_placement(inst)),
            "rotation": inst.rotation,
            "z_offset": inst.z_offset,
            "z_base": floor_map[inst.floor].z_base + inst.z_offset,
        }
        for inst in manifest.members
    ]


# ─────────────────────────────────────────────────────────────
# POST /api/projects/{id}/calculate — Manifest → BOQ 실행
# ─────────────────────────────────────────────────────────────
@router.post("/{project_id}/calculate", response_model=BOQCalculateResponse)
def calculate_project(
    project_id: str = Path(..., pattern=r"^[A-Za-z0-9\-_]{1,64}$"),
) -> BOQCalculateResponse:
    """저장된 Manifest → MemberInput[] → BOQ 파이프라인. Phase 1: BEAM/COLUMN 만."""
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

    member_inputs = _resolve_inputs(manifest)
    if not member_inputs:
        raise HTTPException(status_code=422, detail="처리 가능한 부재(BEAM/COLUMN)가 없습니다")

    return _run_pipeline(project_id, member_inputs)


def _resolve_inputs(manifest: ManifestModel) -> list[dict]:
    symbols = list({m.spec for m in manifest.members})
    spec_map = db.get_spec_map(symbols)
    return resolve_all(manifest, spec_map)


def _run_pipeline(project_id: str, member_inputs: list[dict]) -> BOQCalculateResponse:
    dto_list = [MemberInputDTO(**m) for m in member_inputs]
    state = BOQState(project_id=project_id, members=[m.model_dump() for m in dto_list])
    state = planner_node(state)
    state = executor_node(state)
    state = reviewer_node(state)

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
