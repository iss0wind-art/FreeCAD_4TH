"""
test_wall_thickness.py — WALL 두께 추정 단위 테스트
====================================================
TDD RED: WALL 두께 추정 로직.

[규칙]
  - 레이어명 패턴 매칭으로 기본 두께 결정
  - 00_SHEAR WALL    → 300mm (전단벽, RC)
  - A-WALL-RC        → 200mm (RC 벽체)
  - S-하부벽체       → 200mm (하부벽체)
  - 기타 (S-????)    → 200mm (기본 폴백)
  - 레이어 미상      → 200mm
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline.wall_thickness import estimate_wall_thickness


class TestEstimateThickness(unittest.TestCase):
    def test_shear_wall_300mm(self):
        self.assertEqual(estimate_wall_thickness("00_SHEAR WALL"), 300)

    def test_xref_a_wall_rc_200mm(self):
        self.assertEqual(
            estimate_wall_thickness("XR지하2층평면도$0$A-WALL-RC"), 200
        )
        self.assertEqual(
            estimate_wall_thickness("XR지하1층평면도$0$A-WALL-RC"), 200
        )

    def test_s_lower_wall_200mm(self):
        self.assertEqual(estimate_wall_thickness("S-하부벽체"), 200)

    def test_unknown_layer_default_200mm(self):
        self.assertEqual(estimate_wall_thickness("UNKNOWN_LAYER"), 200)
        self.assertEqual(estimate_wall_thickness(""), 200)

    def test_case_insensitive(self):
        self.assertEqual(estimate_wall_thickness("00_shear wall"), 300)
        self.assertEqual(estimate_wall_thickness("a-wall-rc"), 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
