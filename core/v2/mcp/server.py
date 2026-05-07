"""
FreeCAD v4 BOQ MCP 서버
========================
v4 산출물(Manifest, STEP, BOQ)을 Claude가 직접 조회할 수 있게 노출.

[제공 도구]
  - list_projects: output/v2/ 안의 프로젝트 목록
  - get_manifest_summary: Manifest 메타·통계
  - get_step_stats: STEP 파일 솔리드 통계 + BBox
  - get_boq_summary: BOQ JSON 집계
  - list_members: 부재 목록 (필터·페이지)
  - get_drawing_meta: DXF inspect 결과

[실행]
  python core/v2/mcp/server.py

[등록 (Claude Code)]
  ~/.claude/settings.json 의 mcpServers에 추가:
  {
    "mcpServers": {
      "freecad-v2": {
        "command": "python",
        "args": ["D:/Git/FreeCAD_4TH/core/v2/mcp/server.py"]
      }
    }
  }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))

from fastmcp import FastMCP

mcp = FastMCP("freecad-v2-boq")

OUTPUT_V2 = ROOT / "output" / "v2"


# ─────────────────────────────────────────────────────────────
# list_projects
# ─────────────────────────────────────────────────────────────
def list_projects() -> List[Dict[str, Any]]:
    """v4 시스템 산출물이 있는 프로젝트 목록 (output/v2/<id>)."""
    if not OUTPUT_V2.exists():
        return []

    projects = []
    for d in OUTPUT_V2.iterdir():
        if not d.is_dir():
            continue
        info = {
            "project_id": d.name,
            "manifest_yaml": (d / "manifest.boq.yaml").exists(),
            "step_file": None,
            "boq_json": (d / "boq.json").exists(),
            "boq_csv": (d / "boq.csv").exists(),
            "render_pngs": [],
        }
        # STEP 찾기
        for step in d.glob("*.step"):
            info["step_file"] = step.name
            info["step_size_mb"] = round(step.stat().st_size / 1024 / 1024, 2)
            break
        # PNG 찾기
        for png in d.glob("*.png"):
            info["render_pngs"].append(png.name)
        projects.append(info)
    return projects


# ─────────────────────────────────────────────────────────────
# get_manifest_summary
# ─────────────────────────────────────────────────────────────
def get_manifest_summary(project_id: str) -> Dict[str, Any]:
    """프로젝트 Manifest 메타·통계."""
    yaml_path = OUTPUT_V2 / project_id / "manifest.boq.yaml"
    if not yaml_path.exists():
        return {"error": f"manifest 없음: {yaml_path}"}

    import yaml
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    members = data.get("members", [])
    floors = data.get("floors", [])
    grid = data.get("grid")

    # 타입별 카운트
    from collections import Counter
    type_counts = Counter(m.get("type", "?") for m in members)
    floor_counts = Counter(m.get("floor", "?") for m in members)

    return {
        "project_id": data.get("project", {}).get("id"),
        "project_name": data.get("project", {}).get("name"),
        "version": data.get("version"),
        "units": data.get("project", {}).get("units"),
        "total_members": len(members),
        "type_counts": dict(type_counts),
        "floor_counts": dict(floor_counts),
        "floors": [{"id": f["id"], "z_base": f["z_base"], "height": f["height"]}
                   for f in floors],
        "has_grid": grid is not None,
        "grid_info": {
            "x_lines": len(grid.get("x_lines", {})) if grid else 0,
            "y_lines": len(grid.get("y_lines", {})) if grid else 0,
            "origin": grid.get("origin") if grid else None,
        } if grid else None,
        "yaml_size_kb": round(yaml_path.stat().st_size / 1024, 1),
    }


# ─────────────────────────────────────────────────────────────
# get_boq_summary
# ─────────────────────────────────────────────────────────────
def get_boq_summary(project_id: str) -> Dict[str, Any]:
    """BOQ JSON 집계 (체적/면적/거푸집/길이)."""
    boq_path = OUTPUT_V2 / project_id / "boq.json"
    if not boq_path.exists():
        return {"error": f"boq.json 없음: {boq_path}"}

    with open(boq_path, encoding="utf-8") as f:
        data = json.load(f)

    return {
        "project_id": data.get("project_id"),
        "generated": data.get("generated"),
        "total_members": data.get("total_members"),
        "by_type": data.get("by_type", {}),
        "boq_size_kb": round(boq_path.stat().st_size / 1024, 1),
    }


# ─────────────────────────────────────────────────────────────
# list_members
# ─────────────────────────────────────────────────────────────
def list_members(
    project_id: str,
    type_filter: Optional[str] = None,
    floor_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """부재 목록 (필터링 + 페이지)."""
    yaml_path = OUTPUT_V2 / project_id / "manifest.boq.yaml"
    if not yaml_path.exists():
        return {"error": f"manifest 없음"}

    import yaml
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    members = data.get("members", [])

    # 필터
    if type_filter:
        members = [m for m in members if m.get("type") == type_filter]
    if floor_filter:
        members = [m for m in members if m.get("floor") == floor_filter]

    total = len(members)
    page = members[offset:offset + limit]

    return {
        "total_filtered": total,
        "offset": offset,
        "limit": limit,
        "members": page,
    }


# ─────────────────────────────────────────────────────────────
# get_step_stats
# ─────────────────────────────────────────────────────────────
def get_step_stats(project_id: str) -> Dict[str, Any]:
    """STEP 파일 통계 (FreeCAD 필요)."""
    step_files = list((OUTPUT_V2 / project_id).glob("*.step"))
    if not step_files:
        return {"error": "STEP 파일 없음"}
    step = step_files[0]

    try:
        import Part  # type: ignore
    except ImportError:
        return {
            "error": "FreeCAD 환경 필요 (freecadcmd 또는 FreeCAD Python)",
            "step_file": str(step),
            "step_size_mb": round(step.stat().st_size / 1024 / 1024, 2),
        }

    shape = Part.read(str(step))
    bbox = shape.BoundBox
    return {
        "step_file": step.name,
        "step_size_mb": round(step.stat().st_size / 1024 / 1024, 2),
        "n_solids": len(shape.Solids),
        "bbox_mm": {
            "x": [bbox.XMin, bbox.XMax],
            "y": [bbox.YMin, bbox.YMax],
            "z": [bbox.ZMin, bbox.ZMax],
        },
        "extent_m": {
            "x": round(bbox.XLength / 1000, 2),
            "y": round(bbox.YLength / 1000, 2),
            "z": round(bbox.ZLength / 1000, 2),
        },
    }


# ─────────────────────────────────────────────────────────────
# get_drawing_meta
# ─────────────────────────────────────────────────────────────
def get_drawing_meta(dxf_path: str) -> Dict[str, Any]:
    """DXF 메타 분석 (units/sheets/layers/text 통계).

    Args:
        dxf_path: DXF 파일 절대 경로
    """
    p = Path(dxf_path)
    if not p.exists():
        return {"error": f"파일 없음: {dxf_path}"}

    from core.v2.inspect.meta_pipeline import inspect

    meta = inspect(p)

    layer_top = sorted(
        meta.layer_stats.items(),
        key=lambda kv: kv[1].entity_count,
        reverse=True,
    )[:10]

    return {
        "path": meta.path,
        "units": meta.units,
        "drawing_kind": meta.drawing_kind.value,
        "fingerprint": meta.fingerprint,
        "bbox": meta.bbox,
        "n_sheets": len(meta.sheets),
        "sheet_pitch": meta.sheet_pitch,
        "n_layers": len(meta.layer_stats),
        "top10_layers": [
            {"name": name, "count": st.entity_count, "dom": st.dominant_type}
            for name, st in layer_top
        ],
        "text_stats": {
            cat.value: meta.text_stats.count(cat)
            for cat in meta.text_stats.labels.keys()
        },
        "sl_per_sheet": meta.sl_per_sheet,
    }


# ─────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# MCP 도구 일괄 등록
# ─────────────────────────────────────────────────────────────
mcp.tool(list_projects)
mcp.tool(get_manifest_summary)
mcp.tool(get_boq_summary)
mcp.tool(list_members)
mcp.tool(get_step_stats)
mcp.tool(get_drawing_meta)


if __name__ == "__main__":
    mcp.run()
