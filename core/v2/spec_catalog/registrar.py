"""
registrar.py — 미발견 spec 자동 등록 (v4 P4)
==============================================
NEW_REQUIRED 인 단면 → 카탈로그에 추가.
"""
from __future__ import annotations

from typing import Optional

from core.v2.spec_catalog.matcher import (
    CatalogSpec,
    ExtractedSection,
    SpecCatalog,
)


def register_new_spec(
    extracted: ExtractedSection,
    catalog: SpecCatalog,
    project_scope: str,
    auto_symbol_prefix: str = "AUTO",
) -> CatalogSpec:
    """추출된 단면을 카탈로그에 신규 등록.

    Args:
        extracted: 추출 결과
        catalog: 카탈로그 (in-place 수정)
        project_scope: 프로젝트 ID (글로벌 등록 X, 프로젝트 한정)
    """
    # 자동 심볼: AUTO-{type}-{idx}
    if extracted.symbol:
        symbol = f"{extracted.symbol}-{project_scope}"
    else:
        idx = sum(1 for s in catalog.specs
                  if s.project_scope == project_scope) + 1
        symbol = f"{auto_symbol_prefix}-{extracted.member_type.value.upper()}-{idx:04d}"

    spec = CatalogSpec(
        symbol=symbol,
        member_type=extracted.member_type,
        width_mm=extracted.width_mm,
        height_mm=extracted.height_mm,
        thickness_mm=extracted.thickness_mm,
        project_scope=project_scope,
        source="API",
    )
    catalog.add(spec)
    return spec
