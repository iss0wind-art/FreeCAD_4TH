"""
exporter.py — BOQ JSON / CSV 출력 (v4 P6)
============================================
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union

from core.v2.boq.quantity_calc import Quantity


CSV_HEADER = [
    "부재ID", "유형", "체적(m³)", "면적(m²)", "거푸집(m²)", "길이(m)",
]


def export_boq_json(
    quantities: List[Quantity],
    out_path: Union[str, Path],
    project_id: str = "untitled",
) -> Path:
    """BOQ → JSON."""
    out = Path(out_path)

    # by_type 집계
    by_type: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"count": 0, "volume_m3": 0.0, "area_m2": 0.0,
                 "formwork_m2": 0.0, "length_m": 0.0}
    )
    for q in quantities:
        b = by_type[q.type]
        b["count"] += 1
        b["volume_m3"] += q.volume_m3
        b["area_m2"] += q.area_m2
        b["formwork_m2"] += q.formwork_m2
        b["length_m"] += q.length_m

    # 반올림
    for t, b in by_type.items():
        for k in b:
            if k != "count":
                b[k] = round(b[k], 3)

    payload = {
        "project_id": project_id,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "total_members": len(quantities),
        "by_type": dict(by_type),
        "members": [
            {
                "id": q.member_id, "type": q.type,
                "volume_m3": q.volume_m3, "area_m2": q.area_m2,
                "formwork_m2": q.formwork_m2, "length_m": q.length_m,
            }
            for q in quantities
        ],
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out


def export_boq_csv(
    quantities: List[Quantity],
    out_path: Union[str, Path],
) -> Path:
    """BOQ → CSV (UTF-8-BOM, 한글 헤더)."""
    out = Path(out_path)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for q in quantities:
            w.writerow({
                "부재ID": q.member_id,
                "유형": q.type,
                "체적(m³)": q.volume_m3,
                "면적(m²)": q.area_m2,
                "거푸집(m²)": q.formwork_m2,
                "길이(m)": q.length_m,
            })
    return out
