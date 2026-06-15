"""
grid_resolver.py — 시트별 격자선 좌표 자동 추출 (v4 P2.1)
============================================================
시트 안의 X·Y 격자 라벨 위치 → x_lines, y_lines 사전 생성.

[규약]
  - 매직넘버 0건
  - 도면-내재 신호만 (격자 라벨 위치)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from core.v2.inspect.meta_pipeline import DrawingMeta
from core.v2.inspect.sheet_segmenter import SheetMeta
from core.v2.inspect.text_classifier import TextCategory, TextLabel, classify_single


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
    # 1. 시트 내 격자 텍스트 & 라인 수집
    texts = [l for l in meta.text_stats.all()
             if sheet.bbox[0] <= l.x <= sheet.bbox[2] and sheet.bbox[1] <= l.y <= sheet.bbox[3]]
    
    # 격자 후보들 (텍스트 근처의 긴 수직/수평선)
    # (가정: 텍스트 근처 2m 이내에 격자선이 있음)
    x_pos: Dict[str, List[float]] = defaultdict(list) # label -> [x_coordinates]
    y_pos: Dict[str, List[float]] = defaultdict(list) # label -> [y_coordinates]
    
    for t in texts:
        cat = classify_single(t.text)
        if cat not in [TextCategory.GRID_X, TextCategory.GRID_Y]:
            continue
            
        # 가장자리 필터링 (Zoning): 진짜 격자는 시트 가장자리에 있음
        # (시트 폭의 15% 이내 가장자리만 인정)
        x_margin = (sheet.bbox[2] - sheet.bbox[0]) * 0.15
        y_margin = (sheet.bbox[3] - sheet.bbox[1]) * 0.15
        
        is_edge_x = (t.y < sheet.bbox[1] + y_margin) or (t.y > sheet.bbox[3] - y_margin)
        is_edge_y = (t.x < sheet.bbox[0] + x_margin) or (t.x > sheet.bbox[2] - x_margin)

        label = t.text.upper()
        
        # 1-1. X-grid (수직선) -> 상/하단 가장자리에 있어야 함
        if label.startswith('X') or (label.isdigit() and 1 <= int(label) <= 99):
            if is_edge_x:
                clean_label = label if label.startswith('X') else "X"+label
                x_pos[clean_label].append(t.x)
        # 1-2. Y-grid (수평선) -> 좌/우측 가장자리에 있어야 함
        elif label.startswith('Y') or (len(label) == 1 and 'A' <= label <= 'Z'):
            if is_edge_y:
                clean_label = label if label.startswith('Y') else "Y"+label
                y_pos[clean_label].append(t.y)

    if not x_pos or not y_pos:
        return None

    x_lines = {k: sum(v) / len(v) for k, v in x_pos.items()}
    y_lines = {k: sum(v) / len(v) for k, v in y_pos.items()}

    # 원점: X1·Y1 교점 (없으면 최소값 폴백하되, 나중에 시트 정렬 시 이름표 기준으로 보정됨)
    origin_x = x_lines.get("X1", min(x_lines.values()) if x_lines else 0.0)
    origin_y = y_lines.get("Y1", min(y_lines.values()) if y_lines else 0.0)

    # 정규화: 원점 기준 상대좌표 (이 값은 로컬 추출용)
    x_lines_norm = {k: v - origin_x for k, v in x_lines.items()}
    y_lines_norm = {k: v - origin_y for k, v in y_lines.items()}

    return SheetGrid(
        sheet_id=sheet.sheet_id,
        x_lines=x_lines,  # 정규화하지 않은 CAD 원본 좌표 유지 (정렬용)
        y_lines=y_lines,
        origin=(origin_x, origin_y),
        rotation_deg=0.0,
    )


def _in_bbox(x: float, y: float,
             bbox: Tuple[float, float, float, float]) -> bool:
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]
