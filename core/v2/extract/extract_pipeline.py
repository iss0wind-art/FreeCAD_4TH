"""
extract_pipeline.py — 부재 추출 통합 (v4 P4)
==============================================
레이어 분류 결과 → 5개 부재 타입 일괄 추출 → MemberInstance[].
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    columns: List[Tuple[ExtractedColumn, str]] = field(default_factory=list) # (member, sheet_id)
    walls: List[Tuple[ExtractedWall, str]] = field(default_factory=list)
    beams: List[Tuple[ExtractedBeam, str]] = field(default_factory=list)
    slabs: List[Tuple[ExtractedSlab, str]] = field(default_factory=list)
    foundations: List[Tuple[ExtractedFoundation, str]] = field(default_factory=list)
    section_specs: Dict[str, SectionSpec] = field(default_factory=dict)
    layer_roles: Dict[str, LayerRole] = field(default_factory=dict)
    # 일람표에서 추출한 심볼→단면 카탈로그
    section_catalog: Dict[str, Any] = field(default_factory=dict)


def extract_all_members(meta: DrawingMeta,
                        section_catalog: Optional[Dict] = None) -> ExtractionResult:
    """모든 부재 타입 일괄 추출 (시트 배정 포함)."""
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

    # 2. 단면 라벨 수집
    section_label_positions = [
        (lab.text, lab.x, lab.y)
        for lab in meta.text_stats.by_category(TextCategory.SECTION_CODE)
    ]
    section_specs = collect_section_specs(section_label_positions)

    all_text_positions = [
        (lab.text, lab.x, lab.y)
        for lab in meta.text_stats.all()
    ]

    # 카탈로그에서 슬라브 두께 lookup
    catalog = section_catalog or {}
    slab_thickness_lookup: Dict[str, float] = {}
    for sym, entry in catalog.items():
        member_type = entry.get("member_type") if isinstance(entry, dict) else None
        if member_type == "slab":
            t = entry.get("width_mm") if isinstance(entry, dict) else None
            if t and t > 0:
                slab_thickness_lookup[sym] = float(t)

    # 3. 부재 추출
    raw_columns = extract_columns(doc, cols_layers)
    raw_walls = extract_walls(doc, walls_layers)
    raw_beams = extract_beams(
        doc, beams_layers,
        section_specs=section_specs,
        section_label_positions=section_label_positions,
    )
    raw_slabs = extract_slabs(
        doc, slabs_layers,
        label_positions=all_text_positions,
        slab_catalog=slab_thickness_lookup,
    )
    raw_fnds = extract_foundations(doc, fnds_layers)

    # 4. 시트 배정 (Spatial Tagging)
    def _assign_sheet(cx, cy):
        for s in meta.sheets:
            xmin, ymin, xmax, ymax = s.bbox
            if xmin <= cx <= xmax and ymin <= cy <= ymax:
                return s.sheet_id
        return "unknown"

    columns = [(c, sid) for c in raw_columns if (sid := _assign_sheet(c.cx, c.cy)) != "unknown"]
    walls = [(w, sid) for w in raw_walls if (sid := _assign_sheet((w.p0[0]+w.p1[0])/2, (w.p0[1]+w.p1[1])/2)) != "unknown"]
    beams = [(b, sid) for b in raw_beams if (sid := _assign_sheet((b.p0[0]+b.p1[0])/2, (b.p0[1]+b.p1[1])/2)) != "unknown"]
    slabs = [(s, sid) for s in raw_slabs if (sid := _assign_sheet(s.polygon[0][0], s.polygon[0][1])) != "unknown"]
    foundations = [(f, sid) for f in raw_fnds if (sid := _assign_sheet(f.cx, f.cy)) != "unknown"]

    return ExtractionResult(
        columns=columns,
        walls=walls,
        beams=beams,
        slabs=slabs,
        foundations=foundations,
        section_specs=section_specs,
        layer_roles=layer_roles,
        section_catalog=section_catalog or {},
    )


def to_manifest_members(
    result: ExtractionResult,
    floor_id_default: str,
    project_id: str,
    transforms: Optional[Dict[str, Any]] = None,
) -> List[MemberInstance]:
    """ExtractionResult → MemberInstance[] (Z-Stacking 적용).
    
    Args:
        floor_id_default: 폴백 층 ID
        project_id: 프로젝트 ID
        transforms: {sheet_id: SheetTransform}
    """
    members: List[MemberInstance] = []
    cat = result.section_catalog or {}
    trans = transforms or {}

    def _apply(x, y, sid):
        if sid in trans:
            t = trans[sid]
            # tx/ty는 앵커 정렬용, tz는 SL 층고용
            return x + t.tx, y + t.ty, t.tz
        return x, y, 0.0

    # COLUMN
    for i, (c, sid) in enumerate(result.columns, 1):
        gx, gy, gz = _apply(c.cx, c.cy, sid)
        spec_symbol = f"COL-MEAS-{int(c.width_mm)}x{int(c.height_mm)}"
        members.append(MemberInstance(
            id=f"COL-{sid}-{i:04d}",
            spec=spec_symbol,
            type="column",
            floor=sid,
            at=GridRef(xy=[gx, gy], z=gz),
        ))

    # BEAM
    for i, (b, sid) in enumerate(result.beams, 1):
        gx0, gy0, gz0 = _apply(b.p0[0], b.p0[1], sid)
        gx1, gy1, gz1 = _apply(b.p1[0], b.p1[1], sid)
        
        if b.section_symbol and b.section_symbol in cat:
            spec = b.section_symbol
        elif b.section_symbol:
            spec = f"UNKNOWN-{b.section_symbol}"
        else:
            spec = f"UNKNOWN-BEAM-NOLABEL"

        members.append(MemberInstance(
            id=f"BM-{sid}-{i:04d}",
            spec=spec,
            type="beam",
            floor=sid,
            from_=GridRef(xy=[gx0, gy0], z=gz0),
            to=GridRef(xy=[gx1, gy1], z=gz1),
        ))

    # WALL
    for i, (w, sid) in enumerate(result.walls, 1):
        gx0, gy0, gz0 = _apply(w.p0[0], w.p0[1], sid)
        gx1, gy1, gz1 = _apply(w.p1[0], w.p1[1], sid)
        sym = f"WALL-MEAS-T{int(w.thickness_mm)}"
        members.append(MemberInstance(
            id=f"WL-{sid}-{i:04d}",
            spec=sym,
            type="wall",
            floor=sid,
            polygon=[
                GridRef(xy=[gx0, gy0], z=gz0),
                GridRef(xy=[gx1, gy1], z=gz1),
            ],
        ))

    # SLAB
    for i, (s, sid) in enumerate(result.slabs, 1):
        gz = trans[sid].tz if sid in trans else 0.0
        poly_g = []
        for p in s.polygon:
            gx, gy, _ = _apply(p[0], p[1], sid)
            poly_g.append(GridRef(xy=[gx, gy], z=gz))

        if s.matched_from_catalog and s.section_symbol:
            spec = f"SLAB-{s.section_symbol}-T{int(s.thickness_mm)}"
        elif s.section_symbol:
            spec = f"SLAB-{s.section_symbol}-UNMATCHED"
        else:
            spec = f"SLAB-T{int(s.thickness_mm)}-UNVERIFIED"

        members.append(MemberInstance(
            id=f"SL-{sid}-{i:04d}",
            spec=spec,
            type="slab",
            floor=sid,
            polygon=poly_g,
        ))

    # FND
    for i, (f, sid) in enumerate(result.foundations, 1):
        gx, gy, gz = _apply(f.cx, f.cy, sid)
        sym = f"FND-MEAS-{int(f.width_mm)}x{int(f.height_mm)}"
        members.append(MemberInstance(
            id=f"FND-{sid}-{i:04d}",
            spec=sym,
            type="foundation",
            floor=sid,
            at=GridRef(xy=[gx, gy], z=gz),
        ))
    
    return members
