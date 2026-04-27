"""
/api/specs — 부재 스펙 카탈로그 라우터 (Phase 1 Track D, P0)

api_contract.md P0 엔드포인트:
  GET  /api/specs
  GET  /api/specs/{symbol}
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import api.database as db

router = APIRouter(prefix="/api/specs", tags=["specs"])


class SpecResponse(BaseModel):
    symbol: str
    project_scope: str
    member_type: str
    subtype: Optional[str] = None
    width: float
    height: float
    depth: float
    thickness: float
    length: float
    wall_thickness: float
    remark: Optional[str] = None
    source: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


@router.get("", response_model=list[SpecResponse])
def list_specs(
    member_type: Optional[str] = Query(None, description="BEAM|COLUMN|SLAB|WALL|FOUNDATION"),
):
    """부재 스펙 목록 조회. member_type 으로 필터링 가능."""
    allowed = {"BEAM", "COLUMN", "SLAB", "WALL", "FOUNDATION"}
    if member_type and member_type not in allowed:
        raise HTTPException(status_code=422, detail=f"member_type은 {allowed} 중 하나여야 합니다")
    return db.list_member_specs(member_type=member_type)


@router.get("/{symbol}", response_model=SpecResponse)
def get_spec(symbol: str, project_scope: str = Query("global")):
    """단일 스펙 조회."""
    spec = db.get_member_spec(symbol, project_scope)
    if spec is None:
        raise HTTPException(
            status_code=404,
            detail=f"스펙을 찾을 수 없습니다: symbol={symbol!r}, scope={project_scope!r}",
        )
    return spec
