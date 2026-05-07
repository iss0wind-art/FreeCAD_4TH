"""
extract_pipeline.py — 부재 추출 통합 (v4 P4)
==============================================
레이어 분류 결과 → 5개 부재 타입 일괄 추출 → MemberInstance[].
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import ezdxf

from core.manifest_parser import GridRef, MemberInstance
from core.v2.classify.ks_lexicon import MemberType
from core.v2.classify.layer_role_inferer import (
    LayerRole,
    infer_all_layers,
)
from core.v2.extract.beams import ExtractedBeam, extract_beams
from core.v2.extract.columns import ExtractedColumn, extract_columns
from core.v2.extract.foundations import (
    ExtractedFoundation,
    extract_foundations,
)
from core.v2.extract.section_text import (
    SectionSpec,
    collect_section_specs,
)
from core.v2.extract.slabs import ExtractedSlab, extract_slabs
from core.v2.extract.walls import ExtractedWall, extract_walls
from core.v2.inspect.meta_pipeline import DrawingMeta
from core.v2.inspect.text_classifier import TextCategory


@dataclass
class ExtractionResult:
    """모든 부재 추출 결과 (인스턴스 변환 전)."""
    columns: List[ExtractedColumn] = field(default_factory=list)
    walls: List[ExtractedWall] = field(default_factory=list)
    beams: List[ExtractedBeam] = field(default_factory=list)
    slabs: List[ExtractedSlab] = field(default_factory=list)
    foundations: List[ExtractedFoundation] = field(default_factory=list)
    section_specs: Dict[str, SectionSpec] = field(default_factory=dict)
    layer_roles: Dict[str, LayerRole] = field(default_factory=dict)
    # 일람표에서 추출한 심볼→단면 카탈로그
    section_catalog: Dict[str, Any] = field(default_factory=dict)


def extract_all_members(meta: DrawingMeta,
                        section_catalog: Optional[Dict] = None) -> ExtractionResult:
    """모든 부재 타입 일괄 추출."""
    doc = ezdxf.readfile(meta.path)

    # 1. 레이어 분류
    layer_roles = infer_all_layers(meta.layer_stats)

    # 타입별 레이어 목록
    cols_layers = [l for l, r in layer_roles.items()
                   if r.member_type == MemberType.COLUMN]
    walls_layers = [l for l, r in layer_roles.items()
                    if r.member_type == MemberType.WALL]
    beams_layers = [l for l, r in layer_roles.items()
                    if r.member_type == MemberType.BEAM]
    slabs_layers = [l for l, r in layer_roles.items()
                    if r.member_type == MemberType.SLAB]
    fnds_layers = [l for l, r in layer_roles.items()
                   if r.member_type == MemberType.FOUNDATION]

    # 2. 단면 라벨 수집 (BEAM에 매칭용)
    section_label_positions = [
        (lab.text, lab.x, lab.y)
        for lab in meta.text_stats.by_category(TextCategory.SECTION_CODE)
    ]
    section_specs = collect_section_specs(section_label_positions)

    # 3. 부재 추출
    columns = extract_columns(doc, cols_layers)
    walls = extract_walls(doc, walls_layers)
    beams = extract_beams(
        doc, beams_layers,
        section_specs=section_specs,
        section_label_positions=section_label_positions,
    )
    slabs = extract_slabs(doc, slabs_layers)
    fnds = extract_foundations(doc, fnds_layers)

    return ExtractionResult(
        columns=columns,
        walls=walls,
        beams=beams,
        slabs=slabs,
        foundations=fnds,
        section_specs=section_specs,
        layer_roles=layer_roles,
        section_catalog=section_catalog or {},
    )


def to_manifest_members(
    result: ExtractionResult,
    floor_id: str,
    project_id: str,
) -> List[MemberInstance]:
    """ExtractionResult → MemberInstance[] (manifest_parser 호환).

    Args:
        floor_id: 모든 부재가 속할 층 ID
        project_id: 프로젝트 ID (member ID prefix)
    """
    members: List[MemberInstance] = []

    cat = result.section_catalog or {}

    # COLUMN — 측정값 직접 사용 (LWPOLYLINE bbox = 진짜 단면)
    for i, c in enumerate(result.columns, 1):
        # 카탈로그에 측정값과 매칭되는 심볼 있으면 그것을 spec으로
        spec_symbol = f"COL-MEAS-{int(c.width_mm)}x{int(c.height_mm)}"
        members.append(MemberInstance(
            id=f"COL-{floor_id}-{i:04d}",
            spec=spec_symbol,
            type="column",
            floor=floor_id,
            at=GridRef(xy=[c.cx, c.cy]),
        ))

    # BEAM — 라벨 매칭 → 카탈로그 → 진짜 단면
    for i, b in enumerate(result.beams, 1):
        if b.section_symbol and b.section_symbol in cat:
            entry = cat[b.section_symbol]
            spec = b.section_symbol   # 일람표 심볼 그대로
        elif b.section_symbol:
            spec = f"UNKNOWN-{b.section_symbol}"   # 라벨은 있으나 카탈로그 미매칭
        else:
            spec = f"UNKNOWN-BEAM-NOLABEL"   # 라벨 자체 없음 (정직하게 표기)

        members.append(MemberInstance(
            id=f"BM-{floor_id}-{i:04d}",
            spec=spec,
            type="beam",
            floor=floor_id,
            from_=GridRef(xy=[b.p0[0], b.p0[1]]),
            to=GridRef(xy=[b.p1[0], b.p1[1]]),
        ))

    # WALL — 평행쌍 측정 두께 직접 사용 (자동 추출, 추측 X)
    for i, w in enumerate(result.walls, 1):
        sym = f"WALL-MEAS-T{int(w.thickness_mm)}"
        members.append(MemberInstance(
            id=f"WL-{floor_id}-{i:04d}",
            spec=sym,
            type="wall",
            floor=floor_id,
            polygon=[
                GridRef(xy=[w.p0[0], w.p0[1]]),
                GridRef(xy=[w.p1[0], w.p1[1]]),
            ],
        ))

    # SLAB — 두께 미상이면 명시적 UNKNOWN
    for i, s in enumerate(result.slabs, 1):
        spec = f"SLAB-T{int(s.thickness_mm)}-UNVERIFIED"   # 도면에 두께 표기 없으면 폴백
        members.append(MemberInstance(
            id=f"SL-{floor_id}-{i:04d}",
            spec=spec,
            type="slab",
            floor=floor_id,
            polygon=[GridRef(xy=[p[0], p[1]]) for p in s.polygon],
        ))

    # FND — 측정값 직접
    for i, f in enumerate(result.foundations, 1):
        members.append(MemberInstance(
            id=f"FND-{floor_id}-{i:04d}",
            spec=f"FND-MEAS-{int(f.width_mm)}x{int(f.height_mm)}",
            type="foundation",
            floor=floor_id,
            at=GridRef(xy=[f.cx, f.cy]),
        ))

    return members
