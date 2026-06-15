"""
layer_profiler.py — 레이어 통계 자동 분석 (v4 P1.2)
=====================================================
레이어별: 엔티티 수, dominant entity type, bbox, mean size.

[규약]
  - 매직넘버 0건
  - 도면-내재 신호만 (레이어명 패턴 X)
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class LayerStat:
    """단일 레이어 통계."""
    name: str
    entity_count: int
    dominant_type: str               # "LINE" / "LWPOLYLINE" / ...
    bbox: Tuple[float, float, float, float]   # (xmin, ymin, xmax, ymax)
    mean_entity_size: float          # 엔티티별 bbox 대각의 평균


def profile_layers(doc) -> Dict[str, LayerStat]:
    """모든 레이어의 엔티티 통계.

    Returns:
        {layer_name: LayerStat}
    """
    msp = doc.modelspace()

    # 레이어별 카운터
    type_counter: Dict[str, Counter] = defaultdict(Counter)
    bbox_per_layer: Dict[str, list] = defaultdict(list)
    sizes_per_layer: Dict[str, list] = defaultdict(list)

    def _process_entity(e, trans_layer=None):
        nonlocal type_counter, bbox_per_layer, sizes_per_layer
        
        # 실제 레이어 결정 (INSERT 내부에 있어도 원래 레이어 유지 또는 상속)
        layer = trans_layer or e.dxf.layer
        etype = e.dxftype()
        
        if etype == "INSERT":
            # 블록 내부 탐색
            try:
                block = doc.blocks.get(e.dxf.name)
                for be in block:
                    # 블록 내부의 엔티티는 블록의 레이어를 따를 수도 있고 자기 레이어를 가질 수도 있음
                    # 보통은 자기 레이어(0번 레이어 제외)를 가짐
                    inner_layer = be.dxf.layer
                    if inner_layer == "0":
                        inner_layer = layer # INSERT 레이어 상속
                    _process_entity(be, trans_layer=inner_layer)
            except Exception:
                pass
            # INSERT 자체도 카운트 (추가 신호)
            type_counter[layer][etype] += 1
            return

        type_counter[layer][etype] += 1

        # bbox + size 수집
        try:
            xs, ys = _entity_xy(e)
            if not xs or not ys:
                return
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            bbox_per_layer[layer].append((xmin, ymin, xmax, ymax))
            diag = math.hypot(xmax - xmin, ymax - ymin)
            sizes_per_layer[layer].append(diag)
        except Exception:
            pass

    for e in msp:
        _process_entity(e)

    # 결과 조립
    result: Dict[str, LayerStat] = {}
    for layer, types in type_counter.items():
        bboxes = bbox_per_layer.get(layer, [])
        sizes = sizes_per_layer.get(layer, [])

        if bboxes:
            xmin = min(b[0] for b in bboxes)
            ymin = min(b[1] for b in bboxes)
            xmax = max(b[2] for b in bboxes)
            ymax = max(b[3] for b in bboxes)
            agg_bbox = (xmin, ymin, xmax, ymax)
        else:
            agg_bbox = (0.0, 0.0, 0.0, 0.0)

        mean_size = sum(sizes) / len(sizes) if sizes else 0.0

        result[layer] = LayerStat(
            name=layer,
            entity_count=sum(types.values()),
            dominant_type=types.most_common(1)[0][0],
            bbox=agg_bbox,
            mean_entity_size=mean_size,
        )

    return result


def _entity_xy(e) -> Tuple[list, list]:
    """엔티티에서 X·Y 좌표 추출."""
    etype = e.dxftype()

    if etype == "LINE":
        return ([e.dxf.start.x, e.dxf.end.x],
                [e.dxf.start.y, e.dxf.end.y])

    if etype == "POINT":
        return ([e.dxf.location.x], [e.dxf.location.y])

    if etype in ("LWPOLYLINE", "POLYLINE"):
        try:
            pts = list(e.get_points()) if etype == "LWPOLYLINE" else [
                (v.dxf.location.x, v.dxf.location.y) for v in e.vertices
            ]
            return ([p[0] for p in pts], [p[1] for p in pts])
        except Exception:
            return ([], [])

    if etype in ("CIRCLE", "ARC"):
        cx, cy, r = e.dxf.center.x, e.dxf.center.y, e.dxf.radius
        return ([cx - r, cx + r], [cy - r, cy + r])

    if etype in ("TEXT", "MTEXT"):
        try:
            ip = e.dxf.insert if hasattr(e.dxf, "insert") else e.dxf.location
            return ([ip.x], [ip.y])
        except Exception:
            return ([], [])

    # 기타: bbox 시도
    try:
        bb = e.bbox()
        return ([bb.extmin.x, bb.extmax.x],
                [bb.extmin.y, bb.extmax.y])
    except Exception:
        return ([], [])
