"""
section_text.py — KS 단면 표기 자동 파싱 (v4 P4)
==================================================
'C1: 600x600', 'RG1(400x800)', 'TC1' 등.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class SectionSpec:
    """단면 사양."""
    symbol: str            # "C1", "RG1", "TC2"
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    thickness_mm: Optional[float] = None    # WALL/SLAB
    raw_text: str = ""


# KS 단면 표기 정규식
_PAT_WxH = re.compile(r"(\d+)\s*[xX×]\s*(\d+)")
_PAT_SYMBOL = re.compile(r"([CTGRBFW]+\d+[A-Z]?)", re.IGNORECASE)
_PAT_THK = re.compile(r"(\d+)\s*t\s*(?:hk)?", re.IGNORECASE)


def parse_section_text(text: str) -> Optional[SectionSpec]:
    """단일 텍스트 → SectionSpec.

    예시:
        'C1: 600x600' → SectionSpec(symbol='C1', w=600, h=600)
        'RG1(400x800)' → ...
        'C1' → SectionSpec(symbol='C1')  # 치수 미지정
        '200t' → SectionSpec(thickness_mm=200) — 슬라브/벽 두께
    """
    if not text:
        return None

    # 심볼 추출
    sym_m = _PAT_SYMBOL.search(text)
    symbol = sym_m.group(1).upper() if sym_m else ""

    # 치수
    wh_m = _PAT_WxH.search(text)
    if wh_m:
        w = float(wh_m.group(1))
        h = float(wh_m.group(2))
        return SectionSpec(symbol=symbol, width_mm=w, height_mm=h, raw_text=text)

    # 두께
    thk_m = _PAT_THK.search(text)
    if thk_m:
        return SectionSpec(symbol=symbol, thickness_mm=float(thk_m.group(1)), raw_text=text)

    # 심볼만
    if symbol:
        return SectionSpec(symbol=symbol, raw_text=text)

    return None


def collect_section_specs(
    text_labels: List[Tuple[str, float, float]],
) -> Dict[str, SectionSpec]:
    """모든 단면 라벨 수집.

    같은 symbol에 여러 정의 있으면 width·height·thickness가 채워진 것 우선.
    """
    result: Dict[str, SectionSpec] = {}
    for text, x, y in text_labels:
        spec = parse_section_text(text)
        if spec is None or not spec.symbol:
            continue

        existing = result.get(spec.symbol)
        if existing is None:
            result[spec.symbol] = spec
        else:
            # 치수 더 풍부한 것 채택
            existing_score = sum(
                1 for v in [existing.width_mm, existing.height_mm, existing.thickness_mm]
                if v is not None
            )
            new_score = sum(
                1 for v in [spec.width_mm, spec.height_mm, spec.thickness_mm]
                if v is not None
            )
            if new_score > existing_score:
                result[spec.symbol] = spec

    return result
