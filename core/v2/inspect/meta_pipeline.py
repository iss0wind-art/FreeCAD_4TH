"""
meta_pipeline.py — DXF → DrawingMeta 통합 (v4 P1.7)
======================================================
모든 inspect 모듈을 합쳐 DrawingMeta 단일 데이터 생성.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ezdxf

from core.v2.inspect.drawing_kind_classifier import (
    DrawingKind,
    classify_drawing_kind,
)
from core.v2.inspect.layer_profiler import LayerStat, profile_layers
from core.v2.inspect.sheet_segmenter import (
    SheetMeta,
    detect_sheet_pitch,
    segment_sheets,
)
from core.v2.inspect.sl_extractor import extract_sl_per_sheet
from core.v2.inspect.text_classifier import (
    TextCategory,
    TextStats,
    classify_text,
)
from core.v2.inspect.units_detector import detect_units


@dataclass
class DrawingMeta:
    """DXF 한 장의 메타 — Phase 2 이후 모든 단계의 입력."""
    path: str
    units: str
    bbox: Tuple[float, float, float, float]
    sheets: List[SheetMeta]
    layer_stats: Dict[str, LayerStat]
    text_stats: TextStats
    drawing_kind: DrawingKind
    sl_per_sheet: Dict[str, float]                # {sheet_id: z_sl_mm}
    sheet_pitch: Tuple[Optional[float], Optional[float]]
    fingerprint: str                                # SHA256 prefix


def inspect(dxf_path: Path) -> DrawingMeta:
    """DXF 통합 분석."""
    dxf_path = Path(dxf_path)

    # 파일 fingerprint (캐시 키)
    fingerprint = _file_fingerprint(dxf_path)

    doc = ezdxf.readfile(str(dxf_path))

    # 모든 inspect 호출
    units = detect_units(doc)
    layer_stats = profile_layers(doc)
    text_stats = classify_text(doc)
    sheets = segment_sheets(doc)

    # 시트별 SL
    sl_labels_raw = [
        (lab.text, lab.x, lab.y)
        for lab in text_stats.by_category(TextCategory.SL_VALUE)
    ]
    sl_per_sheet = extract_sl_per_sheet(sheets, sl_labels_raw)
    # 시트에 z_sl 직접 채움
    for s in sheets:
        if s.sheet_id in sl_per_sheet:
            s.z_sl = sl_per_sheet[s.sheet_id]

    # 시트 피치
    pitch_x, pitch_y = detect_sheet_pitch(sheets)

    # 도면 종류
    kind = classify_drawing_kind(
        sheets=sheets,
        pitch_x=pitch_x or 0.0,
        pitch_y=pitch_y or 0.0,
        grid_x_count=text_stats.count(TextCategory.GRID_X),
        grid_y_count=text_stats.count(TextCategory.GRID_Y),
        sl_value_count=text_stats.count(TextCategory.SL_VALUE),
    )

    # 전체 bbox
    if layer_stats:
        all_xmin = min(s.bbox[0] for s in layer_stats.values())
        all_ymin = min(s.bbox[1] for s in layer_stats.values())
        all_xmax = max(s.bbox[2] for s in layer_stats.values())
        all_ymax = max(s.bbox[3] for s in layer_stats.values())
        full_bbox = (all_xmin, all_ymin, all_xmax, all_ymax)
    else:
        full_bbox = (0.0, 0.0, 0.0, 0.0)

    return DrawingMeta(
        path=str(dxf_path),
        units=units,
        bbox=full_bbox,
        sheets=sheets,
        layer_stats=layer_stats,
        text_stats=text_stats,
        drawing_kind=kind,
        sl_per_sheet=sl_per_sheet,
        sheet_pitch=(pitch_x, pitch_y),
        fingerprint=fingerprint,
    )


def _file_fingerprint(path: Path) -> str:
    """파일 SHA256 prefix 12자."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        # 큰 파일은 chunked
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]
