"""
test_boq.py — BOQ 수량 + 출력 (RED+GREEN)
============================================
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.v2.boq.exporter import export_boq_csv, export_boq_json
from core.v2.boq.quantity_calc import compute_quantity
from core.v2.build.manifest_resolver import ResolvedMember


class TestQuantity(unittest.TestCase):
    def test_column_volume(self):
        m = ResolvedMember(
            id="C1", type="column", spec="C1", floor_id="1F",
            z_bottom=0, z_top=4500,
            at_xy=(0, 0), width_mm=600, height_mm=600,
        )
        q = compute_quantity(m)
        # 0.6 * 0.6 * 4.5 = 1.62
        self.assertAlmostEqual(q.volume_m3, 1.62, places=2)

    def test_beam_volume(self):
        m = ResolvedMember(
            id="B1", type="beam", spec="RG1", floor_id="1F",
            z_bottom=0, z_top=4500,
            from_xy=(0, 0), to_xy=(6000, 0),
            width_mm=400, height_mm=800,
        )
        q = compute_quantity(m)
        # 6.0 * 0.4 * 0.8 = 1.92
        self.assertAlmostEqual(q.volume_m3, 1.92, places=2)
        self.assertAlmostEqual(q.length_m, 6.0)

    def test_export_json(self):
        m = ResolvedMember(
            id="C1", type="column", spec="C1", floor_id="1F",
            z_bottom=0, z_top=4500,
            at_xy=(0, 0), width_mm=600, height_mm=600,
        )
        qs = [compute_quantity(m)]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = Path(f.name)
        try:
            export_boq_json(qs, tmp, project_id="TEST")
            data = json.loads(tmp.read_text(encoding="utf-8"))
            self.assertEqual(data["project_id"], "TEST")
            self.assertEqual(data["total_members"], 1)
            self.assertIn("column", data["by_type"])
        finally:
            tmp.unlink(missing_ok=True)

    def test_export_csv(self):
        m = ResolvedMember(
            id="C1", type="column", spec="C1", floor_id="1F",
            z_bottom=0, z_top=4500,
            at_xy=(0, 0), width_mm=600, height_mm=600,
        )
        qs = [compute_quantity(m)]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            tmp = Path(f.name)
        try:
            export_boq_csv(qs, tmp)
            content = tmp.read_bytes()
            self.assertTrue(content.startswith(b"\xef\xbb\xbf"))   # BOM
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
