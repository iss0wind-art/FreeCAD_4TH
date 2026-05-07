"""
test_member_data.py — Member 데이터클래스 단위 테스트
======================================================
TDD RED 단계: 구현 전 실패 테스트.

검증 항목:
  1. Member 생성 (5종 타입)
  2. to_dict / from_dict 라운드트립
  3. members_accumulated.json 실데이터 로드
  4. 체적·면적 계산 (COLUMN/BEAM/WALL)
  5. 타입 검증 (잘못된 type 거부)
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline.member_data import Member, VALID_TYPES, MemberCollection


# ─────────────────────────────────────────────────────────────
# 1. Member 생성
# ─────────────────────────────────────────────────────────────
class TestMemberCreation(unittest.TestCase):
    """Member 인스턴스 생성 — 5종 타입 모두."""

    def test_create_column(self):
        m = Member(
            id="COL-B2F-0001", type="COLUMN", floor="B2F", source="DONG",
            x=96640.9, y=2374004.3, z_bot=-9050, z_top=-5600,
            section="400x800", layer="A-COL",
        )
        self.assertEqual(m.type, "COLUMN")
        self.assertEqual(m.section, "400x800")
        self.assertEqual(m.height_mm, 3450)  # z_top - z_bot

    def test_create_beam(self):
        m = Member(
            id="BM-B2F-0001", type="BEAM", floor="B2F", source="DONG",
            x=106291.3, y=2283477.9, z_bot=-9050, z_top=-5600,
            length_mm=6397.2, angle_deg=104.0, layer="S-BEAM",
        )
        self.assertEqual(m.type, "BEAM")
        self.assertAlmostEqual(m.length_mm, 6397.2, places=1)

    def test_create_wall(self):
        m = Member(
            id="WL-B2F-0001", type="WALL", floor="B2F", source="DONG",
            x=179027.1, y=2260928.2, z_bot=-9050, z_top=-5600,
            length_mm=12249.7, height_mm=3450, angle_deg=104.0,
            layer="A-WALL-RC",
        )
        self.assertEqual(m.type, "WALL")

    def test_create_slab(self):
        m = Member(
            id="SL-PKG-0001", type="SLAB", floor="PKG", source="PKG",
            x=1702307.3, y=-1068590.1, z_bot=-9050, z_top=-5600,
            area_m2=1.306, layer="S-PC-SLAB",
        )
        self.assertEqual(m.type, "SLAB")
        self.assertAlmostEqual(m.area_m2, 1.306, places=3)

    def test_create_fnd(self):
        m = Member(
            id="FND-B2F-0001", type="FND", floor="B2F", source="DONG",
            x=69202.2, y=2305078.9, z_bot=-10050, z_top=-9050,
            layer="S-FOUNDATION",
        )
        self.assertEqual(m.type, "FND")

    def test_invalid_type_rejected(self):
        with self.assertRaises(ValueError):
            Member(
                id="X-0001", type="INVALID_TYPE", floor="B2F", source="DONG",
                x=0, y=0, z_bot=0, z_top=1, layer="X",
            )


# ─────────────────────────────────────────────────────────────
# 2. to_dict / from_dict 라운드트립
# ─────────────────────────────────────────────────────────────
class TestMemberRoundtrip(unittest.TestCase):
    """to_dict() → from_dict() 결과가 원본과 같은지."""

    def test_roundtrip_column(self):
        original = Member(
            id="COL-B2F-0001", type="COLUMN", floor="B2F", source="DONG",
            x=96640.9, y=2374004.3, z_bot=-9050, z_top=-5600,
            section="400x800", layer="A-COL",
        )
        d = original.to_dict()
        restored = Member.from_dict(d)
        self.assertEqual(original, restored)

    def test_roundtrip_all_types(self):
        for sample in _make_samples():
            d = sample.to_dict()
            restored = Member.from_dict(d)
            self.assertEqual(sample, restored, f"roundtrip 실패: {sample.id}")


# ─────────────────────────────────────────────────────────────
# 3. 실 데이터 로드
# ─────────────────────────────────────────────────────────────
class TestLoadAccumulated(unittest.TestCase):
    """members_accumulated.json 실데이터 로드."""

    def test_load_real_json(self):
        path = ROOT / "output" / "members_accumulated.json"
        if not path.exists():
            self.skipTest(f"실데이터 없음: {path}")

        coll = MemberCollection.load_json(path)
        self.assertGreater(len(coll), 20000, "25,219건 기대")

        # 5종 타입 모두 존재
        type_counts = coll.count_by_type()
        for t in ["COLUMN", "BEAM", "WALL", "SLAB", "FND"]:
            self.assertIn(t, type_counts, f"{t} 누락")
            self.assertGreater(type_counts[t], 0, f"{t} count=0")


# ─────────────────────────────────────────────────────────────
# 4. 체적 / 면적 계산
# ─────────────────────────────────────────────────────────────
class TestVolumeCalculation(unittest.TestCase):
    """COLUMN·BEAM·WALL 체적 계산."""

    def test_column_volume(self):
        # 400x800 단면, 높이 3450 → 0.4*0.8*3.45 = 1.104 m³
        m = Member(
            id="COL-1", type="COLUMN", floor="B2F", source="DONG",
            x=0, y=0, z_bot=-9050, z_top=-5600,
            section="400x800", layer="A-COL",
        )
        self.assertAlmostEqual(m.volume_m3(), 1.104, places=3)

    def test_beam_volume_with_section(self):
        # 길이 6000mm, 단면 400x800 → 6.0 * 0.4 * 0.8 = 1.92 m³
        m = Member(
            id="BM-1", type="BEAM", floor="B2F", source="DONG",
            x=0, y=0, z_bot=-9050, z_top=-5600,
            length_mm=6000, angle_deg=0, section="400x800", layer="S-BEAM",
        )
        self.assertAlmostEqual(m.volume_m3(), 1.92, places=2)

    def test_wall_area(self):
        # 길이 12000, 높이 3450 → 12.0 * 3.45 = 41.4 m²
        m = Member(
            id="WL-1", type="WALL", floor="B2F", source="DONG",
            x=0, y=0, z_bot=-9050, z_top=-5600,
            length_mm=12000, height_mm=3450, angle_deg=0, layer="A-WALL-RC",
        )
        self.assertAlmostEqual(m.area_value_m2(), 41.4, places=1)

    def test_slab_area_passthrough(self):
        m = Member(
            id="SL-1", type="SLAB", floor="PKG", source="PKG",
            x=0, y=0, z_bot=-9050, z_top=-5600,
            area_m2=1.306, layer="S-PC-SLAB",
        )
        self.assertAlmostEqual(m.area_value_m2(), 1.306, places=3)


# ─────────────────────────────────────────────────────────────
# 5. MemberCollection 집계
# ─────────────────────────────────────────────────────────────
class TestMemberCollection(unittest.TestCase):
    """타입별·층별 집계."""

    def test_count_by_type(self):
        members = _make_samples()
        coll = MemberCollection(members)
        counts = coll.count_by_type()
        # 5종 1개씩
        for t in ["COLUMN", "BEAM", "WALL", "SLAB", "FND"]:
            self.assertEqual(counts[t], 1)

    def test_total_volume_by_type(self):
        members = [
            Member(id="C-1", type="COLUMN", floor="B2F", source="DONG",
                   x=0, y=0, z_bot=-9050, z_top=-5600,
                   section="400x800", layer="A-COL"),
            Member(id="C-2", type="COLUMN", floor="B2F", source="DONG",
                   x=0, y=0, z_bot=-9050, z_top=-5600,
                   section="400x800", layer="A-COL"),
        ]
        coll = MemberCollection(members)
        vol = coll.total_volume_m3("COLUMN")
        self.assertAlmostEqual(vol, 1.104 * 2, places=3)


# ─────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────
def _make_samples():
    return [
        Member(id="COL-1", type="COLUMN", floor="B2F", source="DONG",
               x=96640.9, y=2374004.3, z_bot=-9050, z_top=-5600,
               section="400x800", layer="A-COL"),
        Member(id="BM-1", type="BEAM", floor="B2F", source="DONG",
               x=106291.3, y=2283477.9, z_bot=-9050, z_top=-5600,
               length_mm=6397.2, angle_deg=104.0, layer="S-BEAM"),
        Member(id="WL-1", type="WALL", floor="B2F", source="DONG",
               x=179027.1, y=2260928.2, z_bot=-9050, z_top=-5600,
               length_mm=12249.7, height_mm=3450, angle_deg=104.0,
               layer="A-WALL-RC"),
        Member(id="SL-1", type="SLAB", floor="PKG", source="PKG",
               x=1702307.3, y=-1068590.1, z_bot=-9050, z_top=-5600,
               area_m2=1.306, layer="S-PC-SLAB"),
        Member(id="FND-1", type="FND", floor="B2F", source="DONG",
               x=69202.2, y=2305078.9, z_bot=-10050, z_top=-9050,
               layer="S-FOUNDATION"),
    ]


if __name__ == "__main__":
    unittest.main(verbosity=2)
