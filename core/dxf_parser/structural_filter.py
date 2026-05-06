"""
structural_filter.py — 골조 전용 레이어 필터
=============================================
콘크리트 골조(기둥·보·슬라브·전단벽·코어)만 통과.
나머지 (조적·마감·창호·설비·가구) 전부 차단.

[골조의 정의 — 방부장 2026-05-06 기준]
  포함: 기둥(COLUMN), 보(BEAM/GIRDER), 슬라브(SLAB),
        전단벽(SHEAR WALL), 코어월(CORE), 격자선(GRID)
  제외: 조적(BRICK), 마감(FIN/PAINT/TILE), 창호(DOOR/WIN),
        설비(MEP/ELEC/PLUMB), 가구(FUR), 천장(CEIL), 지반(PILE)
"""
from __future__ import annotations

import re
from typing import Optional

import ezdxf

from core.dxf_parser.entity_scanner import iter_all


# ─────────────────────────────────────────────────────────────
# 레이어 패턴
# ─────────────────────────────────────────────────────────────

# 골조 레이어 (포함)
_STRUCTURAL = re.compile(
    r'(S[-_]기둥|S[-_]COL|STRUCT[-_]COL'         # 기둥
    r'|S[-_]GIRDER|S[-_]BEAM|00[-_]BEAM|GIRDER|00[-_]APT\)?BEAM'
    r'|S[-_]SLAB|S[-_]PC[-_]SLAB|00[-_]SLAB'     # 슬라브
    r'|S[-_]PC[-_]GIRDER|PC[-_]GIRDER'            # PC 보
    r'|00[-_]SHEAR|SHEAR[-_]WALL|전단벽|CORE'     # 전단벽·코어
    r'|00[-_]COLUMN|00[-_]UNDER'                   # 지하 기둥
    r'|S[-_]WALL|S[-_]전단|S[-_]코어'             # 구조 벽
    r'|A[-_]WALL[-_]RC'                            # RC 벽 (콘크리트)
    r'|^S[-_](?!Def)'                             # "S-" 접두사 레이어 (S-Defpoints 제외)
    r'|^00[-_]'                                    # "00_" 접두사 레이어 (지하 구조)
    r')',
    re.IGNORECASE,
)

# 비골조 레이어 (제외 — 명시)
_NON_STRUCTURAL = re.compile(
    r'(BRICK|벽돌|조적'
    r'|A[-_]FUR|FURNITURE|FUR[-_]'                # 가구
    r'|A[-_]FIN|FINISH|PAINT|TILE|CARPET'          # 마감
    r'|A[-_]DOOR|DOOR|WIN|WINDOW|창호'             # 창호
    r'|A[-_]CEIL|CEIL|CEILING|천장'                # 천장
    r'|ELEC|MEP|PLUMB|HVAC|설비|배관|전기'         # 설비
    r'|A[-_]SITE|SITE|지반|GROUND|대지'            # 지반·대지
    r'|PILE|파일|STEEL|강재'                        # 파일·강재
    r'|HATCH(?!.*SLAB)'                            # HATCH (슬라브 HATCH 제외)
    r'|TEXT|DIM|ANNO|주석|치수'                    # 주석·치수
    r'|Defpoints|BORD|FRAME|BORDER'               # 도곽
    r')',
    re.IGNORECASE,
)


def is_structural(layer: str) -> bool:
    """레이어가 골조 부재인지 판단."""
    if _NON_STRUCTURAL.search(layer):
        return False
    return bool(_STRUCTURAL.search(layer))


def is_structural_block(block_name: str) -> bool:
    """INSERT 블록명이 골조 부재인지 판단.

    한국 구조 도면 블록 패턴:
      기둥: C400X800, B2-B1 C2, TC600X900, EC1, PC2
      보: G1, RB20, GB-1
    """
    COL_PAT = re.compile(
        r'C\d{3,}|B\d[-_]B\d\s+[EP]?C\d|TC\d|EC\d|PC\d',
        re.IGNORECASE,
    )
    BEAM_PAT = re.compile(r'\bG\d+\b|\bGB[-_]\d|\bRB\d', re.IGNORECASE)
    EV_PAT = re.compile(r'ELEV|승강기', re.IGNORECASE)
    EXCLUDE = re.compile(r'FUR|FIN|DOOR|WIN|ELEC|MEP|CEIL', re.IGNORECASE)

    if EXCLUDE.search(block_name):
        return False
    return bool(COL_PAT.search(block_name) or
                BEAM_PAT.search(block_name) or
                EV_PAT.search(block_name))


# ─────────────────────────────────────────────────────────────
# 골조 전용 엔티티 순회
# ─────────────────────────────────────────────────────────────

def iter_structural(msp,
                    depth: int = 8,
                    entity_types: Optional[list] = None):
    """골조 레이어의 엔티티만 순회.

    entity_types: ['LINE', 'LWPOLYLINE', 'INSERT', 'HATCH'] 등
                  None이면 전부.
    """
    for e in iter_all(msp, max_depth=depth):
        t = e.dxftype()
        if entity_types and t not in entity_types:
            continue
        try:
            layer = e.dxf.layer
        except Exception:
            continue
        if not is_structural(layer):
            if t == 'INSERT':
                try:
                    bname = e.dxf.name
                    if is_structural_block(bname):
                        yield e
                        continue
                except Exception:
                    pass
            continue
        yield e


# ─────────────────────────────────────────────────────────────
# 레이어 분류 보고
# ─────────────────────────────────────────────────────────────

def classify_layers(doc) -> dict:
    """도면의 모든 레이어를 골조/비골조로 분류.

    Returns:
        {'structural': {layer: count}, 'non_structural': {layer: count},
         'unknown': {layer: count}}
    """
    msp = doc.modelspace()
    cats: dict = {'structural': {}, 'non_structural': {}, 'unknown': {}}

    for e in iter_all(msp):
        try:
            layer = e.dxf.layer
        except Exception:
            continue
        if _NON_STRUCTURAL.search(layer):
            cat = 'non_structural'
        elif _STRUCTURAL.search(layer):
            cat = 'structural'
        else:
            cat = 'unknown'
        cats[cat][layer] = cats[cat].get(layer, 0) + 1

    return cats


def report_layer_classification(doc) -> str:
    """레이어 분류 보고서."""
    cats = classify_layers(doc)
    lines = ['[골조 레이어 분류]']
    for cat, layers in cats.items():
        total = sum(layers.values())
        lines.append(f'\n  {cat} ({len(layers)}개 레이어, {total:,}개 엔티티):')
        for layer, cnt in sorted(layers.items(), key=lambda x: -x[1])[:10]:
            lines.append(f'    {layer[:50]}: {cnt:,}')
    return '\n'.join(lines)
