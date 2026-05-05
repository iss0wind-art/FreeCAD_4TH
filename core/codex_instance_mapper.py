"""
codex_instance_mapper.py — 코드↔인스턴스 매핑 PoC
================================================

본영 단군 직접 봉정. 2026-05-05.

이천 1차 시험 회고 §1 실패 1 — *데이터-모델 단절*의 첫 단추.
박스 추출은 됐다. Codex 채굴은 됐다. 그러나 매핑이 0건이었다.
본 모듈이 그 0건을 깨는 첫 PoC다.

[입력]
- codex_path: output/codex_*.json (기둥/보/벽 통합 법전)
- instances: List[BoxInstance] — 평면도에서 추출한 박스 + 라벨

[출력]
- List[Mapping] — 박스 ↔ codex symbol 매핑
- 매칭 실패 분리 박제 (정직성)

[매칭 우선순위]
1) 라벨 일치 (TEXT가 박스 안/근처에 있음)            → confidence=1.0, method='label'
2) 단면 일치 (W·H tolerance 5mm, 회전 허용)        → confidence=0.7, method='dimension'
3) 단면 일치 + source/floor 힌트로 좁힘             → confidence=0.85, method='dimension+context'
4) 매칭 실패                                      → unmatched (정직 박제)

[사용 예]
    from core.codex_instance_mapper import load_codex, map_instances
    codex = load_codex('output/codex_columns_unified.json')
    mappings, unmatched = map_instances(boxes, codex)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


DEFAULT_TOL_MM = 5.0


@dataclass
class CodexEntry:
    source: str
    symbol: str
    width: float
    height: float
    floor_from: Optional[int] = None
    floor_to: Optional[int] = None
    main_bar: Optional[str] = None
    hoop: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class BoxInstance:
    box_id: str                      # 평면도 박스 식별자 (예: "101동_B1F_box_42")
    width: float                     # 박스 가로 (mm)
    height: float                    # 박스 세로 (mm)
    label: Optional[str] = None      # 박스 안/근처 TEXT (있으면)
    source_hint: Optional[str] = None  # 동/영역 힌트 (예: "101~112동")
    floor_hint: Optional[int] = None   # 층 힌트


@dataclass
class Mapping:
    box_id: str
    matched_symbol: str
    matched_source: str
    confidence: float
    method: str
    codex_entry: CodexEntry


def load_codex(path: str | Path) -> list[CodexEntry]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    raw = data.get('부재_법전', [])
    out: list[CodexEntry] = []
    for r in raw:
        out.append(CodexEntry(
            source=r.get('source', ''),
            symbol=r.get('symbol', ''),
            width=float(r.get('width', 0)),
            height=float(r.get('height', 0)),
            floor_from=r.get('floor_from'),
            floor_to=r.get('floor_to'),
            main_bar=r.get('main_bar'),
            hoop=r.get('hoop'),
            extra={k: v for k, v in r.items() if k not in
                   {'source', 'symbol', 'width', 'height', 'floor_from',
                    'floor_to', 'main_bar', 'hoop'}},
        ))
    return out


def _dim_match(box_w: float, box_h: float, ce: CodexEntry, tol: float) -> bool:
    """단면 일치 (회전 허용 — TC15·16 W>H 패턴 대응)."""
    direct = abs(box_w - ce.width) <= tol and abs(box_h - ce.height) <= tol
    rotated = abs(box_w - ce.height) <= tol and abs(box_h - ce.width) <= tol
    return direct or rotated


def _floor_overlap(floor_hint: Optional[int], ce: CodexEntry) -> bool:
    if floor_hint is None or ce.floor_from is None or ce.floor_to is None:
        return True  # 힌트 없으면 차별 없음
    return ce.floor_from <= floor_hint <= ce.floor_to


def _source_match(source_hint: Optional[str], ce: CodexEntry) -> bool:
    if source_hint is None:
        return True
    return source_hint.strip() == ce.source.strip()


def map_instances(
    instances: list[BoxInstance],
    codex: list[CodexEntry],
    tol_mm: float = DEFAULT_TOL_MM,
) -> tuple[list[Mapping], list[BoxInstance]]:
    """박스 인스턴스를 codex symbol에 매핑.

    반환: (매핑 성공 리스트, 매칭 실패 박스 리스트)
    """
    mappings: list[Mapping] = []
    unmatched: list[BoxInstance] = []

    for inst in instances:
        # 1순위 — 라벨 일치 (확정)
        if inst.label:
            label = inst.label.strip()
            label_hits = [c for c in codex if c.symbol == label
                          and _source_match(inst.source_hint, c)]
            if label_hits:
                ce = label_hits[0]  # source 힌트로 이미 좁힘
                mappings.append(Mapping(
                    box_id=inst.box_id, matched_symbol=ce.symbol,
                    matched_source=ce.source, confidence=1.0,
                    method='label', codex_entry=ce))
                continue
            # 라벨 매칭 실패는 dim 시도로 fallback (라벨이 typo 등 가능)

        # 2·3순위 — 단면 일치 + 컨텍스트
        candidates = [c for c in codex if _dim_match(inst.width, inst.height, c, tol_mm)]
        if not candidates:
            unmatched.append(inst)
            continue

        # 컨텍스트로 좁힘 (source > floor)
        with_source = [c for c in candidates if _source_match(inst.source_hint, c)]
        if len(with_source) == 1:
            ce = with_source[0]
            mappings.append(Mapping(
                box_id=inst.box_id, matched_symbol=ce.symbol,
                matched_source=ce.source, confidence=0.85,
                method='dimension+source', codex_entry=ce))
            continue

        if with_source:
            with_floor = [c for c in with_source if _floor_overlap(inst.floor_hint, c)]
            if len(with_floor) == 1:
                ce = with_floor[0]
                mappings.append(Mapping(
                    box_id=inst.box_id, matched_symbol=ce.symbol,
                    matched_source=ce.source, confidence=0.85,
                    method='dimension+source+floor', codex_entry=ce))
                continue
            pool = with_floor or with_source
        else:
            pool = candidates

        # 단면만 일치, 다수 후보 — 첫 번째 채택, confidence 낮춤
        ce = pool[0]
        mappings.append(Mapping(
            box_id=inst.box_id, matched_symbol=ce.symbol,
            matched_source=ce.source,
            confidence=0.7 if len(pool) == 1 else 0.5,
            method='dimension' + ('-ambiguous' if len(pool) > 1 else ''),
            codex_entry=ce))

    return mappings, unmatched


def report_markdown(mappings: list[Mapping], unmatched: list[BoxInstance]) -> str:
    total = len(mappings) + len(unmatched)
    if total == 0:
        return '# 매핑 결과 — 입력 0건'

    by_method: dict[str, int] = {}
    for m in mappings:
        by_method[m.method] = by_method.get(m.method, 0) + 1

    lines = [
        '# 코드↔인스턴스 매핑 결과',
        '',
        f'- 총 인스턴스: **{total}**',
        f'- 매칭 성공: **{len(mappings)}** ({100*len(mappings)/total:.1f}%)',
        f'- 매칭 실패: **{len(unmatched)}** ({100*len(unmatched)/total:.1f}%)',
        '',
        '## 매칭 방법별 분포',
        '',
        '| 방법 | 개수 | 신뢰도 |',
        '|------|-----:|:------:|',
    ]
    method_conf = {'label': '1.00', 'dimension+source': '0.85',
                   'dimension+source+floor': '0.85',
                   'dimension': '0.70', 'dimension-ambiguous': '0.50'}
    for k, v in sorted(by_method.items(), key=lambda x: -x[1]):
        lines.append(f'| {k} | {v} | {method_conf.get(k, "?")} |')

    if unmatched:
        lines += ['', '## 매칭 실패 박스 (정직 박제)', '',
                  '| box_id | W (mm) | H (mm) | 라벨 | source_hint |',
                  '|--------|-------:|-------:|------|-------------|']
        for u in unmatched[:30]:  # 30건만 미리보기
            lines.append(f'| {u.box_id} | {u.width:.0f} | {u.height:.0f} '
                         f'| {u.label or "-"} | {u.source_hint or "-"} |')
        if len(unmatched) > 30:
            lines.append(f'| ... | | | | ({len(unmatched)-30} more) |')

    return '\n'.join(lines)


def save_mappings(mappings: list[Mapping], unmatched: list[BoxInstance],
                  out_path_json: str | Path) -> None:
    payload = {
        'mappings': [
            {**asdict(m), 'codex_entry': asdict(m.codex_entry)} for m in mappings
        ],
        'unmatched': [asdict(u) for u in unmatched],
        'stats': {
            'total': len(mappings) + len(unmatched),
            'matched': len(mappings),
            'unmatched': len(unmatched),
        },
    }
    Path(out_path_json).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


# === 사용 예시 (이천이 v3 트림 코드와 결합) =============================
#
# from core.codex_instance_mapper import (
#     load_codex, map_instances, BoxInstance, report_markdown, save_mappings
# )
#
# codex = load_codex('output/codex_columns_unified.json')
#
# # tests/test_b1f_102_v3_trim_boq.py 의 박스 추출 로직 결과를 BoxInstance로 변환
# instances = []
# for i, box in enumerate(extracted_column_boxes):  # ← 너의 추출 결과
#     instances.append(BoxInstance(
#         box_id=f'102_B1F_col_{i}',
#         width=box['w'], height=box['h'],
#         label=box.get('text_label'),         # 박스 안 TEXT 있으면 1순위 매칭
#         source_hint='101~112동',             # 102동이면 101~112동 일람표 사용
#         floor_hint=-1,                        # B1F = -1
#     ))
#
# mappings, unmatched = map_instances(instances, codex)
# print(report_markdown(mappings, unmatched))
# save_mappings(mappings, unmatched, 'output/mapping_102_B1F_columns.json')
#
# # 결과: 각 박스가 (TC2, source=101~112동, W=600, H=1200, main_bar=16-D25, ...)
# #       즉 *익명 wall:143이 아니라 식별된 부재*가 된다.
# === end ============================================================
