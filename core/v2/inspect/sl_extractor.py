"""
sl_extractor.py — SL 표고 자동 파싱 (v4 P1.5)
================================================
'SL=GL.-9.05' 같은 KS 표기 → mm 단위 절대 표고.
시트별 매칭은 거리 기반 (가장 가까운 시트).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from core.v2.inspect.sheet_segmenter import SheetMeta

# KS 표기 정규식
_PAT_SL = re.compile(r"SL\s*=\s*GL\.\s*([+-]?\d+\.\d+)\s*m?", re.IGNORECASE)


def parse_sl_value(text: str) -> Optional[float]:
    """SL 텍스트 → mm 단위 표고."""
    m = _PAT_SL.search(text)
    if not m:
        return None
    value_m = float(m.group(1))
    return value_m * 1000.0   # m → mm


def extract_sl_per_sheet(
    sheets: List[SheetMeta],
    sl_labels: List[Tuple[str, float, float]],
) -> Dict[str, float]:
    """SL 라벨을 가장 가까운 시트에 매칭.

    Args:
        sheets: 시트 목록
        sl_labels: [(text, x, y), ...]

    Returns:
        {sheet_id: sl_mm}
    """
    result: Dict[str, float] = {}

    for text, x, y in sl_labels:
        sl_mm = parse_sl_value(text)
        if sl_mm is None:
            continue

        # 가장 가까운 시트 (시트 중심까지의 거리)
        best_sheet = None
        best_dist = float("inf")
        for s in sheets:
            cx = (s.bbox[0] + s.bbox[2]) / 2
            cy = (s.bbox[1] + s.bbox[3]) / 2
            d = (x - cx) ** 2 + (y - cy) ** 2
            if d < best_dist:
                best_dist = d
                best_sheet = s

        if best_sheet:
            # 한 시트에 여러 SL 있으면 가장 작은 값 (가장 낮은 SL)
            current = result.get(best_sheet.sheet_id)
            if current is None or sl_mm < current:
                result[best_sheet.sheet_id] = sl_mm

    return result
