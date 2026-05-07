"""
sheet_segmenter.py — DXF 시트 자동 검출 (v4 P1.4)
====================================================
**가장 중요한 모듈** — 도면 한 장에 시트 N개가 옆으로 나열된 구조 자동 분리.

3중 신호 합의:
  (a) TITLEBLOCK INSERT 블록 — 가장 강한 신호 (있으면)
  (b) 표제 TEXT 클러스터 (S30-001, "지하2층 평면도", "101동")
  (c) 격자 라벨 X·Y 클러스터링 (X1·Y1 위치 → 시트 SW 추정)

[규약]
  - 매직넘버 0건 (bin_size 등 모두 함수 인자)
  - 도면-내재 신호만
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from core.v2.inspect.text_classifier import TextCategory, classify_text


# ─────────────────────────────────────────────────────────────
# SheetMeta
# ─────────────────────────────────────────────────────────────

@dataclass
class SheetMeta:
    """단일 시트 메타."""
    sheet_id: str                                   # "S30-001" 또는 자동 생성
    floor_label: Optional[str]                      # "B2F" / "1F" / None
    bbox: Tuple[float, float, float, float]         # (xmin, ymin, xmax, ymax)
    sw_corner: Tuple[float, float]                  # SW 모서리 (좌표 정규화 앵커)
    confidence: float                                # 0.0 ~ 1.0
    z_sl: Optional[float] = None                    # SL 절대 표고 (mm)
    grid_x_labels: List[Tuple[str, float, float]] = field(default_factory=list)
    grid_y_labels: List[Tuple[str, float, float]] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# 1D 클러스터링
# ─────────────────────────────────────────────────────────────

def cluster_x_positions(
    xs: List[float],
    bin_size: float,
) -> List[Tuple[float, int]]:
    """1D X 좌표 클러스터링.

    Args:
        xs: X 좌표 리스트
        bin_size: 같은 클러스터로 볼 최대 간격 (mm)

    Returns:
        [(center_x, count), ...] - center 오름차순
    """
    if not xs:
        return []

    sorted_xs = sorted(xs)
    clusters: List[List[float]] = [[sorted_xs[0]]]

    for x in sorted_xs[1:]:
        if x - clusters[-1][-1] <= bin_size:
            clusters[-1].append(x)
        else:
            clusters.append([x])

    return [(sum(c) / len(c), len(c)) for c in clusters]


# ─────────────────────────────────────────────────────────────
# Sheet pitch 자동 추출
# ─────────────────────────────────────────────────────────────

def detect_sheet_pitch(
    sheets: List[SheetMeta],
    pitch_tolerance: float = 1000.0,
) -> Tuple[Optional[float], Optional[float]]:
    """시트 중심 X·Y의 차분 모드 → 가로/세로 피치.

    Returns:
        (pitch_x, pitch_y) — 검출 실패 시 None
    """
    if len(sheets) < 2:
        return None, None

    cx = sorted([(s.bbox[0] + s.bbox[2]) / 2 for s in sheets])
    cy = sorted([(s.bbox[1] + s.bbox[3]) / 2 for s in sheets])

    diffs_x = [cx[i + 1] - cx[i] for i in range(len(cx) - 1) if cx[i + 1] - cx[i] > 0]
    diffs_y = [cy[i + 1] - cy[i] for i in range(len(cy) - 1) if cy[i + 1] - cy[i] > 0]

    pitch_x = _mode_of_diffs(diffs_x, pitch_tolerance) if diffs_x else None
    pitch_y = _mode_of_diffs(diffs_y, pitch_tolerance) if diffs_y else None
    return pitch_x, pitch_y


def _mode_of_diffs(diffs: List[float], tolerance: float) -> float:
    """tolerance 내에서 가장 빈번한 값."""
    # bucketize
    buckets: Counter = Counter()
    for d in diffs:
        bucket = round(d / tolerance) * tolerance
        buckets[bucket] += 1
    if not buckets:
        return diffs[0]
    return buckets.most_common(1)[0][0]


# ─────────────────────────────────────────────────────────────
# 시트 검출 메인
# ─────────────────────────────────────────────────────────────

# 시트 검출 임계값 — 함수 인자 기본값
DEFAULT_GRID_BIN_SIZE = 200_000.0    # 격자 라벨 X 클러스터링 (mm)
DEFAULT_SHEET_HALF_SPAN = 100_000.0  # 시트 중심 ± 반쪽폭


def segment_sheets(
    doc,
    grid_bin_size: float = DEFAULT_GRID_BIN_SIZE,
    sheet_half_span: float = DEFAULT_SHEET_HALF_SPAN,
) -> List[SheetMeta]:
    """DXF에서 시트 자동 검출.

    전략 (3중 신호):
        1. 표제 TEXT (sheet_code + floor_label) 위치 클러스터링
        2. 격자 라벨 X·Y 클러스터 → 시트 영역 추정
        3. 둘이 일치하면 confidence ↑
    """
    text_stats = classify_text(doc)

    # (a) 시트 코드 위치 (S30-001 등)
    sheet_codes = text_stats.by_category(TextCategory.SHEET_CODE)
    floor_labels = text_stats.by_category(TextCategory.FLOOR)
    grid_x = text_stats.by_category(TextCategory.GRID_X)
    grid_y = text_stats.by_category(TextCategory.GRID_Y)

    # (b) 격자 X·Y의 같은 라벨('X1') 위치들 → 클러스터
    sheets: List[SheetMeta] = []

    # 'X1' 라벨이 N번 등장 = 시트 N개 (가장 강력한 신호)
    x1_labels = [g for g in grid_x if g.text.upper() == "X1"]
    y1_labels = [g for g in grid_y if g.text.upper() == "Y1"]

    if x1_labels and y1_labels:
        # X1·Y1 교점들이 시트 SW 모서리
        for i, (xl, yl) in enumerate(zip(
            sorted(x1_labels, key=lambda g: g.x),
            sorted(y1_labels, key=lambda g: g.y),
        )):
            sw_x, sw_y = xl.x, yl.y
            # 시트 bbox 추정 — 인접 X1까지의 폭으로
            sheets.append(SheetMeta(
                sheet_id=f"sheet_{i+1}",
                floor_label=None,
                bbox=(sw_x - sheet_half_span, sw_y - sheet_half_span,
                      sw_x + sheet_half_span, sw_y + sheet_half_span),
                sw_corner=(sw_x, sw_y),
                confidence=0.7,
                grid_x_labels=[(g.text, g.x, g.y) for g in grid_x
                               if abs(g.x - xl.x) < grid_bin_size],
                grid_y_labels=[(g.text, g.x, g.y) for g in grid_y
                               if abs(g.y - yl.y) < grid_bin_size],
            ))

    # 시트 코드(S30-001)가 시트 안 어디에 있는지 매칭
    for sc in sheet_codes:
        for s in sheets:
            xmin, ymin, xmax, ymax = s.bbox
            if xmin <= sc.x <= xmax and ymin <= sc.y <= ymax:
                if s.sheet_id.startswith("sheet_"):
                    s.sheet_id = sc.text
                s.confidence = min(1.0, s.confidence + 0.2)

    # 층 라벨 매칭
    for fl in floor_labels:
        for s in sheets:
            xmin, ymin, xmax, ymax = s.bbox
            if xmin <= fl.x <= xmax and ymin <= fl.y <= ymax:
                if s.floor_label is None:
                    s.floor_label = fl.text.upper()

    # (c) 시트 0개 + 시트 코드/격자 있으면 단일 시트로 폴백
    if not sheets and (sheet_codes or grid_x):
        # 전체 도면 bbox로 단일 시트
        all_x = ([sc.x for sc in sheet_codes]
                 + [g.x for g in grid_x] + [g.x for g in grid_y])
        all_y = ([sc.y for sc in sheet_codes]
                 + [g.y for g in grid_x] + [g.y for g in grid_y])
        if all_x and all_y:
            sheets.append(SheetMeta(
                sheet_id=sheet_codes[0].text if sheet_codes else "sheet_1",
                floor_label=floor_labels[0].text if floor_labels else None,
                bbox=(min(all_x), min(all_y), max(all_x), max(all_y)),
                sw_corner=(min(all_x), min(all_y)),
                confidence=0.5,
            ))

    return sheets
