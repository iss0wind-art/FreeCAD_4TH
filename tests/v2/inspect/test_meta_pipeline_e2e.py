"""
test_meta_pipeline_e2e.py — DrawingMeta + Manifest 골격 e2e (RED)
==================================================================
v4 P1.7 + P1.8 통합 검증.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import ezdxf

from core.v2.build_manifest.skeleton import build_skeleton
from core.v2.inspect.meta_pipeline import inspect


class TestInspectSynthetic(unittest.TestCase):
    """합성 DXF로 inspect → Manifest 골격."""

    def test_inspect_creates_meta(self):
        # 합성 DXF
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            tmp = Path(f.name)

        try:
            doc = ezdxf.new()
            doc.header["$INSUNITS"] = 4  # mm
            msp = doc.modelspace()
            msp.add_line((0, 0), (10000, 10000), dxfattribs={"layer": "S-BEAM"})
            msp.add_text("S30-001", dxfattribs={"insert": (5000, 5000)})
            msp.add_text("B2F", dxfattribs={"insert": (5000, 4500)})
            msp.add_text("SL=GL.-9.05", dxfattribs={"insert": (1000, 1000)})
            doc.saveas(str(tmp))

            meta = inspect(tmp)
            self.assertEqual(meta.units, "mm")
            self.assertGreater(len(meta.layer_stats), 0)
            self.assertGreaterEqual(len(meta.sheets), 1)
            self.assertEqual(len(meta.fingerprint), 12)

            # Manifest 골격
            manifest = build_skeleton(meta, "TEST-001", "Test Project")
            self.assertEqual(manifest.project.id, "TEST-001")
            self.assertEqual(manifest.project.units, "mm")
            self.assertGreater(len(manifest.floors), 0)
            self.assertEqual(manifest.members, [])

        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
