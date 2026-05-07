"""
test_boq_export.py — BOQ 내보내기 단위 테스트
==============================================
TDD RED: 구현 전 실패 테스트.

검증:
  1. JSON 내보내기 (전체 + 집계)
  2. CSV 내보내기 (UTF-8-BOM 헤더, 행 수)
  3. 메타 정보 (project, generated, total_members)
  4. 빈 컬렉션 처리
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline.boq_export import export_boq_csv, export_boq_json
from core.pipeline.member_data import Member, MemberCollection


# ─────────────────────────────────────────────────────────────
# JSON 내보내기
# ─────────────────────────────────────────────────────────────
class TestExportJson(unittest.TestCase):
    def test_json_basic_structure(self):
        coll = _make_sample_collection()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "boq.json"
            export_boq_json(coll, out, project="test_project")

            self.assertTrue(out.exists())
            d = json.loads(out.read_text(encoding="utf-8"))

            # 메타
            self.assertEqual(d["project"], "test_project")
            self.assertEqual(d["total_members"], 5)
            self.assertIn("generated", d)

            # 집계
            self.assertIn("by_type", d)
            self.assertEqual(d["by_type"]["COLUMN"]["count"], 1)
            self.assertEqual(d["by_type"]["BEAM"]["count"], 1)

            # 부재 목록
            self.assertEqual(len(d["members"]), 5)

    def test_json_volume_aggregation(self):
        # COLUMN 2개 (각 1.104 m³) + WALL 1개 (체적 0)
        members = [
            Member(id="C1", type="COLUMN", floor="B2F", source="DONG",
                   x=0, y=0, z_bot=-9050, z_top=-5600,
                   section="400x800", layer="A-COL"),
            Member(id="C2", type="COLUMN", floor="B2F", source="DONG",
                   x=0, y=0, z_bot=-9050, z_top=-5600,
                   section="400x800", layer="A-COL"),
            Member(id="W1", type="WALL", floor="B2F", source="DONG",
                   x=0, y=0, z_bot=-9050, z_top=-5600,
                   length_mm=12000, height_mm=3450, layer="A-WALL-RC"),
        ]
        coll = MemberCollection(members)

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "boq.json"
            export_boq_json(coll, out, project="vol_test")
            d = json.loads(out.read_text(encoding="utf-8"))

            self.assertAlmostEqual(
                d["by_type"]["COLUMN"]["volume_m3"], 2.208, places=2
            )
            self.assertAlmostEqual(
                d["by_type"]["WALL"]["area_m2"], 41.4, places=1
            )

    def test_json_by_floor_aggregation(self):
        members = [
            Member(id="C1", type="COLUMN", floor="B2F", source="DONG",
                   x=0, y=0, z_bot=-9050, z_top=-5600,
                   section="400x800", layer="A-COL"),
            Member(id="C2", type="COLUMN", floor="B1F", source="DONG",
                   x=0, y=0, z_bot=-5600, z_top=370,
                   section="400x800", layer="A-COL"),
        ]
        coll = MemberCollection(members)

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "boq.json"
            export_boq_json(coll, out, project="floor_test")
            d = json.loads(out.read_text(encoding="utf-8"))

            self.assertIn("by_floor", d)
            self.assertEqual(d["by_floor"]["B2F"]["count"], 1)
            self.assertEqual(d["by_floor"]["B1F"]["count"], 1)


# ─────────────────────────────────────────────────────────────
# CSV 내보내기
# ─────────────────────────────────────────────────────────────
class TestExportCsv(unittest.TestCase):
    def test_csv_header_and_rows(self):
        coll = _make_sample_collection()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "boq.csv"
            export_boq_csv(coll, out)

            self.assertTrue(out.exists())
            # UTF-8-BOM 확인
            raw = out.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "BOM 누락")

            # 헤더 + 5행
            with open(out, encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            self.assertEqual(len(rows), 6, "헤더 1행 + 데이터 5행 기대")

            header = rows[0]
            for col in ["부재ID", "유형", "층", "구역"]:
                self.assertIn(col, header)

    def test_csv_data_integrity(self):
        coll = _make_sample_collection()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "boq.csv"
            export_boq_csv(coll, out)

            with open(out, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            ids = [r["부재ID"] for r in rows]
            self.assertEqual(set(ids), {"COL-1", "BM-1", "WL-1", "SL-1", "FND-1"})


# ─────────────────────────────────────────────────────────────
# 빈 컬렉션
# ─────────────────────────────────────────────────────────────
class TestEmptyCollection(unittest.TestCase):
    def test_empty_json(self):
        coll = MemberCollection()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "boq.json"
            export_boq_json(coll, out, project="empty")
            d = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(d["total_members"], 0)
            self.assertEqual(d["members"], [])

    def test_empty_csv(self):
        coll = MemberCollection()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "boq.csv"
            export_boq_csv(coll, out)
            with open(out, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), 1, "헤더만 존재")


# ─────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────
def _make_sample_collection() -> MemberCollection:
    return MemberCollection([
        Member(id="COL-1", type="COLUMN", floor="B2F", source="DONG",
               x=96640.9, y=2374004.3, z_bot=-9050, z_top=-5600,
               section="400x800", layer="A-COL"),
        Member(id="BM-1", type="BEAM", floor="B2F", source="DONG",
               x=106291.3, y=2283477.9, z_bot=-9050, z_top=-5600,
               length_mm=6397.2, angle_deg=104.0, section="400x800",
               layer="S-BEAM"),
        Member(id="WL-1", type="WALL", floor="B2F", source="DONG",
               x=179027.1, y=2260928.2, z_bot=-9050, z_top=-5600,
               length_mm=12249.7, height_mm=3450, layer="A-WALL-RC"),
        Member(id="SL-1", type="SLAB", floor="PKG", source="PKG",
               x=1702307.3, y=-1068590.1, z_bot=-9050, z_top=-5600,
               area_m2=1.306, layer="S-PC-SLAB"),
        Member(id="FND-1", type="FND", floor="B2F", source="DONG",
               x=69202.2, y=2305078.9, z_bot=-10050, z_top=-9050,
               layer="S-FOUNDATION"),
    ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
