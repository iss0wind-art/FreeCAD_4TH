"""
boq_export.py — BOQ 내보내기 (JSON / CSV)
==========================================
순수 Python 모듈. FreeCAD 의존성 없음.

[출력 포맷]
  JSON: 메타 + by_type + by_floor + members[]
  CSV : UTF-8-BOM, 한글 헤더 (엑셀 호환)
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Union

from core.pipeline.member_data import MemberCollection

# ─────────────────────────────────────────────────────────────
# CSV 헤더 (한글, 엑셀 호환)
# ─────────────────────────────────────────────────────────────

CSV_HEADER = [
    "부재ID", "유형", "층", "구역",
    "X(mm)", "Y(mm)", "Z_bot(mm)", "Z_top(mm)",
    "단면", "길이(mm)", "각도(°)", "높이(mm)",
    "체적(m³)", "면적(m²)", "레이어",
]


# ─────────────────────────────────────────────────────────────
# JSON 내보내기
# ─────────────────────────────────────────────────────────────

def _aggregate_by_type(coll: MemberCollection) -> Dict[str, Dict[str, float]]:
    """타입별 집계: count + 체적/면적."""
    result: Dict[str, Dict[str, float]] = {}
    for m in coll:
        bucket = result.setdefault(m.type, {"count": 0, "volume_m3": 0.0, "area_m2": 0.0})
        bucket["count"] += 1
        bucket["volume_m3"] += m.volume_m3()
        bucket["area_m2"] += m.area_value_m2()

    # 0인 필드 정리
    for t, b in result.items():
        b["volume_m3"] = round(b["volume_m3"], 3)
        b["area_m2"]   = round(b["area_m2"],   3)
    return result


def _aggregate_by_floor(coll: MemberCollection) -> Dict[str, Dict[str, float]]:
    """층별 집계."""
    result: Dict[str, Dict[str, float]] = {}
    for m in coll:
        bucket = result.setdefault(m.floor, {"count": 0, "volume_m3": 0.0, "area_m2": 0.0})
        bucket["count"] += 1
        bucket["volume_m3"] += m.volume_m3()
        bucket["area_m2"] += m.area_value_m2()

    for f, b in result.items():
        b["volume_m3"] = round(b["volume_m3"], 3)
        b["area_m2"]   = round(b["area_m2"],   3)
    return result


def export_boq_json(
    coll: MemberCollection,
    path: Union[str, Path],
    project: str = "untitled",
) -> Path:
    """BOQ → JSON.

    Returns:
        저장된 파일 경로.
    """
    path = Path(path)
    out: Dict[str, Any] = {
        "project": project,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "total_members": len(coll),
        "by_type": _aggregate_by_type(coll),
        "by_floor": _aggregate_by_floor(coll),
        "members": [m.to_dict() for m in coll],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return path


# ─────────────────────────────────────────────────────────────
# CSV 내보내기
# ─────────────────────────────────────────────────────────────

def _member_to_csv_row(m) -> Dict[str, Any]:
    return {
        "부재ID":      m.id,
        "유형":        m.type,
        "층":          m.floor,
        "구역":        m.source,
        "X(mm)":       round(float(m.x), 1),
        "Y(mm)":       round(float(m.y), 1),
        "Z_bot(mm)":   round(float(m.z_bot), 1),
        "Z_top(mm)":   round(float(m.z_top), 1),
        "단면":        m.section or "",
        "길이(mm)":    round(float(m.length_mm), 1) if m.length_mm is not None else "",
        "각도(°)":     round(float(m.angle_deg), 1) if m.angle_deg is not None else "",
        "높이(mm)":    round(float(m.height_mm), 1) if m.height_mm is not None else round(m.height_z_mm, 1),
        "체적(m³)":    round(m.volume_m3(), 3),
        "면적(m²)":    round(m.area_value_m2(), 3),
        "레이어":      m.layer,
    }


def export_boq_csv(
    coll: MemberCollection,
    path: Union[str, Path],
) -> Path:
    """BOQ → CSV (UTF-8-BOM, 한글 헤더).

    Returns:
        저장된 파일 경로.
    """
    path = Path(path)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for m in coll:
            writer.writerow(_member_to_csv_row(m))
    return path
