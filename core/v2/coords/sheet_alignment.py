"""
sheet_alignment.py — 같은 도면 시트 간 정렬 (v4 P2.3)
=======================================================
한 도면 안 N개 시트를 절대 좌표계로 정렬.

[전략]
  기준 시트(가장 SW 위치)의 앵커를 (0, 0)으로 두고
  나머지 시트는 (앵커_x - 기준_x, 앵커_y - 기준_y) 평행이동.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from core.v2.coords.anchor_finder import Anchor


@dataclass
class SheetTransform:
    """시트 좌표 → 절대 좌표 변환."""
    sheet_id: str
    tx: float
    ty: float
    tz: float = 0.0
    rot_deg: float = 0.0
    scale: float = 1.0
    derivation: List[str] = field(default_factory=list)


def align_sheets_within_drawing(
    anchors: Dict[str, Anchor],
    sl_per_sheet: Optional[Dict[str, float]] = None,
) -> Dict[str, SheetTransform]:
    """기준 시트(SW)를 (0,0)으로 두고 나머지 시트 오프셋 계산 + Z축 높이 반영."""
    if not anchors:
        return {}

    # 기준 시트: 앵커 X 가장 작은 시트
    ref_anchor = min(anchors.values(), key=lambda a: (a.x, a.y))
    sls = sl_per_sheet or {}

    result: Dict[str, SheetTransform] = {}
    for sheet_id, anchor in anchors.items():
        # X, Y 정렬: 앵커 일치화
        tx = ref_anchor.x - anchor.x
        ty = ref_anchor.y - anchor.y
        
        # Z 정렬: SL 값 반영 (없으면 0.0)
        tz = sls.get(sheet_id, 0.0)
        
        result[sheet_id] = SheetTransform(
            sheet_id=sheet_id,
            tx=tx,
            ty=ty,
            tz=tz,
            rot_deg=0.0,
            scale=1.0,
            derivation=[anchor.method, f"ref={ref_anchor.sheet_id}", f"sl={tz}"],
        )
    return result
