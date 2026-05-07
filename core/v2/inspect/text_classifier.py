"""
text_classifier.py — TEXT/MTEXT 7부류 자동 분류 (v4 P1.3)
============================================================
KS 표준 정규식 기반.

[규약]
  - 정규식은 KS 표준만 (사전지식 OK)
  - 매직넘버 0건
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


# ─────────────────────────────────────────────────────────────
# 카테고리
# ─────────────────────────────────────────────────────────────

class TextCategory(str, Enum):
    GRID_X       = "grid_x"
    GRID_Y       = "grid_y"
    FLOOR        = "floor"
    SL_VALUE     = "sl_value"
    SECTION_CODE = "section_code"
    SHEET_CODE   = "sheet_code"
    DIM          = "dim"
    UNKNOWN      = "unknown"


# ─────────────────────────────────────────────────────────────
# KS 표준 정규식 (사전지식)
# ─────────────────────────────────────────────────────────────

_PAT_GRID_X = re.compile(r"^X\d+[a-z]?$", re.IGNORECASE)
_PAT_GRID_Y = re.compile(r"^Y\d+[a-z]?$", re.IGNORECASE)
_PAT_FLOOR  = re.compile(r"^(B?\d+F|RF|MF|PIT)$", re.IGNORECASE)
_PAT_SL     = re.compile(r"SL\s*=\s*GL\.\s*[+-]?\d+\.\d+", re.IGNORECASE)
_PAT_SECTION = re.compile(r"^(C|TC|RG|G|B|TB|FB|W|F)\d+[A-Z]?$", re.IGNORECASE)
_PAT_SHEET   = re.compile(r"^S\d{2}-\d{3}$", re.IGNORECASE)
_PAT_DIM     = re.compile(r"^\d+(\.\d+)?$")


# ─────────────────────────────────────────────────────────────
# 라벨 + 통계
# ─────────────────────────────────────────────────────────────

@dataclass
class TextLabel:
    text: str
    x: float
    y: float
    category: TextCategory


@dataclass
class TextStats:
    """카테고리별 텍스트 라벨 모음."""
    labels: Dict[TextCategory, List[TextLabel]] = field(
        default_factory=lambda: {c: [] for c in TextCategory}
    )

    def add(self, category: TextCategory, text: str, x: float, y: float) -> None:
        label = TextLabel(text=text, x=x, y=y, category=category)
        self.labels.setdefault(category, []).append(label)

    def count(self, category: TextCategory) -> int:
        return len(self.labels.get(category, []))

    def by_category(self, category: TextCategory) -> List[TextLabel]:
        return self.labels.get(category, [])

    def all(self) -> List[TextLabel]:
        return [lab for labs in self.labels.values() for lab in labs]


# ─────────────────────────────────────────────────────────────
# 분류 함수
# ─────────────────────────────────────────────────────────────

def classify_single(text: str) -> TextCategory:
    """단일 문자열 → 카테고리."""
    if not text:
        return TextCategory.UNKNOWN
    t = text.strip()

    # 우선순위 (구체적인 패턴 먼저)
    if _PAT_SHEET.match(t):
        return TextCategory.SHEET_CODE
    if _PAT_SL.search(t):
        return TextCategory.SL_VALUE
    if _PAT_FLOOR.match(t):
        return TextCategory.FLOOR
    if _PAT_GRID_X.match(t):
        return TextCategory.GRID_X
    if _PAT_GRID_Y.match(t):
        return TextCategory.GRID_Y
    if _PAT_SECTION.match(t):
        return TextCategory.SECTION_CODE
    if _PAT_DIM.match(t):
        return TextCategory.DIM

    return TextCategory.UNKNOWN


def classify_text(doc) -> TextStats:
    """DXF 문서의 모든 TEXT/MTEXT 분류."""
    stats = TextStats()
    msp = doc.modelspace()

    for e in msp:
        etype = e.dxftype()
        if etype not in ("TEXT", "MTEXT"):
            continue

        # 텍스트 추출
        try:
            if etype == "TEXT":
                content = e.dxf.text
            else:
                # MTEXT: plain_text() 사용
                content = e.plain_text() if hasattr(e, "plain_text") else e.text
        except Exception:
            continue

        # 위치 추출
        try:
            if hasattr(e.dxf, "insert"):
                ip = e.dxf.insert
            else:
                ip = e.dxf.location
            x, y = float(ip.x), float(ip.y)
        except Exception:
            x, y = 0.0, 0.0

        category = classify_single(content)
        stats.add(category, content, x, y)

    return stats
