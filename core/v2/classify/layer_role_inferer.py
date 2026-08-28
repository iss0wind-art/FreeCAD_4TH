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
    """레이어명 + 통계 → 역할 (엄격한 규칙 적용).

    Args:
        layer: 레이어명
        stat: 해당 레이어 LayerStat
    """
    derivation = []

    # 1. 키워드 기반 하드코어 분류 (ks_lexicon.py에 정의된 명확한 구조 레이어만 허용)
    keyword_type = classify_layer_by_keyword(layer)
    
    # 2. 건축 도면의 잡선(A-TEXT, DEFPOINT, DIM 등) 원천 차단
    if layer.upper().startswith("A-") or "DEFPOINT" in layer.upper() or "DIM" in layer.upper() or "TEXT" in layer.upper():
        keyword_type = MemberType.IGNORE
        derivation.append("rule:architecture_or_anno_ignored")
    elif keyword_type != MemberType.UNKNOWN:
        derivation.append(f"keyword:{keyword_type.value}")
    else:
        # [삭제됨] 이전의 'LWPOLYLINE이면 무조건 기둥' 같은 억측 로직 완전 폐기
        # 모르는 레이어는 모른다고 확실히 분류해야 쓰레기 데이터가 섞이지 않음.
        derivation.append("unknown:no_matching_pattern")

    # 3. 신뢰도 (Confidence) 책정
    if "keyword" in str(derivation):
        confidence = 0.95
    elif "rule" in str(derivation):
        confidence = 0.99 # 명확히 거를 것은 신뢰도 높음
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
