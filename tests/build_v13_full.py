"""
build_v13_full.py — 전체 영역 풀빌드
======================================
DONG B1F+B2F + PKG B1F+B2F 모든 부재 (필터 없음).

산출:
  output/v13_full.step  — 전체 솔리드 통합 STEP

실행:
  "C:/Program Files/FreeCAD 1.1/bin/FreeCAD.exe" output/v13_full.step  (시연)
  "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_v13_full.py  (빌드)
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import FreeCAD
import Part

from core.pipeline.boq_solid_builder import beam_solid, box_solid, prism_solid
from core.pipeline.member_data import MemberCollection
from core.pipeline.wall_thickness import estimate_wall_thickness

ACCUMULATED = "output/members_accumulated.json"
SLAB_BOQ    = "output/v13_slabs.json"
COORD_CFG   = "output/coord_config.json"
FULL_STEP   = "output/v13_full.step"


def main():
    t0 = time.time()
    print("=" * 60)
    print("v13 FULL: 전체 영역 통합 STEP")
    print("=" * 60)

    coll = MemberCollection.load_json(ACCUMULATED)
    print(f"부재 로드: {len(coll)}건")
    print(f"  타입별: {coll.count_by_type()}")
    print(f"  층별:   {coll.count_by_floor()}")

    # PKG 좌표 변환 오프셋
    cfg = json.load(open(COORD_CFG, encoding="utf-8"))
    TX_PKG = float(cfg["TX_PKG"])
    TY_PKG = float(cfg["TY_PKG"])
    print(f"PKG 오프셋: TX={TX_PKG}, TY={TY_PKG}")

    doc = FreeCAD.newDocument("V13Full")

    def transform_xy(m):
        """PKG 부재면 좌표 변환."""
        if m.source == "PKG":
            return m.x + TX_PKG, m.y + TY_PKG
        return m.x, m.y

    # ── COLUMN ─────────────────────────────────────────────
    n_col = 0
    for m in coll.filter(type_="COLUMN"):
        sec = m.parse_section()
        if sec is None:
            continue
        w, h = sec
        x, y = transform_xy(m)
        s = box_solid(x, y, m.z_bot, m.z_top, w, h)
        if s is None:
            continue
        obj = doc.addObject("Part::Feature", m.id)
        obj.Shape = s
        n_col += 1
    print(f"COLUMN 솔리드: {n_col}개")

    # ── BEAM ───────────────────────────────────────────────
    n_beam = 0
    for m in coll.filter(type_="BEAM"):
        length = float(m.length_mm or 0)
        if length < 100:
            continue
        ang = math.radians(float(m.angle_deg or 0))
        cx, cy = transform_xy(m)
        x0 = cx - length / 2 * math.cos(ang)
        y0 = cy - length / 2 * math.sin(ang)
        x1 = cx + length / 2 * math.cos(ang)
        y1 = cy + length / 2 * math.sin(ang)
        bw, bh = 400, 800
        sec = m.parse_section()
        if sec:
            bw, bh = sec
        s = beam_solid(x0, y0, x1, y1, bw=bw, bh=bh,
                       zb=m.z_top - bh, zt=m.z_top)
        if s is None:
            continue
        obj = doc.addObject("Part::Feature", m.id)
        obj.Shape = s
        n_beam += 1
    print(f"BEAM 솔리드: {n_beam}개")

    # ── WALL ───────────────────────────────────────────────
    n_wall = 0
    for m in coll.filter(type_="WALL"):
        length = float(m.length_mm or 0)
        if length < 100:
            continue
        thickness = estimate_wall_thickness(m.layer)
        ang = math.radians(float(m.angle_deg or 0))
        cx, cy = transform_xy(m)
        x0 = cx - length / 2 * math.cos(ang)
        y0 = cy - length / 2 * math.sin(ang)
        x1 = cx + length / 2 * math.cos(ang)
        y1 = cy + length / 2 * math.sin(ang)
        s = beam_solid(x0, y0, x1, y1, bw=thickness, bh=thickness,
                       zb=m.z_bot, zt=m.z_top)
        if s is None:
            continue
        obj = doc.addObject("Part::Feature", m.id)
        obj.Shape = s
        n_wall += 1
    print(f"WALL 솔리드: {n_wall}개")

    # ── SLAB (PKG, v13_slabs.json 활용) ───────────────────
    n_slab = 0
    if Path(SLAB_BOQ).exists():
        # SLAB 폴리곤은 v13_slabs.step에서 가져오는 게 정확
        # 여기서는 v13_slabs.step을 별도 import
        try:
            slab_shapes = Part.read("output/v13_slabs.step")
            for i, s in enumerate(slab_shapes.Solids, 1):
                obj = doc.addObject("Part::Feature", f"SL-PKG-{i:04d}")
                obj.Shape = s
                n_slab += 1
            print(f"SLAB 솔리드: {n_slab}개 (v13_slabs.step에서 import)")
        except Exception as e:
            print(f"SLAB import 실패: {e}")

    doc.recompute()
    total = len(doc.Objects)
    print(f"\n총 솔리드: {total}개")

    # 통합 STEP 저장
    print(f"STEP 저장 중: {FULL_STEP}")
    Part.export([o for o in doc.Objects], str(FULL_STEP))
    size_mb = Path(FULL_STEP).stat().st_size / 1024 / 1024
    print(f"STEP 저장: {FULL_STEP} ({size_mb:.1f} MB)")

    # BBox
    all_shapes = [o.Shape for o in doc.Objects if hasattr(o, "Shape") and o.Shape]
    if all_shapes:
        compound = Part.makeCompound(all_shapes)
        bbox = compound.BoundBox
        print(f"\nBBox:")
        print(f"  X: [{bbox.XMin:.0f}, {bbox.XMax:.0f}]  ({bbox.XLength/1000:.1f}m)")
        print(f"  Y: [{bbox.YMin:.0f}, {bbox.YMax:.0f}]  ({bbox.YLength/1000:.1f}m)")
        print(f"  Z: [{bbox.ZMin:.0f}, {bbox.ZMax:.0f}]  ({bbox.ZLength/1000:.2f}m)")

    FreeCAD.closeDocument(doc.Name)
    print(f"\n소요: {time.time()-t0:.1f}s")


main()
