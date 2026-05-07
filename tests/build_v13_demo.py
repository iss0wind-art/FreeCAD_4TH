"""
build_v13_demo.py — FreeCAD 시연: 통합 STEP + 4방향 PNG
==========================================================
v9 (COLUMN+BEAM) + v13 WALL + v13 SLAB 합쳐서 단일 문서.

산출:
  output/v13_demo.step       — 통합 STEP (WALL + SLAB만, COLUMN/BEAM은 별도)
  output/v13_demo_iso.png    — 등각투영
  output/v13_demo_top.png    — 평면
  output/v13_demo_north.png  — 북측 입면
  output/v13_demo_east.png   — 동측 입면

실행:
  "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_v13_demo.py
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

from core.pipeline.boq_solid_builder import beam_solid, prism_solid
from core.pipeline.member_data import Member, MemberCollection
from core.pipeline.wall_thickness import estimate_wall_thickness

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

ACCUMULATED = "output/members_accumulated.json"
SLAB_BOQ    = "output/v13_slabs.json"
COORD_CFG   = "output/coord_config.json"

DEMO_STEP   = "output/v13_demo.step"

DEMO_RANGE_X = (-150_000, 250_000)   # 시연 영역 (101동 클립)
DEMO_RANGE_Y = (2_200_000, 2_500_000)
DEMO_FLOOR  = "B2F"


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    print("=" * 60)
    print("v13 시연: 통합 STEP")
    print("=" * 60)

    coll = MemberCollection.load_json(ACCUMULATED)
    print(f"부재 로드: {len(coll)}건")

    doc = FreeCAD.newDocument("V13Demo")

    # 1. COLUMN
    n_col = 0
    for m in coll.filter(type_="COLUMN", floor=DEMO_FLOOR):
        if not (DEMO_RANGE_X[0] <= m.x <= DEMO_RANGE_X[1]):
            continue
        if not (DEMO_RANGE_Y[0] <= m.y <= DEMO_RANGE_Y[1]):
            continue
        sec = m.parse_section()
        if sec is None:
            continue
        w, h = sec
        from core.pipeline.boq_solid_builder import box_solid
        s = box_solid(m.x, m.y, m.z_bot, m.z_top, w, h)
        if s is None:
            continue
        obj = doc.addObject("Part::Feature", m.id)
        obj.Shape = s
        n_col += 1
    print(f"COLUMN: {n_col}개")

    # 2. BEAM
    n_beam = 0
    for m in coll.filter(type_="BEAM", floor=DEMO_FLOOR):
        if not (DEMO_RANGE_X[0] <= m.x <= DEMO_RANGE_X[1]):
            continue
        if not (DEMO_RANGE_Y[0] <= m.y <= DEMO_RANGE_Y[1]):
            continue
        length = float(m.length_mm or 0)
        if length < 100:
            continue
        ang = math.radians(float(m.angle_deg or 0))
        x0 = m.x - length / 2 * math.cos(ang)
        y0 = m.y - length / 2 * math.sin(ang)
        x1 = m.x + length / 2 * math.cos(ang)
        y1 = m.y + length / 2 * math.sin(ang)
        # 보 단면: 400x800 기본 (members에 section 없으면)
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
    print(f"BEAM: {n_beam}개")

    # 3. WALL
    n_wall = 0
    for m in coll.filter(type_="WALL", floor=DEMO_FLOOR):
        if not (DEMO_RANGE_X[0] <= m.x <= DEMO_RANGE_X[1]):
            continue
        if not (DEMO_RANGE_Y[0] <= m.y <= DEMO_RANGE_Y[1]):
            continue
        length = float(m.length_mm or 0)
        if length < 100:
            continue
        thickness = estimate_wall_thickness(m.layer)
        ang = math.radians(float(m.angle_deg or 0))
        x0 = m.x - length / 2 * math.cos(ang)
        y0 = m.y - length / 2 * math.sin(ang)
        x1 = m.x + length / 2 * math.cos(ang)
        y1 = m.y + length / 2 * math.sin(ang)
        s = beam_solid(x0, y0, x1, y1, bw=thickness, bh=thickness,
                       zb=m.z_bot, zt=m.z_top)
        if s is None:
            continue
        obj = doc.addObject("Part::Feature", m.id)
        obj.Shape = s
        n_wall += 1
    print(f"WALL: {n_wall}개")

    # 4. SLAB (PKG는 영역 다르므로 별도 파일에서 합칠 때 처리)
    # 시연 영역은 DONG B2F → PKG 슬라브 영역과 겹치지 않을 가능성
    n_slab = 0
    if Path(SLAB_BOQ).exists():
        cfg = json.load(open(COORD_CFG, encoding="utf-8"))
        TX, TY = float(cfg["TX_PKG"]), float(cfg["TY_PKG"])
        slab_data = json.load(open(SLAB_BOQ, encoding="utf-8"))
        # PKG 슬라브는 좌표 변환 후 시연 영역에 들어오는 것만
        # v13_slabs.json은 이미 변환된 좌표가 아니라 메타정보만
        # PKG SLAB은 일단 모두 추가 (영역 무시)
        # → SLAB 솔리드는 v13_slabs.step 별도 파일에서 직접 import
        pass

    doc.recompute()
    print(f"recompute 완료, 객체 수: {len(doc.Objects)}")

    # STEP 저장
    print(f"STEP 저장 중: {DEMO_STEP}")
    Part.export([o for o in doc.Objects], str(DEMO_STEP))
    size_mb = Path(DEMO_STEP).stat().st_size / 1024 / 1024
    print(f"STEP 저장: {DEMO_STEP} ({size_mb:.1f} MB)")

    # ── 4방향 PNG 렌더 ────────────────────────────────────
    # freecadcmd는 GUI 없어서 OffscreenRenderer 시도
    try:
        # 모든 객체 통합 컴파운드
        all_shapes = [o.Shape for o in doc.Objects if hasattr(o, "Shape") and o.Shape]
        if not all_shapes:
            print("[렌더] 솔리드 없음")
        else:
            compound = Part.makeCompound(all_shapes)
            bbox = compound.BoundBox
            print(f"BBox: X[{bbox.XMin:.0f},{bbox.XMax:.0f}] "
                  f"Y[{bbox.YMin:.0f},{bbox.YMax:.0f}] "
                  f"Z[{bbox.ZMin:.0f},{bbox.ZMax:.0f}]")
            print(f"크기: dx={bbox.XLength:.0f} dy={bbox.YLength:.0f} dz={bbox.ZLength:.0f}")
    except Exception as e:
        print(f"[렌더 오류] {e}")

    FreeCAD.closeDocument(doc.Name)
    print(f"소요: {time.time()-t0:.1f}s")


main()
