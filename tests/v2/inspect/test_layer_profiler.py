"""
test_layer_profiler.py — 레이어 통계 자동 분석 (RED)
=====================================================
v4 P1.2.

검증:
  1. 레이어별 엔티티 수 카운트
  2. dominant entity type 식별
  3. bbox 계산
  4. mean entity size
  5. 빈 레이어 처리
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import ezdxf

from core.v2.inspect.layer_profiler import (
    LayerStat,
    profile_layers,
)


class TestProfileLayers(unittest.TestCase):
    def test_basic_counts(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_line((0, 0), (1000, 0), dxfattribs={"layer": "S-BEAM"})
        msp.add_line((0, 0), (0, 1000), dxfattribs={"layer": "S-BEAM"})
        msp.add_line((100, 100), (200, 200), dxfattribs={"layer": "S-COL"})

        stats = profile_layers(doc)
        self.assertIn("S-BEAM", stats)
        self.assertIn("S-COL", stats)
        self.assertEqual(stats["S-BEAM"].entity_count, 2)
        self.assertEqual(stats["S-COL"].entity_count, 1)

    def test_dominant_entity_type(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        # 5 LINE + 1 POLYLINE → dominant = LINE
        for i in range(5):
            msp.add_line((i, 0), (i, 100), dxfattribs={"layer": "WALL"})
        msp.add_lwpolyline(
            [(0, 0), (10, 0), (10, 10), (0, 10)],
            dxfattribs={"layer": "WALL"},
            close=True,
        )
        stats = profile_layers(doc)
        self.assertEqual(stats["WALL"].dominant_type, "LINE")

    def test_bbox(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_line((10, 20), (100, 200), dxfattribs={"layer": "L1"})
        stats = profile_layers(doc)
        bbox = stats["L1"].bbox
        self.assertAlmostEqual(bbox[0], 10.0, places=1)   # xmin
        self.assertAlmostEqual(bbox[1], 20.0, places=1)   # ymin
        self.assertAlmostEqual(bbox[2], 100.0, places=1)  # xmax
        self.assertAlmostEqual(bbox[3], 200.0, places=1)  # ymax

    def test_empty_doc(self):
        doc = ezdxf.new()
        stats = profile_layers(doc)
        self.assertEqual(len(stats), 0)

    def test_layer_stat_structure(self):
        # LayerStat dataclass 필드
        s = LayerStat(
            name="X", entity_count=5, dominant_type="LINE",
            bbox=(0, 0, 100, 100), mean_entity_size=50.0,
        )
        self.assertEqual(s.name, "X")
        self.assertEqual(s.entity_count, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
