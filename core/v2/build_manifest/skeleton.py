"""
skeleton.py — DrawingMeta → Manifest 골격 (v4 P1.8)
=====================================================
project / floors 만 채운 초기 매니페스트.
grid·members는 후속 Phase에서.
"""
from __future__ import annotations

from typing import List

from core.manifest_parser import (
    FloorDef,
    GridConfig,
    ManifestModel,
    ProjectMeta,
)
from core.v2.inspect.meta_pipeline import DrawingMeta
from core.v2.inspect.sl_extractor import extract_floors_from_drawing


# 표준 층고 (KS 사전지식 — 실측 SL 우선, 누락 시 폴백)
DEFAULT_FLOOR_HEIGHT_MM = 3500.0


def build_skeleton(
    meta: DrawingMeta,
    project_id: str,
    project_name: str,
    units: str = "mm",
) -> ManifestModel:
    """DrawingMeta + project 메타 → Manifest 골격.

    - project: id, name, units
    - floors: 시트 floor_label 또는 sheet_id에서 추출, z_sl로 z_base 결정
    - grid: None (Phase 2에서 작성)
    - members: [] (Phase 4에서 작성)
    """
    # 1. 도면 전체에서 '지하2층 SL = GL.-9.05' 형식으로 자동 추출 (1순위)
    all_labels = [(lab.text, lab.x, lab.y) for lab in meta.text_stats.all()]
    auto_floors = extract_floors_from_drawing(all_labels)

    # 2. 시트별 z_sl 폴백 (sl_extractor 별도 매칭)
    floor_map: dict[str, float] = dict(auto_floors)
    for s in meta.sheets:
        floor_id = s.floor_label or s.sheet_id
        z_sl = s.z_sl if s.z_sl is not None else None
        if z_sl is None:
            continue
        if floor_id not in floor_map or z_sl < floor_map[floor_id]:
            floor_map[floor_id] = z_sl

    # 3. 모두 없으면 sheet_id 기본 floor 1개
    if not floor_map:
        floor_map = {(meta.sheets[0].sheet_id if meta.sheets else "1F"): 0.0}

    # Z 오름차순 정렬
    sorted_floors = sorted(floor_map.items(), key=lambda kv: kv[1])

    # spec contract: z_base ≥ 0 강제 → 가장 낮은 SL을 0으로 정규화
    if sorted_floors:
        offset = sorted_floors[0][1]
        sorted_floors = [(fid, z - offset) for fid, z in sorted_floors]

    # FloorDef 생성 (height = 다음 층까지, 단일 시트면 DEFAULT)
    floors: List[FloorDef] = []
    for i, (fid, z_base) in enumerate(sorted_floors):
        if i + 1 < len(sorted_floors):
            raw_height = sorted_floors[i + 1][1] - z_base
            height = raw_height if raw_height > 0 else DEFAULT_FLOOR_HEIGHT_MM
        else:
            height = DEFAULT_FLOOR_HEIGHT_MM
        floors.append(FloorDef(
            id=fid,
            z_base=z_base,
            height=height,
        ))

    return ManifestModel(
        version="1.0",
        project=ProjectMeta(
            id=project_id,
            name=project_name,
            units="mm",
        ),
        grid=None,        # Phase 2
        floors=floors or [
            FloorDef(id="1F", z_base=0.0, height=DEFAULT_FLOOR_HEIGHT_MM)
        ],
        members=[],       # Phase 4
    )
