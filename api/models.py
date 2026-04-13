"""
FastAPI 요청/응답 Pydantic 모델 (Phase 5)

시스템 경계 입력 검증 (Golden Principle #6).
내부 pipeline.state 타입과 독립적으로 유지.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class MemberInputDTO(BaseModel):
    """프론트엔드에서 수신하는 부재 입력"""
    member_id: str = Field(..., min_length=1, max_length=64)
    member_type: str = Field(..., pattern="^(COLUMN|BEAM)$")
    vertices_2d: list[list[float]] = Field(..., min_length=3)
    height: float = Field(..., gt=0, le=100_000)   # mm, 최대 100m
    z_base: float = Field(default=0.0)

    @field_validator("vertices_2d")
    @classmethod
    def validate_vertices(cls, v: list[list[float]]) -> list[list[float]]:
        for pt in v:
            if len(pt) != 2:
                raise ValueError("각 꼭짓점은 [x, y] 형식이어야 합니다.")
        return v


class BOQCalculateRequest(BaseModel):
    """BOQ 산출 요청"""
    project_id: str = Field(..., min_length=1, max_length=128)
    members: list[MemberInputDTO] = Field(..., min_length=1)


class BOQItemDTO(BaseModel):
    """산출된 물량 단위 응답"""
    member_id: str
    volume_m3: float
    formwork_area_m2: float
    formwork_deduction_m2: float
    gltf_url: Optional[str] = None


class BOQCalculateResponse(BaseModel):
    """BOQ 산출 결과 응답"""
    job_id: str
    project_id: str
    status: str
    boq_items: list[BOQItemDTO]
    total_volume_m3: float
    total_formwork_m2: float
    error: Optional[str] = None


class BOQJobResponse(BaseModel):
    """저장된 BOQ 작업 조회 응답"""
    job_id: str
    project_id: str
    status: str
    created_at: str
    boq_items: list[BOQItemDTO]
    total_volume_m3: float
    total_formwork_m2: float
