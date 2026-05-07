"""
ks_lexicon.py — KS 표준 부재 키워드 사전 (v4 P3.1)
====================================================
도면-agnostic: 특정 도면 레이어명 X, KS 일반 키워드만.

[패턴 형식]
  - 키워드 부분 일치 (case-insensitive)
  - 한글·영문 혼용
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List


class MemberType(str, Enum):
    COLUMN     = "column"
    BEAM       = "beam"
    WALL       = "wall"
    SLAB       = "slab"
    FOUNDATION = "foundation"
    IGNORE     = "ignore"
    UNKNOWN    = "unknown"


# KS·국내 도면 일반 키워드
KS_KEYWORDS: Dict[MemberType, List[str]] = {
    MemberType.COLUMN: [
        "COLUMN", "COL", "기둥",
        "S-COL", "00_COLUMN", "A-COL",
    ],
    MemberType.BEAM: [
        "BEAM", "GIRDER", "GDR", "보",
        "S-BEAM", "S-GIRDER", "S-PC-GIRDER",
        "00_BEAM", "00_(APT)BEAM",
        "RG", "RB", "TB", "FB",
    ],
    MemberType.WALL: [
        "WALL", "벽체", "벽",
        "A-WALL-RC", "S-WALL", "S-하부벽체",
        "00_SHEAR.WALL", "00_SHEAR WALL",
        "SHEAR",
    ],
    MemberType.SLAB: [
        "SLAB", "바닥", "FLOOR",
        "S-SLAB", "S-PC-SLAB",
        "00_SLAB",
    ],
    MemberType.FOUNDATION: [
        "FOOTING", "FOUNDATION", "MAT", "PILE",
        "기초", "FND", "F-",
        "S-FOUNDATION", "S-BASE", "S-FND",
    ],
    MemberType.IGNORE: [
        # 건축·치수·텍스트 레이어 (구조 아님)
        "DIM", "DIMENSION", "HATCH",
        "A-FUR", "A-STAIR", "A-CEN",
        "A-TAG", "A-DIM", "A-ANNO", "A-FIN",
        "A-WALL-BRICK",                 # 벽돌은 비구조
        "Defpoints", "DEFPOINTS",
        "00_HATCH", "ANNO", "TEXT-ONLY",
        "AH-",                            # 건축 보조
        "0-Pile",                         # 파일은 별도 (기초 분기)
        "XR-CEN", "00_CENTER",
    ],
}


def classify_layer_by_keyword(layer_name: str) -> MemberType:
    """레이어명 → MemberType (키워드 매칭).

    우선순위:
        1. IGNORE (먼저 거름)
        2. COLUMN/WALL/BEAM/SLAB/FOUNDATION (구체적 키워드)
        3. UNKNOWN (매칭 없음)
    """
    if not layer_name:
        return MemberType.UNKNOWN

    name_upper = layer_name.upper()

    # 1. IGNORE 먼저
    for kw in KS_KEYWORDS[MemberType.IGNORE]:
        if kw.upper() in name_upper:
            return MemberType.IGNORE

    # 2. 구체적 부재 키워드 (가장 긴 키워드 우선 매칭)
    candidates = []
    for mt in [MemberType.COLUMN, MemberType.BEAM, MemberType.WALL,
               MemberType.SLAB, MemberType.FOUNDATION]:
        for kw in KS_KEYWORDS[mt]:
            if kw.upper() in name_upper:
                candidates.append((len(kw), mt))

    if candidates:
        # 가장 긴 키워드 매칭 우선
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]

    return MemberType.UNKNOWN
