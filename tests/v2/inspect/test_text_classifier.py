"""
test_text_classifier.py — TEXT/MTEXT 7부류 분류 (RED)
=======================================================
v4 P1.3.

검증 7부류:
  1. grid_x_label   ^X\d+[a-z]?$
  2. grid_y_label   ^Y\d+[a-z]?$
  3. floor_label    ^(B?\d+F|RF|MF|PIT)$
  4. sl_value       'SL\s*=\s*GL\.\s*[+-]?\d+\.\d+'
  5. section_code   ^(C|TC|RG|G|B|TB|FB|W|F)\d+[A-Z]?$
  6. sheet_code     ^S\d{2}-\d{3}$
  7. dim_text       숫자만 (단순 측정값)
  + unknown
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import ezdxf

from core.v2.inspect.text_classifier import (
    TextCategory,
    TextStats,
    classify_single,
    classify_text,
)


class TestSingleClassify(unittest.TestCase):
    """개별 문자열 분류."""

    def test_grid_x_labels(self):
        for t in ["X1", "X2", "X13", "X13a", "X22b"]:
            self.assertEqual(classify_single(t), TextCategory.GRID_X)

    def test_grid_y_labels(self):
        for t in ["Y1", "Y18", "Y22a"]:
            self.assertEqual(classify_single(t), TextCategory.GRID_Y)

    def test_floor_labels(self):
        for t in ["B1F", "B2F", "1F", "2F", "RF", "MF", "PIT"]:
            self.assertEqual(classify_single(t), TextCategory.FLOOR)

    def test_sl_values(self):
        for t in ["SL=GL.-9.05", "SL = GL.-5.60", "SL=GL.+0.000",
                  "SL = GL. -9.05m"]:
            self.assertEqual(classify_single(t), TextCategory.SL_VALUE)

    def test_section_codes(self):
        for t in ["C1", "TC1", "RG1", "G2", "B5", "TB1", "FB3", "W1", "F2"]:
            self.assertEqual(classify_single(t), TextCategory.SECTION_CODE)

    def test_sheet_codes(self):
        for t in ["S30-001", "S30-002", "S99-999"]:
            self.assertEqual(classify_single(t), TextCategory.SHEET_CODE)

    def test_dim_text(self):
        for t in ["3450", "12750", "150"]:
            self.assertEqual(classify_single(t), TextCategory.DIM)

    def test_unknown(self):
        for t in ["헬로", "ABC", "공동주택", "기둥일람표"]:
            self.assertEqual(classify_single(t), TextCategory.UNKNOWN)


class TestClassifyText(unittest.TestCase):
    """DXF 전체 TEXT/MTEXT 분류."""

    def test_basic_dxf(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_text("X1", dxfattribs={"insert": (100, 0)})
        msp.add_text("Y1", dxfattribs={"insert": (0, 100)})
        msp.add_text("S30-001", dxfattribs={"insert": (0, 0)})
        msp.add_text("C1", dxfattribs={"insert": (50, 50)})

        stats = classify_text(doc)
        self.assertGreaterEqual(stats.count(TextCategory.GRID_X), 1)
        self.assertGreaterEqual(stats.count(TextCategory.GRID_Y), 1)
        self.assertGreaterEqual(stats.count(TextCategory.SHEET_CODE), 1)
        self.assertGreaterEqual(stats.count(TextCategory.SECTION_CODE), 1)

    def test_text_stats_structure(self):
        stats = TextStats()
        stats.add(TextCategory.GRID_X, "X1", 100.0, 0.0)
        stats.add(TextCategory.GRID_X, "X2", 200.0, 0.0)
        self.assertEqual(stats.count(TextCategory.GRID_X), 2)
        labels = stats.by_category(TextCategory.GRID_X)
        self.assertEqual(len(labels), 2)
        self.assertEqual(labels[0].text, "X1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
