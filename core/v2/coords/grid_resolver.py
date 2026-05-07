"""
grid_resolver.py — 시트별 격자선 좌표 자동 추출 (v4 P2.1)
============================================================
시트 안의 X·Y 격자 라벨 위치 → x_lines, y_lines 사전 생성.

[규약]
  - 매직넘버 0건
  - 도면-내재 신호만 (격자 라벨 위치)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.v2.inspect.meta_pipeline import DrawingMeta
from core.v2.inspect.sheet_segmenter import SheetMeta
from core.v2.inspect.text_classifier import TextCategory, TextLabel


@dataclass
class SheetGrid:
    """시트 1개의 격자선 좌표."""
    sheet_id: str
    x_lines: Dict[str, float]    # {"X1": 0, "X2": 6000, ...}
    y_lines: Dict[str, float]    # {"Y1": 0, "Y2": 8000, ...}
    origin: Tuple[float, float]  # 격자 원점 (X1·Y1 교점 또는 SW)
    rotation_deg: float = 0.0


def resolve_grid_per_sheet(meta: DrawingMeta) -> Dict[str, SheetGrid]:
    """모든 시트의 격자 좌표.

    Returns:
        {sheet_id: SheetGrid}, 격자 미검출 시트는 누락
    """
    result: Dict[str, SheetGrid] = {}

    for sheet in meta.sheets:
        grid = _resolve_one_sheet(sheet, meta)
        if grid:
            result[sheet.sheet_id] = grid

    return result


def _resolve_one_sheet(sheet: SheetMeta, meta: DrawingMeta) -> Optional[SheetGrid]:
    """시트 1개의 격자 추출."""
    # 시트 내 격자 라벨 모으기 (sheet_segmenter가 이미 채움)
    x_in_sheet = sheet.grid_x_labels
    y_in_sheet = sheet.grid_y_labels

    # 폴백: 시트 bbox 내 격자 라벨 직접 검색
    if not x_in_sheet:
        x_in_sheet = [
            (lab.text, lab.x, lab.y)
            for lab in meta.text_stats.by_category(TextCategory.GRID_X)
            if _in_bbox(lab.x, lab.y, sheet.bbox)
        ]
    if not y_in_sheet:
        y_in_sheet = [
            (lab.text, lab.x, lab.y)
            for lab in meta.text_stats.by_category(TextCategory.GRID_Y)
            if _in_bbox(lab.x, lab.y, sheet.bbox)
        ]

    if not x_in_sheet or not y_in_sheet:
        return None

    # 라벨별 위치 (같은 라벨 여러 개면 평균)
    x_pos: Dict[str, List[float]] = {}
    for text, x, _ in x_in_sheet:
        x_pos.setdefault(text.upper(), []).append(x)
    y_pos: Dict[str, List[float]] = {}
    for text, _, y in y_in_sheet:
        y_pos.setdefault(text.upper(), []).append(y)

    x_lines = {k: sum(v) / len(v) for k, v in x_pos.items()}
    y_lines = {k: sum(v) / len(v) for k, v in y_pos.items()}

    # 원점: X1·Y1 교점 → 가장 작은 라벨 폴백
    origin_x = x_lines.get("X1", min(x_lines.values()))
    origin_y = y_lines.get("Y1", min(y_lines.values()))

    # 정규화: 원점 기준 상대좌표
    x_lines_norm = {k: v - origin_x for k, v in x_lines.items()}
    y_lines_norm = {k: v - origin_y for k, v in y_lines.items()}

    return SheetGrid(
        sheet_id=sheet.sheet_id,
        x_lines=x_lines_norm,
        y_lines=y_lines_norm,
        origin=(origin_x, origin_y),
        rotation_deg=0.0,    # 회전은 v4.1+ (지금은 직각만)
    )


def _in_bbox(x: float, y: float,
             bbox: Tuple[float, float, float, float]) -> bool:
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]
