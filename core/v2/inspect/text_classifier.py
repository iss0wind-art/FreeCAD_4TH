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


def classify_text(doc, max_block_depth: int = 8) -> TextStats:
    """DXF 문서의 모든 TEXT/MTEXT 분류 (INSERT 블록 재귀 포함).

    Args:
        max_block_depth: INSERT 재귀 최대 깊이.

    [신호 회수 전략]
        1. modelspace의 plain TEXT/MTEXT
        2. INSERT 엔티티의 ATTRIB (보이는 라벨)
        3. INSERT가 참조하는 BLOCK 정의 안의 TEXT/MTEXT/ATTDEF (재귀, 깊이 제한)
    """
    stats = TextStats()
    msp = doc.modelspace()

    for e in msp:
        _walk_entity_for_text(e, doc, stats, depth=0,
                              max_depth=max_block_depth,
                              offset_x=0.0, offset_y=0.0)

    return stats


def _walk_entity_for_text(
    e, doc, stats: TextStats, depth: int, max_depth: int,
    offset_x: float, offset_y: float,
) -> None:
    """엔티티 1개 처리 — INSERT면 재귀."""
    etype = e.dxftype()

    # TEXT / MTEXT — 직접 추출
    if etype in ("TEXT", "MTEXT"):
        _emit_text(e, etype, stats, offset_x, offset_y)
        return

    # ATTRIB / ATTDEF — INSERT 안의 라벨
    if etype in ("ATTRIB", "ATTDEF"):
        _emit_text(e, "TEXT", stats, offset_x, offset_y)
        return

    # INSERT — ATTRIB 추출 + BLOCK 재귀
    if etype == "INSERT":
        # ATTRIB 추출 (visible attributes attached to the INSERT)
        try:
            for attrib in e.attribs:
                _emit_text(attrib, "ATTRIB", stats, offset_x, offset_y)
        except Exception:
            pass

        if depth >= max_depth:
            return

        # INSERT의 위치 + 회전 → 자식 좌표 변환 (단순 평행이동만)
        try:
            ix = float(e.dxf.insert.x) + offset_x
            iy = float(e.dxf.insert.y) + offset_y
        except Exception:
            ix, iy = offset_x, offset_y

        # BLOCK 정의 재귀
        try:
            block_name = e.dxf.name
            block = doc.blocks.get(block_name)
            if block is None:
                return
            for child in block:
                _walk_entity_for_text(child, doc, stats, depth + 1,
                                      max_depth, ix, iy)
        except Exception:
            return


def _emit_text(e, etype: str, stats: TextStats,
               offset_x: float, offset_y: float) -> None:
    """엔티티에서 텍스트·위치 추출 후 stats에 추가."""
    try:
        if etype in ("TEXT", "ATTRIB"):
            content = e.dxf.text
        else:
            content = e.plain_text() if hasattr(e, "plain_text") else e.text
    except Exception:
        return

    if not content:
        return

    try:
        if hasattr(e.dxf, "insert"):
            ip = e.dxf.insert
        else:
            ip = e.dxf.location
        x = float(ip.x) + offset_x
        y = float(ip.y) + offset_y
    except Exception:
        x, y = offset_x, offset_y

    category = classify_single(content)
    stats.add(category, content, x, y)
