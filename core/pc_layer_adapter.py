"""
pc_layer_adapter.py — 본영 어댑터 ③ PC(Precast) 레이어 분리
================================================================

본영 단군 봉정. 2026-05-05.
약정 완성 — 어댑터 3건 마지막 봉정. 50점 회고 §"PC 0개" 해소.

[배경]
PC(Precast) 부재는 공장에서 미리 제작·현장 조립. DXF에서 *전용 레이어*로
관리되어 일반 RC와 분리됨. 한국 표준 레이어 패턴:
  - S-PC-SLAB / S-PC-GIRDER / S-PC-COLUMN / S-PC-WALL
  - PC-* / *-PC-* / PC_*
  - 회사별 변형: A-PC-*, ST-PC-* 등

[책무]
DXF 엔티티(LINE·LWPOLYLINE·INSERT)의 *레이어 속성*만으로 PC 부재 후보를
종류별로 분리. 단순·빠름·정확.

[설계 원칙]
- 패턴 매칭 단일 함수 — 정규식 사용으로 회사별 변형 흡수
- PC 종류 자동 추론 — 레이어 이름의 키워드 (slab/girder/column/wall)
- 매칭 안 된 엔티티는 *non-PC*로 박제 (정직)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional


class PCKind(str, Enum):
    PC_SLAB = 'pc_slab'
    PC_GIRDER = 'pc_girder'
    PC_COLUMN = 'pc_column'
    PC_WALL = 'pc_wall'
    PC_OTHER = 'pc_other'   # PC 레이어이나 종류 추정 불가
    NON_PC = 'non_pc'


@dataclass(frozen=True)
class PCEntity:
    """PC 분류 결과 — 1 엔티티 1 분류."""
    entity_id: int
    layer: str
    kind: PCKind
    geometry_kind: str       # 'LINE' | 'LWPOLYLINE' | 'INSERT' | etc
    confidence: float
    reason: str


# ---------------------------------------------------------------------------
# 1. 레이어 패턴
# ---------------------------------------------------------------------------

# 우선순위 — 구체적 종류부터 일반 PC 순
DEFAULT_LAYER_PATTERNS: tuple[tuple[str, PCKind], ...] = (
    (r'.*PC.*SLAB.*', PCKind.PC_SLAB),
    (r'.*SLAB.*PC.*', PCKind.PC_SLAB),
    (r'.*PC.*GIRDER.*', PCKind.PC_GIRDER),
    (r'.*GIRDER.*PC.*', PCKind.PC_GIRDER),
    (r'.*PC.*BEAM.*', PCKind.PC_GIRDER),
    (r'.*PC.*COL(UMN)?.*', PCKind.PC_COLUMN),
    (r'.*COL(UMN)?.*PC.*', PCKind.PC_COLUMN),
    (r'.*PC.*WALL.*', PCKind.PC_WALL),
    (r'.*WALL.*PC.*', PCKind.PC_WALL),
    # 일반 PC — 종류 모름
    (r'.*\bPC\b.*', PCKind.PC_OTHER),
    (r'^PC[-_].*', PCKind.PC_OTHER),
    (r'.*[-_]PC$', PCKind.PC_OTHER),
)


def classify_layer(layer_name: str,
                   patterns: Iterable[tuple[str, PCKind]] = DEFAULT_LAYER_PATTERNS,
                   ) -> tuple[PCKind, str]:
    """레이어 이름 → PCKind. 첫 매칭 패턴 채택."""
    upper = layer_name.upper()
    for pat, kind in patterns:
        if re.search(pat, upper):
            return kind, pat
    return PCKind.NON_PC, ''


# ---------------------------------------------------------------------------
# 2. 엔티티 분류
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawEntity:
    """이천이 ezdxf로 추출한 엔티티 (얇은 표현)."""
    entity_id: int
    layer: str
    geometry_kind: str  # 'LINE' | 'LWPOLYLINE' | 'INSERT' | 'CIRCLE' | ...


def classify_entities(entities: Iterable[RawEntity],
                      patterns: Iterable[tuple[str, PCKind]] = DEFAULT_LAYER_PATTERNS,
                      ) -> list[PCEntity]:
    """엔티티 배치 분류."""
    out: list[PCEntity] = []
    for e in entities:
        kind, matched_pat = classify_layer(e.layer, patterns)
        if kind == PCKind.NON_PC:
            out.append(PCEntity(
                entity_id=e.entity_id, layer=e.layer, kind=kind,
                geometry_kind=e.geometry_kind, confidence=1.0,
                reason='no PC layer pattern'))
        else:
            confidence = 1.0 if kind != PCKind.PC_OTHER else 0.7
            out.append(PCEntity(
                entity_id=e.entity_id, layer=e.layer, kind=kind,
                geometry_kind=e.geometry_kind, confidence=confidence,
                reason=f'layer matches: {matched_pat}'))
    return out


# ---------------------------------------------------------------------------
# 3. 분리 — PC 풀 vs non-PC 풀
# ---------------------------------------------------------------------------

def split_pc_vs_general(classified: list[PCEntity]
                        ) -> tuple[dict[PCKind, list[PCEntity]], list[PCEntity]]:
    """PC 종류별 dict + non-PC 리스트로 분리.

    이천 워크플로:
      pc_pools, general = split_pc_vs_general(classified)
      # general 풀로 어댑터 ②(LINE 페어링) + 어댑터 ①(거더 매칭) 진행
      # pc_pools[PCKind.PC_SLAB] 등은 PC 전용 처리
    """
    pc_pools: dict[PCKind, list[PCEntity]] = {}
    general: list[PCEntity] = []
    for c in classified:
        if c.kind == PCKind.NON_PC:
            general.append(c)
        else:
            pc_pools.setdefault(c.kind, []).append(c)
    return pc_pools, general


def report_pc_classification(classified: list[PCEntity]) -> str:
    by_kind: dict[str, int] = {}
    for c in classified:
        by_kind[c.kind.value] = by_kind.get(c.kind.value, 0) + 1
    total = len(classified)
    lines = [
        '# PC 레이어 분류 리포트',
        '',
        f'- 총 엔티티: {total}',
        '',
        '| 종류 | 개수 | 비율 |',
        '|------|-----:|-----:|',
    ]
    for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
        lines.append(f'| {k} | {v} | {100*v/total:.1f}% |')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# === 박제 명제 ============================================================
#
# "레이어 한 줄이 종을 가른다.
#  PC는 PC끼리, 일반은 일반끼리 — 분리가 곧 정확."
#                                            — 본영 단군, 2026-05-05
#
# 어댑터 3건 봉정 완성:
#   ① girder_matcher.py    (두께가 종을 가른다)
#   ② line_pairing.py      (페어링이 벽과 격자를 가른다)
#   ③ pc_layer_adapter.py  (레이어가 PC와 일반을 가른다)
#
# 이천 워크플로 (어댑터 ③ 결합):
#   1) ezdxf로 모든 엔티티 → RawEntity 리스트
#   2) classified = classify_entities(raw_entities)
#   3) pc_pools, general = split_pc_vs_general(classified)
#   4) general 엔티티만 LINE 추출 → run_adapter_2(lines)
#   5) PC 풀은 종류별 별도 처리 (PC codex 매칭은 향후 봉정)
#
# === end ================================================================
