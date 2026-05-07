"""
stage1_structural_filter.py — Stage 1: 골조선 분리
====================================================
DXF 전체 엔티티 중 구조 골조선만 추출.
잡선(가구·치수·건축마감·XRef 비구조) 전부 제거.

[골조 레이어 기준]
  KEEP:  S-* 접두사 레이어 (S-GIRDER, S-BEAM, S-COL 등)
         A-WALL-RC 패턴 (RC 구조벽)  ← XRef 포함
  DROP:  A-FUR, A-STAIR, A-CEN, Defpoints, 00_HATCH
         치수선(DIMENSION), 주석(MTEXT 단독), 가구

[출력]
  FilterResult — 레이어별 엔티티 목록
  stage1_entities.json — 골조 엔티티 요약
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import ezdxf

from core.dxf_parser.entity_scanner import iter_all

# ── 레이어 분류 패턴 ─────────────────────────────────────────

# KEEP: 구조 레이어
_KEEP_PAT = re.compile(
    r'^S-'                          # S- 접두사 (S-GIRDER, S-BEAM, S-COL ...)
    r'|A-WALL-RC'                   # RC 구조벽
    r'|S-WALL'                      # 구조벽 직접 레이어
    r'|S-SLAB|S-FND|S-BASE'        # 슬라브·기초
    r'|00_COLUMN'                   # PKG 기둥
    r'|00_SHEAR.WALL'              # PKG 전단벽
    r'|00_BEAM|00_\(APT\)BEAM'    # PKG 보 ← 확인됨
    r'|S-PC-GIRDER|S-PC-SLAB'     # PC 거더·슬라브 ← 확인됨
    r'|00_SLAB.END',               # 슬라브 단부
    re.IGNORECASE,
)
# XRef 레이어에서 구조 관련 추출 (XR...A-WALL-RC 등)
_XREF_STRUCT_PAT = re.compile(r'A-WALL-RC', re.IGNORECASE)

# DROP: 명확히 버릴 레이어
_DROP_PAT = re.compile(
    r'A-FUR|A-STAIR|A-CEN|A-TAG|A-DIM'
    r'|Defpoints|00_HATCH|HATCH'
    r'|A-ANNO|ANNO|TEXT-ONLY'
    r'|A-DOOR|A-WINDOW|A-EQUIP',
    re.IGNORECASE,
)
# DROP 엔티티 타입
_DROP_TYPES = {'DIMENSION', 'ATTDEF', 'ATTRIB', 'VIEWPORT', 'XLINE', 'RAY'}


# ── 자료구조 ─────────────────────────────────────────────────

@dataclass
class StructuralEntity:
    etype:   str    # LINE, LWPOLYLINE, CIRCLE, HATCH ...
    layer:   str
    coords:  List[Tuple[float, float]]  # 대표 좌표 (중심 or 시작/끝)
    length:  Optional[float] = None     # LINE 길이


@dataclass
class FilterResult:
    entities:   List[StructuralEntity] = field(default_factory=list)
    by_layer:   Dict[str, int]         = field(default_factory=dict)
    by_type:    Dict[str, int]         = field(default_factory=dict)
    dropped:    int                    = 0
    total_in:   int                    = 0


# ── 메인 필터 ────────────────────────────────────────────────

def filter_structural(
    dxf_path: str,
    clip: Optional[Tuple[float, float, float, float]] = None,
    encoding: str = 'cp949',
) -> FilterResult:
    """
    DXF에서 골조 엔티티만 추출한다.

    Args:
        dxf_path: DXF 파일 경로
        clip:     (xmin, ymin, xmax, ymax) — None이면 전체
        encoding: DXF 인코딩 (한국 도면 cp949)

    Returns:
        FilterResult — 골조 엔티티 목록 + 통계
    """
    doc = ezdxf.readfile(dxf_path, encoding=encoding)
    msp = doc.modelspace()
    result = FilterResult()

    xmin = ymin = xmax = ymax = None
    if clip:
        xmin, ymin, xmax, ymax = clip

    for e in iter_all(msp):
        result.total_in += 1
        etype = e.dxftype()

        # 타입 필터
        if etype in _DROP_TYPES:
            result.dropped += 1
            continue

        layer = getattr(e.dxf, 'layer', '0') or '0'

        # 레이어 필터
        is_direct_struct = bool(_KEEP_PAT.search(layer))
        is_xref_struct   = bool(_XREF_STRUCT_PAT.search(layer))
        if not (is_direct_struct or is_xref_struct):
            result.dropped += 1
            continue
        if _DROP_PAT.search(layer):
            result.dropped += 1
            continue

        # 좌표 추출 + 클립 필터
        coords, length = _get_coords(e, etype)
        if not coords:
            result.dropped += 1
            continue

        if clip:
            cx = sum(p[0] for p in coords) / len(coords)
            cy = sum(p[1] for p in coords) / len(coords)
            if not (xmin <= cx <= xmax and ymin <= cy <= ymax):
                result.dropped += 1
                continue

        se = StructuralEntity(etype=etype, layer=layer,
                              coords=coords, length=length)
        result.entities.append(se)
        result.by_layer[layer] = result.by_layer.get(layer, 0) + 1
        result.by_type[etype]  = result.by_type.get(etype, 0) + 1

    return result


def _get_coords(e, etype: str):
    """엔티티에서 대표 좌표 목록과 길이 반환."""
    import math
    try:
        if etype == 'LINE':
            s, en = e.dxf.start, e.dxf.end
            L = math.hypot(en.x-s.x, en.y-s.y)
            return [(s.x, s.y), (en.x, en.y)], L
        elif etype in ('CIRCLE', 'ARC'):
            c = e.dxf.center
            return [(c.x, c.y)], e.dxf.radius
        elif etype == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in e.get_points()]
            return pts, None
        elif etype == 'HATCH':
            for path in e.paths:
                try:
                    pts = list(path.vertices)
                    if pts:
                        return [(p[0], p[1]) for p in pts[:4]], None
                except: pass
        elif etype in ('TEXT', 'MTEXT'):
            p = e.dxf.insert
            return [(p.x, p.y)], None
        elif etype == 'INSERT':
            p = e.dxf.insert
            return [(p.x, p.y)], None
    except:
        pass
    return [], None


# ── 저장 유틸 ────────────────────────────────────────────────

def save_result(result: FilterResult, out_path: str):
    """FilterResult → JSON 요약 저장."""
    summary = {
        'total_in':  result.total_in,
        'kept':      len(result.entities),
        'dropped':   result.dropped,
        'by_layer':  dict(sorted(result.by_layer.items(),
                                 key=lambda x: -x[1])[:30]),
        'by_type':   result.by_type,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=True, indent=2)


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    DXF  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
    CLIP = (69013, 2241258, 229013, 2401258)  # S30-001 B2F

    print('Stage 1: 골조선 분리 실행...')
    r = filter_structural(DXF, clip=CLIP)

    print(f'\n입력: {r.total_in:,}개')
    print(f'보존: {len(r.entities):,}개 ({100*len(r.entities)//max(1,r.total_in)}%)')
    print(f'제거: {r.dropped:,}개')
    print('\n레이어별:')
    for layer, cnt in sorted(r.by_layer.items(), key=lambda x: -x[1])[:15]:
        print(f'  {layer:40s} {cnt:4d}개')
    print('\n타입별:')
    for t, cnt in sorted(r.by_type.items(), key=lambda x: -x[1]):
        print(f'  {t:15s} {cnt:4d}개')

    save_result(r, 'output/stage1_filter.json')
    print('\n→ output/stage1_filter.json 저장')
