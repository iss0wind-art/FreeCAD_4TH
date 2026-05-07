"""
layer_role_inferer.py — 레이어 역할 자동 추론 (v4 P3.2)
=========================================================
키워드 + 통계 합의 → (member_type, confidence).

[추론 신호]
  1. KS 키워드 매칭 (정확히 일치하면 confidence 0.9)
  2. dominant entity type (LINE 위주 → BEAM/WALL, LWPOLYLINE → COLUMN/SLAB)
  3. mean entity size (column ~ 0.4-1m, wall thickness 0.2-0.4m, beam W 0.3-0.6m)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from core.v2.classify.ks_lexicon import (
    KS_KEYWORDS,
    MemberType,
    classify_layer_by_keyword,
)
from core.v2.inspect.layer_profiler import LayerStat


@dataclass
class LayerRole:
    layer: str
    member_type: MemberType
    confidence: float
    derivation: list


def infer_layer_role(
    layer: str,
    stat: LayerStat,
) -> LayerRole:
    """레이어명 + 통계 → 역할.

    Args:
        layer: 레이어명
        stat: 해당 레이어 LayerStat
    """
    derivation = []

    # 1. 키워드
    keyword_type = classify_layer_by_keyword(layer)
    if keyword_type != MemberType.UNKNOWN:
        derivation.append(f"keyword:{keyword_type.value}")

    # 2. dominant type 보정
    dom = stat.dominant_type
    if keyword_type == MemberType.UNKNOWN:
        # 키워드 없으면 dominant로 추정
        if dom == "LWPOLYLINE":
            keyword_type = MemberType.COLUMN     # 기본 가정
            derivation.append("dom:LWPOLYLINE→COLUMN")
        elif dom == "LINE":
            keyword_type = MemberType.BEAM
            derivation.append("dom:LINE→BEAM")

    # 3. confidence
    if "keyword" in str(derivation):
        confidence = 0.9
    elif "dom:" in str(derivation):
        confidence = 0.5
    else:
        confidence = 0.0

    return LayerRole(
        layer=layer,
        member_type=keyword_type,
        confidence=confidence,
        derivation=derivation,
    )


def infer_all_layers(layer_stats: Dict[str, LayerStat]) -> Dict[str, LayerRole]:
    """모든 레이어 역할 일괄 추론."""
    return {
        layer: infer_layer_role(layer, stat)
        for layer, stat in layer_stats.items()
    }
