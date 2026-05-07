"""
test_transform_pipeline.py — 좌표 시스템 e2e (RED+GREEN)
==========================================================
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import ezdxf

from core.v2.build_manifest.grid_writer import write_grid_to_manifest
from core.v2.build_manifest.skeleton import build_skeleton
from core.v2.coords.transform_pipeline import build_coord_system
from core.v2.inspect.meta_pipeline import inspect


class TestBuildCoordSystem(unittest.TestCase):
    def test_synthetic_with_grid(self):
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            tmp = Path(f.name)
        try:
            doc = ezdxf.new()
            doc.header["$INSUNITS"] = 4
            msp = doc.modelspace()
            msp.add_text("S30-001", dxfattribs={"insert": (5000, 5000)})
            # 격자 라벨
            msp.add_text("X1", dxfattribs={"insert": (0, 0)})
            msp.add_text("X2", dxfattribs={"insert": (6000, 0)})
            msp.add_text("Y1", dxfattribs={"insert": (0, 0)})
            msp.add_text("Y2", dxfattribs={"insert": (0, 8000)})
            doc.saveas(str(tmp))

            meta = inspect(tmp)
            coord = build_coord_system(meta)

            self.assertGreaterEqual(len(coord.anchors), 1)
            self.assertGreaterEqual(len(coord.transforms), 1)

            # Manifest grid 작성
            manifest = build_skeleton(meta, "TEST-G", "Grid Test")
            manifest = write_grid_to_manifest(manifest, coord.grids)
            if coord.has_grid:
                self.assertIsNotNone(manifest.grid)

        finally:
            tmp.unlink(missing_ok=True)

    def test_no_grid_fallback(self):
        # 격자 없는 도면 → grid=None
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            tmp = Path(f.name)
        try:
            doc = ezdxf.new()
            doc.header["$INSUNITS"] = 4
            msp = doc.modelspace()
            msp.add_text("S30-001", dxfattribs={"insert": (5000, 5000)})
            doc.saveas(str(tmp))

            meta = inspect(tmp)
            coord = build_coord_system(meta)

            self.assertFalse(coord.has_grid)

            manifest = build_skeleton(meta, "TEST-N", "No Grid")
            manifest = write_grid_to_manifest(manifest, coord.grids)
            self.assertIsNone(manifest.grid)

        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
