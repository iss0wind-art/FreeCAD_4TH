"""
Member Manifest YAML 파서 — Phase 1 Track C

spec/member_manifest_schema.md v1.1 기준.
보안: yaml.safe_load 강제 (yaml.load 절대 금지 — 8조 8항).
단위: 수치 < 10 이면 m 간주 → ×1000 자동 변환 (D2-2 결재).
"""

from __future__ import annotations

import math
import re
from typing import Any, Literal, Optional, Union

import yaml
from pydantic import BaseModel, field_validator, model_validator

# ─────────────────────────────────────────────────────────────
# 단위 정규화 (D2-2)
# ─────────────────────────────────────────────────────────────
_MM_MAX = 100_000  # 100m 초과 시 HUMAN_REQUIRED


def normalize_to_mm(value: float, field_name: str = "") -> float:
    if value < 10:
        converted = value * 1000
    else:
        converted = value
    if converted > _MM_MAX:
        raise ValueError(
            f"HUMAN_REQUIRED: {field_name}={value} → {converted}mm 가 허용 범위({_MM_MAX}mm) 초과"
        )
    return converted


# ─────────────────────────────────────────────────────────────
# 좌표 헬퍼
# ─────────────────────────────────────────────────────────────
class GridRef(BaseModel):
    grid: Optional[list[str]] = None  # ["A", "1"]
    xy: Optional[list[float]] = None

    @model_validator(mode="after")
    def _one_of(self) -> "GridRef":
        if (self.grid is None) == (self.xy is None):
            raise ValueError("grid 또는 xy 중 정확히 하나를 사용하세요")
        if self.grid is not None and len(self.grid) != 2:
            raise ValueError("grid는 [x_key, y_key] 형식이어야 합니다")
        return self


# ─────────────────────────────────────────────────────────────
# 프로젝트 메타
# ─────────────────────────────────────────────────────────────
_ID_RE = re.compile(r"^[A-Za-z0-9\-_]{1,64}$")


class ProjectMeta(BaseModel):
    id: str
    name: str
    units: Literal["mm", "m"] = "mm"
    default_concrete_grade: Optional[str] = None

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError(f"project.id 형식 오류: {v!r}")
        return v


# ─────────────────────────────────────────────────────────────
# 그리드
# ─────────────────────────────────────────────────────────────
class GridConfig(BaseModel):
    origin: list[float] = [0.0, 0.0]
    rotation: float = 0.0
    x_lines: dict[str, float]
    y_lines: dict[str, float]

    @field_validator("origin")
    @classmethod
    def _origin_len(cls, v: list[float]) -> list[float]:
        if len(v) != 2:
            raise ValueError("grid.origin은 [x, y] 2-요소 리스트여야 합니다")
        return v


# ─────────────────────────────────────────────────────────────
# 층 정의
# ─────────────────────────────────────────────────────────────
_FLOOR_ID_RE = re.compile(r"^.{1,32}$")


class FloorDef(BaseModel):
    id: str
    z_base: float
    height: float

    @field_validator("z_base", "height")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("z_base, height는 0 이상이어야 합니다")
        return v


# ─────────────────────────────────────────────────────────────
# 부재 인스턴스
# ─────────────────────────────────────────────────────────────
MemberType = Literal["column", "beam", "slab", "wall", "foundation"]
SubType = Optional[Literal["edge_beam", "transfer_beam", "cantilever_beam"]]

_MEMBER_ID_RE = re.compile(r"^[A-Za-z0-9\-_]{1,64}$")


