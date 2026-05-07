"""
test_sheet_segmenter.py — 시트 자동 검출 (RED)
================================================
v4 P1.4 — **가장 중요한 모듈**.

3중 신호 합의:
  (a) TITLEBLOCK INSERT (가장 강한 신호)
  (b) 표제 TEXT (S30-001, "지하2층 평면도", "101동")
  (c) 외곽 LWPOLYLINE 클러스터링 (DBSCAN-like)

검증:
  1. SheetMeta 데이터 구조
  2. 격자 라벨 X 클러스터링 → sheet pitch 자동 추출
  3. 빈 도면 → 0개 시트
  4. 단일 시트 도면 → 1개 시트
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import ezdxf

from core.v2.inspect.text_classifier import classify_text
from core.v2.inspect.sheet_segmenter import (
    SheetMeta,
    cluster_x_positions,
    detect_sheet_pitch,
    segment_sheets,
)


class TestSheetMetaStructure(unittest.TestCase):
    def test_basic_create(self):
        s = SheetMeta(
            sheet_id="S30-001",
            floor_label="B2F",
            bbox=(0, 0, 100000, 178200),
            sw_corner=(0, 0),
            confidence=0.9,
        )
        self.assertEqual(s.sheet_id, "S30-001")
        self.assertEqual(s.floor_label, "B2F")


class TestClusterXPositions(unittest.TestCase):
    """1D X 클러스터링 — sheet pitch 자동 추출 핵심."""

    def test_three_clusters_evenly_spaced(self):
        # 3 그룹: 100, 200, 300 (간격 100)
        xs = [100, 100.5, 99.8, 200, 200.3, 199.5, 300, 300.1, 299.7]
        clusters = cluster_x_positions(xs, bin_size=50.0)
        self.assertEqual(len(clusters), 3)
        # 각 클러스터 중심
        centers = sorted([c[0] for c in clusters])
        self.assertAlmostEqual(centers[0], 100.0, delta=1.0)
        self.assertAlmostEqual(centers[1], 200.0, delta=1.0)
        self.assertAlmostEqual(centers[2], 300.0, delta=1.0)

    def test_single_cluster(self):
        xs = [50, 50.5, 49.8, 50.2]
        clusters = cluster_x_positions(xs, bin_size=10.0)
        self.assertEqual(len(clusters), 1)

    def test_empty(self):
        clusters = cluster_x_positions([], bin_size=10.0)
        self.assertEqual(clusters, [])


class TestDetectSheetPitch(unittest.TestCase):
    """시트 간격 자동 추출 (mode of differences)."""

    def test_uniform_pitch(self):
        # X 중심: 0, 126_000, 252_000, 378_000 → pitch = 126_000
        sheets = [
            SheetMeta(sheet_id=f"S-{i}", floor_label=f"F{i}",
                      bbox=(i*126_000, 0, (i+1)*126_000, 178_200),
                      sw_corner=(i*126_000, 0), confidence=1.0)
            for i in range(4)
        ]
        pitch_x, pitch_y = detect_sheet_pitch(sheets)
        self.assertAlmostEqual(pitch_x, 126_000, delta=100)

    def test_pkg_pitch(self):
        # PKG: 동 간격 630_000
        sheets = [
            SheetMeta(sheet_id=f"S-{i}", floor_label="B2F",
                      bbox=(i*630_000, 0, i*630_000 + 200_000, 200_000),
                      sw_corner=(i*630_000, 0), confidence=1.0)
            for i in range(3)
        ]
        pitch_x, _ = detect_sheet_pitch(sheets)
        self.assertAlmostEqual(pitch_x, 630_000, delta=100)


class TestSegmentSheets(unittest.TestCase):
    """전체 시트 검출."""

    def test_empty_doc(self):
        doc = ezdxf.new()
        sheets = segment_sheets(doc)
        self.assertEqual(len(sheets), 0)

    def test_single_sheet_with_titleblock_text(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        # 시트 코드 + 격자 라벨 → 1개 시트
        msp.add_text("S30-001", dxfattribs={"insert": (1000, 1000)})
        msp.add_text("X1", dxfattribs={"insert": (0, 0)})
        msp.add_text("X2", dxfattribs={"insert": (10000, 0)})
        msp.add_text("Y1", dxfattribs={"insert": (0, 0)})
        msp.add_text("Y2", dxfattribs={"insert": (0, 10000)})

        sheets = segment_sheets(doc)
        # 최소 1개는 검출되어야 함
        self.assertGreaterEqual(len(sheets), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
