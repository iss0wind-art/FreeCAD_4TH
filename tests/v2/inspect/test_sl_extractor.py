"""
test_sl_extractor.py — SL 표고 자동 파싱 (RED)
================================================
v4 P1.5.

검증:
  1. SL=GL.-9.05  → -9050 mm
  2. SL=GL.+0.000 → 0 mm
  3. m → mm 자동 변환
  4. 시트별 SL 매칭 (가장 가까운 시트)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.v2.inspect.sl_extractor import (
    parse_sl_value,
    extract_sl_per_sheet,
)
from core.v2.inspect.sheet_segmenter import SheetMeta


class TestParseSLValue(unittest.TestCase):
    def test_negative(self):
        self.assertAlmostEqual(parse_sl_value("SL=GL.-9.05"), -9050.0)

    def test_negative_with_space(self):
        self.assertAlmostEqual(parse_sl_value("SL = GL.-9.05"), -9050.0)

    def test_positive_zero(self):
        self.assertAlmostEqual(parse_sl_value("SL=GL.+0.000"), 0.0)

    def test_positive(self):
        self.assertAlmostEqual(parse_sl_value("SL=GL.+5.30"), 5300.0)

    def test_with_m_suffix(self):
        self.assertAlmostEqual(parse_sl_value("SL = GL. -9.05m"), -9050.0)

    def test_invalid_returns_none(self):
        self.assertIsNone(parse_sl_value("아무 텍스트"))


class TestExtractPerSheet(unittest.TestCase):
    def test_match_nearest_sheet(self):
        sheets = [
            SheetMeta(sheet_id="S30-001", floor_label="B2F",
                      bbox=(0, 0, 100, 100), sw_corner=(0, 0), confidence=1.0),
            SheetMeta(sheet_id="S30-002", floor_label="B1F",
                      bbox=(200, 0, 300, 100), sw_corner=(200, 0), confidence=1.0),
        ]
        # SL 라벨 위치
        sl_labels = [
            ("SL=GL.-9.05", 50, 50),     # → S30-001
            ("SL=GL.-5.60", 250, 50),    # → S30-002
        ]
        result = extract_sl_per_sheet(sheets, sl_labels)
        self.assertAlmostEqual(result["S30-001"], -9050.0)
        self.assertAlmostEqual(result["S30-002"], -5600.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
