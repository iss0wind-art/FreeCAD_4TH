"""
test_boq_solid_builder.py — 솔리드 빌더 단위 테스트
====================================================
TDD RED: FreeCAD 의존성 없이 검증 가능한 부분만.

검증 항목:
  1. 입력 유효성 검증 (validate_*)
  2. 보 4코너 좌표 계산 (순수 기하)
  3. FreeCAD 가용성 체크
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline.boq_solid_builder import (
    beam_corner_points,
    has_freecad,
    validate_beam_params,
    validate_box_params,
    validate_prism_params,
)


# ─────────────────────────────────────────────────────────────
# 입력 유효성 검증
# ─────────────────────────────────────────────────────────────
class TestValidateBox(unittest.TestCase):
    def test_valid_box(self):
        ok, msg = validate_box_params(zb=-9050, zt=-5600, w=400, h=800)
        self.assertTrue(ok, msg)

    def test_zero_height(self):
        ok, _ = validate_box_params(zb=0, zt=0, w=400, h=800)
        self.assertFalse(ok)

    def test_negative_height(self):
        ok, _ = validate_box_params(zb=0, zt=-100, w=400, h=800)
        self.assertFalse(ok)

    def test_too_small_width(self):
        ok, _ = validate_box_params(zb=0, zt=100, w=5, h=800)  # < 10
        self.assertFalse(ok)

    def test_too_small_depth(self):
        ok, _ = validate_box_params(zb=0, zt=100, w=400, h=5)
        self.assertFalse(ok)


class TestValidatePrism(unittest.TestCase):
    def test_valid_prism(self):
        pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
        ok, _ = validate_prism_params(pts, zb=0, zt=100)
        self.assertTrue(ok)

    def test_too_few_points(self):
        ok, _ = validate_prism_params([(0, 0), (100, 0)], zb=0, zt=100)
        self.assertFalse(ok)

    def test_zero_height(self):
        pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
        ok, _ = validate_prism_params(pts, zb=0, zt=0)
        self.assertFalse(ok)


class TestValidateBeam(unittest.TestCase):
    def test_valid_beam(self):
        ok, _ = validate_beam_params(0, 0, 6000, 0, bw=400, bh=800,
                                     zb=-9050, zt=-5600)
        self.assertTrue(ok)

    def test_zero_length(self):
        ok, _ = validate_beam_params(0, 0, 0, 0, bw=400, bh=800,
                                     zb=-9050, zt=-5600)
        self.assertFalse(ok)

    def test_too_short(self):
        # length < 100
        ok, _ = validate_beam_params(0, 0, 50, 0, bw=400, bh=800,
                                     zb=-9050, zt=-5600)
        self.assertFalse(ok)

    def test_negative_height(self):
        ok, _ = validate_beam_params(0, 0, 6000, 0, bw=400, bh=800,
                                     zb=0, zt=-100)
        self.assertFalse(ok)


# ─────────────────────────────────────────────────────────────
# 보 4코너 좌표 계산
# ─────────────────────────────────────────────────────────────
class TestBeamCorners(unittest.TestCase):
    """보 중심선 → 4코너 (직사각형 단면 양옆 오프셋)."""

    def test_horizontal_beam(self):
        # X축 방향 보, 너비 400
        pts = beam_corner_points(0, 0, 6000, 0, bw=400)
        self.assertEqual(len(pts), 4)
        # Y로 ±200 떨어진 4점
        ys = sorted({p[1] for p in pts})
        self.assertEqual(ys, [-200, 200])

    def test_vertical_beam(self):
        # Y축 방향 보
        pts = beam_corner_points(0, 0, 0, 6000, bw=400)
        xs = sorted({p[0] for p in pts})
        self.assertEqual(xs, [-200, 200])

    def test_diagonal_beam(self):
        # 45° 대각 보, 너비 400 → 양옆 오프셋 200
        pts = beam_corner_points(0, 0, 1000, 1000, bw=400)
        # 4개 코너, 각 점이 중심선에서 200mm 거리
        for px, py in pts:
            # 중심선 (0,0)-(1000,1000)에 대한 거리
            # 직선 y=x → |y-x|/sqrt(2)
            d = abs(py - px) / math.sqrt(2)
            self.assertAlmostEqual(d, 200, places=2)


# ─────────────────────────────────────────────────────────────
# FreeCAD 가용성
# ─────────────────────────────────────────────────────────────
class TestFreeCADAvailability(unittest.TestCase):
    def test_has_freecad_returns_bool(self):
        result = has_freecad()
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main(verbosity=2)
