"""
sl_extractor.py — SL 표고 자동 파싱 (v4 P1.5)
================================================
KS 표기:
  '지하 2층 SL .%%P0 = GL. -9.05' (가장 흔한 형식, %%P0 = ±0)
  'SL=GL.-9.05'
  'SL = GL. -9.05m'
  'B2F SL +1600' (단차, 절대값 아님 — 무시)

시트별 매칭은 거리 기반 (가장 가까운 시트).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from core.v2.inspect.sheet_segmenter import SheetMeta

# KS 표기 정규식 (여러 변형 지원)
# 1. '지하 2층 SL .%%P0 = GL. -9.05' (가장 일반적)
# 2. 'SL = GL. -9.05'
# 3. 'SL=GL.+0.37'
_PAT_SL_VALUE = re.compile(
    r"SL\s*\.?\s*(?:%%P0|±0|=\s*0)?\s*=\s*GL\.\s*([+-]?\d+\.\d+)\s*m?",
    re.IGNORECASE,
)

# 층 라벨 정규식 (절대 SL 표기와 함께)
# '지하 2층 SL', '지하2층 SL', '1층 SL', 'B2F SL' (마지막은 단차일 수 있어 분리)
_PAT_FLOOR_NEAR_SL = re.compile(
    r"(지하\s*\d+\s*층|\d+\s*층|B?\d+F)\s*SL\s*\.?\s*(?:%%P0|±0)?\s*=\s*GL\.\s*([+-]?\d+\.\d+)",
    re.IGNORECASE,
)


def normalize_floor_label(raw: str) -> str:
    """'지하 2층' → 'B2F', '1층' → '1F'."""
    s = raw.strip().replace(" ", "")
    m = re.match(r"지하(\d+)층", s)
    if m:
        return f"B{m.group(1)}F"
    m = re.match(r"^(\d+)층$", s)
    if m:
        return f"{m.group(1)}F"
    m = re.match(r"^B?(\d+)F$", s, re.IGNORECASE)
    if m:
        return s.upper()
    return s


def parse_sl_value(text: str) -> Optional[float]:
    """SL 텍스트 → mm 단위 표고. 절대값 표기('= GL. ±X.X')만 인식."""
    m = _PAT_SL_VALUE.search(text)
    if not m:
        return None
    value_m = float(m.group(1))
    return value_m * 1000.0   # m → mm


def parse_floor_sl(text: str) -> Optional[Tuple[str, float]]:
    """텍스트에서 (층 라벨, SL mm) 추출.

    예: '지하 2층 SL .%%P0 = GL. -9.05' → ('B2F', -9050.0)
    """
    m = _PAT_FLOOR_NEAR_SL.search(text)
    if not m:
        return None
    floor_raw = m.group(1)
    sl_m = float(m.group(2))
    return (normalize_floor_label(floor_raw), sl_m * 1000.0)


def extract_floors_from_drawing(
    text_labels: List[Tuple[str, float, float]],
) -> Dict[str, float]:
    """전 도면 텍스트에서 층별 SL 자동 추출.

    Returns:
        {floor_id: sl_mm} — 같은 층 여러 표기 시 가장 작은 값
    """
    result: Dict[str, float] = {}
    for text, x, y in text_labels:
        parsed = parse_floor_sl(text)
        if parsed is None:
            continue
        floor, sl_mm = parsed
        if floor not in result or sl_mm < result[floor]:
            result[floor] = sl_mm
    return result


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
