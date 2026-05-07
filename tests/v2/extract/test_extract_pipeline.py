"""
test_extract_pipeline.py — 부재 추출 e2e (RED+GREEN)
======================================================
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import ezdxf

from core.v2.extract.extract_pipeline import (
    extract_all_members,
    to_manifest_members,
)
from core.v2.inspect.meta_pipeline import inspect


class TestExtractSynthetic(unittest.TestCase):
    """합성 도면에서 추출."""

    def test_columns_and_beams(self):
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            tmp = Path(f.name)
        try:
            doc = ezdxf.new()
            doc.header["$INSUNITS"] = 4

            msp = doc.modelspace()

            # 기둥 4개 (S-COL 레이어, 600x600 LWPOLYLINE)
            for cx, cy in [(0, 0), (6000, 0), (0, 8000), (6000, 8000)]:
                msp.add_lwpolyline(
                    [(cx - 300, cy - 300), (cx + 300, cy - 300),
                     (cx + 300, cy + 300), (cx - 300, cy + 300)],
                    dxfattribs={"layer": "S-COL"},
                    close=True,
                )

            # 보 4개 (S-BEAM 레이어, LINE)
            msp.add_line((300, 0), (5700, 0), dxfattribs={"layer": "S-BEAM"})
            msp.add_line((300, 8000), (5700, 8000), dxfattribs={"layer": "S-BEAM"})
            msp.add_line((0, 300), (0, 7700), dxfattribs={"layer": "S-BEAM"})
            msp.add_line((6000, 300), (6000, 7700), dxfattribs={"layer": "S-BEAM"})

            doc.saveas(str(tmp))

            meta = inspect(tmp)
            result = extract_all_members(meta)

            self.assertEqual(len(result.columns), 4)
            self.assertGreaterEqual(len(result.beams), 4)

            # MemberInstance 변환
            members = to_manifest_members(result, floor_id="1F", project_id="TEST")
            # 기둥 4 + 보 4 = 8
            self.assertGreaterEqual(len(members), 8)

        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
