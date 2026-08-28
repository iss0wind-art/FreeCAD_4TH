"""
dxf_loader.py — DXF 엔티티 로딩 및 가공 (v4 P1.1)
==============================================
- 블록 내부 엔티티 재귀적 추출 (Virtual Explode)
- 레이어 필터링 통합
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set, Tuple

import ezdxf


@dataclass
class FlatEntity:
    """블록에서 추출된 평면화된 엔티티 정보."""
    etype: str
    layer: str
    # LINE/LWPOLYLINE/TEXT 등 필요한 기본 정보만
    entity: any


def get_flattened_entities(
    doc: ezdxf.document.Drawing,
    target_layers: Set[str],
    target_types: Set[str],
) -> List[any]:
    """도면 전체(Modelspace + Blocks)에서 조건에 맞는 엔티티를 평면화하여 추출.
    
    Args:
        doc: ezdxf Drawing 객체
        target_layers: 대상 레이어 목록 (대문자 비교 권장)
        target_types: 대상 엔티티 타입 목록 (LINE, LWPOLYLINE 등)
    """
    msp = doc.modelspace()
    result = []
    
    upper_layers = {l.upper() for l in target_layers}
    upper_types = {t.upper() for t in target_types}

    def _visit(e, trans_layer=None):
        etype = e.dxftype()
        layer = trans_layer or e.dxf.layer
        
        if etype == "INSERT":
            try:
                # virtual_entities()는 INSERT의 변환(위치, 회전, 스케일)이 적용된 가상 엔티티들을 반환합니다.
                for be in e.virtual_entities():
                    inner_layer = be.dxf.layer
                    if inner_layer == "0":
                        inner_layer = layer
                    _visit(be, trans_layer=inner_layer)
            except Exception:
                pass
            return

        if etype in upper_types:
            if not upper_layers or layer.upper() in upper_layers:
                if trans_layer:
                    be_layer = trans_layer
                else:
                    be_layer = layer
                # 원본 또는 가상 엔티티의 레이어 강제 보정
                try:
                    e.dxf.layer = be_layer
                except:
                    pass
                result.append(e)

    for e in msp:
        _visit(e)
        
    return result
