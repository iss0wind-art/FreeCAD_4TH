"""
test_cross_drawing_aligner.py — 점군 정합 (RED+GREEN)
=======================================================
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.v2.coords.cross_drawing_aligner import align_point_clouds


class TestAlignPointClouds(unittest.TestCase):
    def test_perfect_match(self):
        # source를 (1000, 2000) 이동 → target과 일치
        src = [(0, 0), (100, 0), (0, 100), (100, 100)]
        tgt = [(1000, 2000), (1100, 2000), (1000, 2100), (1100, 2100)]
        result = align_point_clouds(src, tgt, tolerance_mm=10.0)
        self.assertAlmostEqual(result.tx, 1000, delta=10)
        self.assertAlmostEqual(result.ty, 2000, delta=10)
        self.assertEqual(result.matched_pairs, 4)
        self.assertEqual(result.match_rate, 1.0)

    def test_partial_match(self):
        # source 4개 중 2개만 target에 있음
        src = [(0, 0), (100, 0), (0, 100), (100, 100)]
        tgt = [(1000, 2000), (1100, 2000)]   # 2개만
        result = align_point_clouds(src, tgt, tolerance_mm=10.0)
        self.assertGreaterEqual(result.matched_pairs, 2)

    def test_empty_input(self):
        result = align_point_clouds([], [(0, 0)])
        self.assertEqual(result.matched_pairs, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