class MemberInstance(BaseModel):
    id: str
    spec: str
    type: MemberType
    floor: str
    rotation: float = 0.0
    z_offset: float = 0.0
    subtype: SubType = None

    # 배치 패턴 (정확히 1개)
    at: Optional[GridRef] = None
    from_: Optional[GridRef] = None
    to: Optional[GridRef] = None
    polygon: Optional[list[GridRef]] = None
    vertices_2d: Optional[list[list[float]]] = None

    model_config = {"populate_by_name": True}

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not _MEMBER_ID_RE.match(v):
            raise ValueError(f"member.id 형식 오류: {v!r}")
        return v

    @field_validator("z_offset")
    @classmethod
    def _z_offset_range(cls, v: float) -> float:
        if not (-10000 <= v <= 10000):
            raise ValueError("z_offset은 -10000 ~ +10000 범위여야 합니다")
        return v

    @model_validator(mode="after")
    def _placement_check(self) -> "MemberInstance":
        patterns = [
            self.at is not None,
            self.from_ is not None or self.to is not None,
            self.polygon is not None,
            self.vertices_2d is not None,
        ]
        active = sum(patterns)
        if active == 0:
            raise ValueError(f"member {self.id!r}: 배치 패턴(at/from+to/polygon/vertices_2d) 누락")
        if active > 1:
            raise ValueError(f"member {self.id!r}: 배치 패턴은 정확히 1개만 사용")
        if (self.from_ is None) != (self.to is None):
            raise ValueError(f"member {self.id!r}: from/to 는 함께 사용해야 합니다")
        return self


# ─────────────────────────────────────────────────────────────
# 최상위 매니페스트
# ─────────────────────────────────────────────────────────────
class ManifestModel(BaseModel):
    version: str = "1.0"
    project: ProjectMeta
    grid: Optional[GridConfig] = None
    floors: list[FloorDef]
    members: list[MemberInstance]

    @model_validator(mode="after")
    def _semantic_checks(self) -> "ManifestModel":
        floor_ids = {f.id for f in self.floors}
        member_ids: set[str] = set()

        for m in self.members:
            if m.id in member_ids:
                raise ValueError(f"member.id 중복: {m.id!r}")
            member_ids.add(m.id)

            if m.floor not in floor_ids:
                raise ValueError(f"member {m.id!r}: floor={m.floor!r} 가 floors 목록에 없음")

            if self.grid is None:
                _require_no_grid_ref(m)
            else:
                _validate_grid_refs(m, self.grid)

        return self


def _require_no_grid_ref(m: MemberInstance) -> None:
    refs = []
    if m.at and m.at.grid:
        refs.append("at.grid")
    if m.from_ and m.from_.grid:
        refs.append("from.grid")
    if m.to and m.to.grid:
        refs.append("to.grid")
    if refs:
        raise ValueError(
            f"member {m.id!r}: grid 설정 없이 grid 참조({refs}) 사용 불가"
        )


def _validate_grid_refs(m: MemberInstance, grid: GridConfig) -> None:
    for ref_name, ref in [("at", m.at), ("from", m.from_), ("to", m.to)]:
        if ref and ref.grid:
            x_key, y_key = ref.grid
            if x_key not in grid.x_lines:
                raise ValueError(
                    f"member {m.id!r}: {ref_name}.grid[0]={x_key!r} 가 grid.x_lines에 없음"
                )
            if y_key not in grid.y_lines:
                raise ValueError(
                    f"member {m.id!r}: {ref_name}.grid[1]={y_key!r} 가 grid.y_lines에 없음"
                )


# ─────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────
def parse_manifest(yaml_text: str) -> ManifestModel:
    """
    YAML 텍스트 → ManifestModel.

    보안: yaml.safe_load 강제.
    from/to 키는 Python 예약어 충돌을 피해 from_ 로 매핑.
    """
    raw: dict[str, Any] = yaml.safe_load(yaml_text)
    if not isinstance(raw, dict):
        raise ValueError("매니페스트는 YAML 딕셔너리여야 합니다")

    members_raw = raw.get("members", [])
    normalized: list[dict[str, Any]] = []
    for m in members_raw:
        entry = dict(m)
        if "from" in entry:
            entry["from_"] = entry.pop("from")
        normalized.append(entry)

    raw["members"] = normalized
    return ManifestModel.model_validate(raw)
