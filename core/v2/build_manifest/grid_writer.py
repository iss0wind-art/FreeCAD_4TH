"""
grid_writer.py — Manifest.grid 자동 작성 (v4 P2.6)
=====================================================
시트 1개의 SheetGrid → Manifest.grid (대표 시트 채택).

[전략]
  - 격자 라벨이 가장 풍부한 시트를 대표 시트로
  - 라벨 정렬 (X1, X2, ... → 알파벳 순; Y1, Y2, ...도 동일)
  - 미검출 시 None (xy 폴백 모드)
"""
from __future__ import annotations

from typing import Dict, Optional

from core.manifest_parser import GridConfig, ManifestModel
from core.v2.coords.grid_resolver import SheetGrid


def write_grid_to_manifest(
    manifest: ManifestModel,
    grids: Dict[str, SheetGrid],
) -> ManifestModel:
    """대표 시트의 격자를 Manifest.grid에 채움.

    grids 비어있으면 manifest 그대로 (grid=None).
    """
    if not grids:
        return manifest

    # 대표 시트: 라벨 수 가장 많은 시트
    rep = max(
        grids.values(),
        key=lambda g: len(g.x_lines) + len(g.y_lines),
    )

    if not rep.x_lines or not rep.y_lines:
        return manifest

    # spec 검증: x_lines / y_lines 모두 비어있지 않아야 함
    grid_config = GridConfig(
        origin=[float(rep.origin[0]), float(rep.origin[1])],
        rotation=rep.rotation_deg,
        x_lines=dict(sorted(rep.x_lines.items())),
        y_lines=dict(sorted(rep.y_lines.items())),
    )

    # ManifestModel은 frozen 아니므로 직접 갱신
    manifest.grid = grid_config
    return manifest
