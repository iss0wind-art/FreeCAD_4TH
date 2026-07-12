"""
wall_extractor.py — DXF LINE → 벽체 페어링 어댑터
===================================================
DXF 도면의 LINE 엔티티를 수집하여 line_pairing.pair_walls에 공급.
벽체 레이어 자동 감지 + 클립 영역 적용.

사용:
    pairs = extract_walls(doc, clip=DONG_CLIP)
    for pair in pairs:
        print(pair.thickness, pair.overlap_length)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import ezdxf

from core.dxf_parser.entity_scanner import iter_all
from core.line_pairing import LineSeg, WallPair, pair_walls


# ─────────────────────────────────────────────────────────────
# 벽체 레이어 패턴
# ─────────────────────────────────────────────────────────────

_WALL_LAYER = re.compile(
    r'(WALL|벽|S[-_]?W\d|전단벽|SHEAR|A[-_]?WALL|RC[-_]?WALL|00[-_]?SHEAR)',
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────
# 자료구조
# ─────────────────────────────────────────────────────────────

@dataclass
class WallExtractResult:
    """벽체 추출 결과."""
    pairs: List[WallPair] = field(default_factory=list)
    line_count: int = 0
    layer_counts: dict = field(default_factory=dict)

    def summary(self) -> str:
        thicknesses = sorted(set(round(p.thickness) for p in self.pairs))
        return (
            f'LINE {self.line_count}개 → 벽 페어 {len(self.pairs)}개 '
            f'두께: {thicknesses[:10]}'
        )


# ─────────────────────────────────────────────────────────────
# 추출 함수
# ─────────────────────────────────────────────────────────────

def extract_walls(doc,
                  clip: Optional[Tuple[float,float,float,float]] = None,
                  wall_layer_pat: Optional[re.Pattern] = None,
                  min_length: float = 500.0,
                  max_thickness: float = 500.0,
                  angle_tol_rad: float = 0.05,
                  max_dist: float = 500.0,
                  min_overlap: float = 300.0) -> WallExtractResult:
    """DXF 도면에서 벽체 추출.

    Args:
        doc: ezdxf 도면
        clip: (xmin,ymin,xmax,ymax) 영역 제한
        wall_layer_pat: 벽 레이어 필터 패턴 (None=기본 패턴)
        min_length: 벽선 최소 길이 (mm, 기본 500mm)
        max_thickness: 최대 벽 두께 (mm, 기본 500mm)
        angle_tol_rad: 페어링 각도 허용 오차 (rad)
        max_dist: 페어링 수직 거리 한계 (mm)
        min_overlap: 페어링 최소 오버랩 (mm)
    """
    pat = wall_layer_pat or _WALL_LAYER
    msp = doc.modelspace()
    lines: List[LineSeg] = []
    layer_counts: dict = {}

    for i, e in enumerate(iter_all(msp)):
        if e.dxftype() != 'LINE':
            continue
        try:
            layer = e.dxf.layer
            if not pat.search(layer):
                continue
            s = e.dxf.start
            en = e.dxf.end
            cx, cy = (s.x+en.x)/2, (s.y+en.y)/2
            if clip and not (clip[0] <= cx <= clip[2] and clip[1] <= cy <= clip[3]):
                continue
            length = math.hypot(en.x-s.x, en.y-s.y)
            if length < min_length:
                continue
            lines.append(LineSeg(
                p1=(s.x, s.y), p2=(en.x, en.y),
                layer=layer, line_id=i,
            ))
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
        except Exception:
            pass

    pairs = pair_walls(
        lines,
        angle_tol=angle_tol_rad,
        max_dist=max_thickness,  # 최대 벽 두께 = max_dist
        min_length=min_length,
        overlap_min_ratio=0.3,
    )

    return WallExtractResult(
        pairs=pairs,
        line_count=len(lines),
        layer_counts=layer_counts,
    )


def extract_walls_from_path(dxf_path: str,
                            encoding: str = 'cp949',
                            clip=None, **kwargs) -> WallExtractResult:
    from core.dxf_parser.encoding_helper import safe_read_dxf
    doc = safe_read_dxf(dxf_path, default_encoding=encoding)
    return extract_walls(doc, clip=clip, **kwargs)
