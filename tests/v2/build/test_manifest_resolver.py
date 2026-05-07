"""
test_manifest_resolver.py — Manifest → ResolvedMember (RED+GREEN)
==================================================================
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.manifest_parser import (
    FloorDef,
    GridConfig,
    GridRef,
    ManifestModel,
    MemberInstance,
    ProjectMeta,
)
from core.v2.build.manifest_resolver import resolve, resolve_grid_ref


class TestResolveGridRef(unittest.TestCase):
    def test_xy_passthrough(self):
        ref = GridRef(xy=[1000.0, 2000.0])
        result = resolve_grid_ref(ref, grid=None)
        self.assertEqual(result, (1000.0, 2000.0))

    def test_grid_lookup(self):
        grid = GridConfig(
            origin=[100, 200], rotation=0,
            x_lines={"A": 0, "B": 6000},
            y_lines={"1": 0, "2": 8000},
        )
        ref = GridRef(grid=["B", "2"])
        x, y = resolve_grid_ref(ref, grid)
        # B=6000 + origin_x=100, 2=8000 + origin_y=200
        self.assertAlmostEqual(x, 6100)
        self.assertAlmostEqual(y, 8200)


class TestResolve(unittest.TestCase):
    def test_basic_manifest(self):
        m = ManifestModel(
            version="1.0",
            project=ProjectMeta(id="T1", name="Test"),
            grid=GridConfig(
                origin=[0, 0], rotation=0,
                x_lines={"A": 0, "B": 6000},
                y_lines={"1": 0, "2": 8000},
            ),
            floors=[FloorDef(id="1F", z_base=0, height=4500)],
            members=[
                MemberInstance(
                    id="C-A1", spec="C1", type="column", floor="1F",
                    at=GridRef(grid=["A", "1"]),
                ),
            ],
        )
        resolved = resolve(m, spec_lookup={"C1": {"width_mm": 600, "height_mm": 600}})
        self.assertEqual(len(resolved), 1)
        r = resolved[0]
        self.assertEqual(r.at_xy, (0, 0))
        self.assertEqual(r.z_bottom, 0)
        self.assertEqual(r.z_top, 4500)
        self.assertEqual(r.width_mm, 600)
        self.assertEqual(r.height_mm, 600)


if __name__ == "__main__":
    unittest.main(verbosity=2)
