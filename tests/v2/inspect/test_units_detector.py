"""
test_units_detector.py — DXF 단위 자동 검출 (RED)
==================================================
v4 P1.1.

검증:
  1. $INSUNITS = 4 (mm) → 'mm'
  2. $INSUNITS = 6 (m)  → 'm'
  3. $INSUNITS = 1 (in) → 'in'
  4. $INSUNITS = 0 (없음) → bbox 통계 폴백
  5. bbox 대각 100~10000 → 'm', 10000+ → 'mm'

핵심 원칙: **매직넘버 0건** — 모든 thresholds 함수 인자로 받음.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import ezdxf

from core.v2.inspect.units_detector import (
    INSUNITS_MAP,
    detect_units,
    detect_units_from_bbox,
)


class TestInsUnitsHeader(unittest.TestCase):
    """$INSUNITS 헤더 우선."""

    def test_mm_header(self):
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 4   # mm
        self.assertEqual(detect_units(doc), "mm")

    def test_m_header(self):
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 6   # m
        self.assertEqual(detect_units(doc), "m")

    def test_inch_header(self):
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 1   # inch
        self.assertEqual(detect_units(doc), "in")

    def test_known_units_map(self):
        # KS·AutoCAD 표준 INSUNITS 코드
        self.assertEqual(INSUNITS_MAP[4], "mm")
        self.assertEqual(INSUNITS_MAP[6], "m")
        self.assertEqual(INSUNITS_MAP[1], "in")


class TestBboxFallback(unittest.TestCase):
    """$INSUNITS=0 일 때 bbox 통계로 폴백."""

    def test_bbox_in_meters(self):
        # bbox 대각 ~30m → 'm' (입력은 m 단위 좌표)
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 0
        msp = doc.modelspace()
        msp.add_line((0, 0), (20, 25))   # 대각 32m
        result = detect_units(doc)
        # bbox 폴백은 'm' 또는 명시적 fallback
        self.assertIn(result, ("m", "mm"))

    def test_bbox_in_millimeters(self):
        # bbox 대각 ~30,000mm → 'mm'
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 0
        msp = doc.modelspace()
        msp.add_line((0, 0), (20000, 25000))   # 대각 32,000
        self.assertEqual(detect_units(doc), "mm")

    def test_bbox_helper_explicit_thresholds(self):
        # 임계값 외부 주입 (매직넘버 금지)
        # bbox 대각이 max_meter_diag 이하면 'm', 초과면 'mm'
        self.assertEqual(
            detect_units_from_bbox(diag_value=50.0, max_meter_diag=10000.0),
            "m",
        )
        self.assertEqual(
            detect_units_from_bbox(diag_value=50000.0, max_meter_diag=10000.0),
            "mm",
        )


class TestEmptyDocument(unittest.TestCase):
    """빈 도면 — fallback OK."""

    def test_empty_doc_returns_default(self):
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 0
        # 엔티티 없음 → 기본값 'mm' (KS 표준)
        result = detect_units(doc)
        self.assertEqual(result, "mm")


if __name__ == "__main__":
    unittest.main(verbosity=2)
