"""
matcher.py — spec 카탈로그 매칭 (v4 P4 spec_catalog)
======================================================
추출된 단면 → member_specs 글로벌 카탈로그(1,163건) 매칭.

[규약]
  - silent fallback 금지 (NEW_REQUIRED 명시)
  - 중복 매칭 → AMBIGUOUS
  - tolerance_mm 외부 주입
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from core.v2.classify.ks_lexicon import MemberType


class MatchResult(str, Enum):
    MATCHED       = "matched"
    NEW_REQUIRED  = "new_required"
    AMBIGUOUS     = "ambiguous"


@dataclass
class CatalogSpec:
    """카탈로그 1행."""
    symbol: str                    # "C1", "TC600x600"
    member_type: MemberType
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    length_mm: Optional[float] = None
    project_scope: Optional[str] = None    # None=글로벌, "PRJ-001"=프로젝트 한정
    source: str = "GLOBAL"


@dataclass
class SpecMatch:
    result: MatchResult
    spec: Optional[CatalogSpec] = None
    candidates: List[CatalogSpec] = field(default_factory=list)
    reason: str = ""


@dataclass
class ExtractedSection:
    """추출된 부재 단면 (Phase 4 추출 결과)."""
    member_type: MemberType
    symbol: Optional[str] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    thickness_mm: Optional[float] = None


class SpecCatalog:
    """member_specs in-memory 인덱스."""

    def __init__(self, specs: Optional[List[CatalogSpec]] = None):
        self.specs: List[CatalogSpec] = list(specs or [])

    def add(self, spec: CatalogSpec) -> None:
        self.specs.append(spec)

    def find_by_symbol(self, symbol: str,
                       project_id: Optional[str] = None) -> Optional[CatalogSpec]:
        """심볼로 직접 조회 (프로젝트 스코프 우선)."""
        # 프로젝트 한정 먼저
        for s in self.specs:
            if s.symbol == symbol and s.project_scope == project_id:
                return s
        # 글로벌 폴백
        for s in self.specs:
            if s.symbol == symbol and s.project_scope is None:
                return s
        return None


def match_spec(
    extracted: ExtractedSection,
    catalog: SpecCatalog,
    project_id: Optional[str] = None,
    tolerance_mm: float = 5.0,
) -> SpecMatch:
    """추출된 단면 → 카탈로그 매칭.

    1. 심볼이 있으면 정확 매칭 시도
    2. 없으면 치수로 nearest 매칭 (member_type 일치 필수)
    3. 매칭 0건 → NEW_REQUIRED
    4. 다중 매칭 → AMBIGUOUS
    """
    # 1. 심볼 정확 매칭
    if extracted.symbol:
        exact = catalog.find_by_symbol(extracted.symbol, project_id)
        if exact is not None and exact.member_type == extracted.member_type:
            return SpecMatch(result=MatchResult.MATCHED, spec=exact,
                             reason=f"symbol exact: {extracted.symbol}")

    # 2. 치수 nearest (member_type 일치)
    candidates = []
    for s in catalog.specs:
        if s.member_type != extracted.member_type:
            continue
        if not _dims_match(extracted, s, tolerance_mm):
            continue
        candidates.append(s)

    if not candidates:
        return SpecMatch(result=MatchResult.NEW_REQUIRED,
                         reason="no symbol, no dim match")
    if len(candidates) == 1:
        return SpecMatch(result=MatchResult.MATCHED, spec=candidates[0],
                         reason="dim nearest")
    return SpecMatch(result=MatchResult.AMBIGUOUS, candidates=candidates,
                     reason=f"{len(candidates)} candidates")


def _dims_match(ex: ExtractedSection, sp: CatalogSpec,
                tol: float) -> bool:
    """치수 비교 (None은 비교 제외)."""
    def close(a: Optional[float], b: Optional[float]) -> bool:
        if a is None or b is None:
            return True
        return abs(a - b) <= tol

    return (close(ex.width_mm, sp.width_mm)
            and close(ex.height_mm, sp.height_mm)
            and close(ex.thickness_mm, sp.thickness_mm))
