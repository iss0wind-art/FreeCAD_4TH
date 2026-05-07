"""
test_classify.py — 부재 분류 (RED+GREEN)
==========================================
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.v2.classify.ks_lexicon import (
    MemberType,
    classify_layer_by_keyword,
)
from core.v2.classify.layer_role_inferer import infer_layer_role
from core.v2.inspect.layer_profiler import LayerStat


class TestKeywordClassify(unittest.TestCase):
    def test_column_keywords(self):
        for layer in ["S-COL", "00_COLUMN", "A-COL", "기둥-001",
                      "XR지하2층평면도$0$A-COL"]:
            self.assertEqual(classify_layer_by_keyword(layer), MemberType.COLUMN)

    def test_beam_keywords(self):
        for layer in ["S-BEAM", "S-GIRDER", "00_BEAM", "00_(APT)BEAM",
                      "S-PC-GIRDER", "TB-1", "RG-2"]:
            self.assertEqual(classify_layer_by_keyword(layer), MemberType.BEAM)

    def test_wall_keywords(self):
        for layer in ["A-WALL-RC", "S-WALL", "00_SHEAR.WALL",
                      "00_SHEAR WALL", "S-하부벽체"]:
            self.assertEqual(classify_layer_by_keyword(layer), MemberType.WALL)

    def test_slab_keywords(self):
        for layer in ["S-SLAB", "S-PC-SLAB"]:
            self.assertEqual(classify_layer_by_keyword(layer), MemberType.SLAB)

    def test_foundation_keywords(self):
        for layer in ["S-FOUNDATION", "S-BASE", "S-FND",
                      "FND-001", "MAT-1"]:
            self.assertEqual(classify_layer_by_keyword(layer), MemberType.FOUNDATION)

    def test_ignore_keywords(self):
        for layer in ["A-DIM", "DIMENSION", "00_HATCH",
                      "Defpoints", "A-FUR", "A-WALL-BRICK",
                      "A-CEN-2"]:
            self.assertEqual(classify_layer_by_keyword(layer), MemberType.IGNORE)

    def test_unknown(self):
        self.assertEqual(classify_layer_by_keyword("RANDOM_LAYER"),
                         MemberType.UNKNOWN)


class TestInferLayerRole(unittest.TestCase):
    def test_keyword_match_high_confidence(self):
        stat = LayerStat(
            name="S-COL", entity_count=10, dominant_type="LWPOLYLINE",
            bbox=(0, 0, 1000, 1000), mean_entity_size=500,
        )
        role = infer_layer_role("S-COL", stat)
        self.assertEqual(role.member_type, MemberType.COLUMN)
        self.assertGreaterEqual(role.confidence, 0.8)

    def test_unknown_layer_dominant_fallback(self):
        stat = LayerStat(
            name="WEIRD_LAYER", entity_count=5, dominant_type="LINE",
            bbox=(0, 0, 100, 100), mean_entity_size=50,
        )
        role = infer_layer_role("WEIRD_LAYER", stat)
        # LINE → BEAM 폴백
        self.assertEqual(role.member_type, MemberType.BEAM)
        self.assertLess(role.confidence, 0.7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
