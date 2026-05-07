"""
dxf_to_manifest.py — DXF → .boq.yaml CLI (v4 P7)
==================================================
도면 1장 또는 여러 장 → Manifest YAML 출력.

[FreeCAD 무관] — 순수 Python.

사용:
  python tools/v2/dxf_to_manifest.py --dxf <path>... --project-id <id> --out <path.yaml>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import yaml

from core.v2.build_manifest.grid_writer import write_grid_to_manifest
from core.v2.build_manifest.skeleton import build_skeleton
from core.v2.coords.transform_pipeline import build_coord_system
from core.v2.extract.extract_pipeline import (
    extract_all_members,
    to_manifest_members,
)
from core.v2.inspect.meta_pipeline import inspect


def main():
    parser = argparse.ArgumentParser(description="DXF → .boq.yaml")
    parser.add_argument("--dxf", required=True, nargs="+", help="평면도 DXF 경로(들)")
    parser.add_argument("--section-list", nargs="*", default=[],
                        help="단면 일람표 DXF 경로 (보 리스트, 기둥 리스트 등)")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--out", required=True, help="출력 .boq.yaml 경로")
    parser.add_argument("--floor", default=None, help="기본 층 ID (없으면 첫 floor 자동)")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    project_name = args.project_name or args.project_id

    # 첫 DXF 한 장으로 골격 + grid + members
    main_dxf = Path(args.dxf[0])
    print(f"[inspect] {main_dxf}")
    meta = inspect(main_dxf)
    print(f"  units={meta.units}  kind={meta.drawing_kind.value}")
    print(f"  sheets={len(meta.sheets)}  layers={len(meta.layer_stats)}")

    print("[skeleton] Manifest 골격 생성")
    manifest = build_skeleton(meta, args.project_id, project_name)
    print(f"  floors={len(manifest.floors)}")

    print("[coords] 좌표 시스템")
    coord = build_coord_system(meta)
    manifest = write_grid_to_manifest(manifest, coord.grids)
    print(f"  has_grid={coord.has_grid}")

    # 일람표 카탈로그 (있으면)
    catalog = {}
    if args.section_list:
        from core.v2.extract.section_list import parse_multiple_lists
        list_paths = [Path(p) for p in args.section_list if Path(p).exists()]
        print(f"[catalog] 일람표 {len(list_paths)}개 파싱")
        cat_entries = parse_multiple_lists(list_paths)
        catalog = {sym: {
            "width_mm": e.width_mm, "height_mm": e.height_mm,
            "member_type": e.member_type.value,
        } for sym, e in cat_entries.items()}
        print(f"  심볼-단면: {len(catalog)}개 (예: {list(catalog.keys())[:5]})")

    print("[extract] 부재 추출")
    result = extract_all_members(meta, section_catalog=catalog)
    print(f"  COL={len(result.columns)} BEAM={len(result.beams)} "
          f"WALL={len(result.walls)} SLAB={len(result.slabs)} "
          f"FND={len(result.foundations)}")

    floor_id = args.floor if args.floor else manifest.floors[0].id
    members = to_manifest_members(result, floor_id=floor_id,
                                  project_id=args.project_id)
    manifest.members = members
    print(f"  members={len(members)}")

    # YAML 직렬화 (Pydantic v2)
    yaml_text = yaml.safe_dump(
        manifest.model_dump(by_alias=True, exclude_none=True),
        allow_unicode=True, sort_keys=False,
    )
    out_path.write_text(yaml_text, encoding="utf-8")
    print(f"\n저장: {out_path} ({out_path.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
