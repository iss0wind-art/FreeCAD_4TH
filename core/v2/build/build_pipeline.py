"""
build_pipeline.py — Manifest → STEP 통합 (v4 P5)
==================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Union

from core.manifest_parser import ManifestModel
from core.v2.build.manifest_resolver import ResolvedMember, resolve
from core.v2.build.solid_factory import build_member_solid
from core.v2.build.step_exporter import export_step


@dataclass
class BuildReport:
    total_members: int = 0
    succeeded: int = 0
    failed: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    out_path: str = ""


def build_step_from_manifest(
    manifest: ManifestModel,
    out_path: Union[str, Path],
    spec_lookup: Dict[str, dict] = None,
) -> BuildReport:
    """Manifest → STEP 빌드.

    Args:
        spec_lookup: {symbol: {width_mm, height_mm, thickness_mm}}

    Returns:
        BuildReport
    """
    resolved = resolve(manifest, spec_lookup=spec_lookup or {})

    shapes_with_names = []
    by_type: Dict[str, int] = {}
    succeeded = 0
    failed = 0

    for r in resolved:
        shape = build_member_solid(r)
        if shape is None:
            failed += 1
            continue
        shapes_with_names.append((shape, r.id))
        succeeded += 1
        by_type[r.type] = by_type.get(r.type, 0) + 1

    out = export_step(shapes_with_names, out_path)

    return BuildReport(
        total_members=len(resolved),
        succeeded=succeeded,
        failed=failed,
        by_type=by_type,
        out_path=str(out),
    )
