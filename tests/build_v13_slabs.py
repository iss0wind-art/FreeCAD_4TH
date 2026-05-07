"""
build_v13_slabs.py — Track 1-B: PKG SLAB 솔리드 생성
======================================================
PKG DXF에서 S-PC-SLAB LWPOLYLINE 직접 추출 → 솔리드.

[처리]
  1. DXF S-PC-SLAB 폴리라인 읽기
  2. self-crossing(나비넥타이) 폴리곤 → 각도 정렬로 보정
  3. coord_config 좌표 변환 (TX, TY 적용)
  4. extrude 솔리드 (두께 150mm 기본)

실행:
  "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_v13_slabs.py

산출:
  output/v13_slabs.step
  output/v13_slabs.json
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ezdxf
from core.pipeline.boq_solid_builder import export_step, prism_solid

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

DXF_PKG = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
COORD_CONFIG = "output/coord_config.json"
STEP_OUT = "output/v13_slabs.step"
BOQ_OUT  = "output/v13_slabs.json"

SLAB_THICKNESS_MM = 150  # PC 슬라브 표준 두께
SLAB_LAYER = "S-PC-SLAB"

# B2F 클립 영역 (members_accumulated.json SLAB 좌표 범위 기반)
PKG_B2F_CLIP = {"xmin": 1100000, "xmax": 1900000, "ymin": -1320000, "ymax": -1020000}


# ─────────────────────────────────────────────────────────────
# self-crossing 폴리곤 보정 (member-agent 로직 재현)
# ─────────────────────────────────────────────────────────────

def shoelace_area(pts):
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def reorder_by_angle(pts):
    """중심 기준 각도 정렬로 self-crossing 보정."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def in_clip(x, y, clip):
    return clip["xmin"] <= x <= clip["xmax"] and clip["ymin"] <= y <= clip["ymax"]


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    print("=" * 60)
    print("v13: PKG SLAB 솔리드 빌드 (Track 1-B)")
    print("=" * 60)

    # 좌표 오프셋
    cfg = json.load(open(COORD_CONFIG, encoding="utf-8"))
    TX, TY = float(cfg["TX_PKG"]), float(cfg["TY_PKG"])
    print(f"좌표 변환: TX={TX}, TY={TY}")

    # DXF 로드
    print(f"DXF 로드: {DXF_PKG}")
    doc = ezdxf.readfile(DXF_PKG)
    msp = doc.modelspace()

    # SLAB 추출
    slabs_raw = []
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer != SLAB_LAYER:
            continue
        pts = [(p[0], p[1]) for p in e.get_points()]
        if len(pts) < 3:
            continue
        # 클립 필터 (B2F 영역)
        cx_avg = sum(p[0] for p in pts) / len(pts)
        cy_avg = sum(p[1] for p in pts) / len(pts)
        if not in_clip(cx_avg, cy_avg, PKG_B2F_CLIP):
            continue
        slabs_raw.append(pts)

    print(f"S-PC-SLAB LWPOLYLINE 추출: {len(slabs_raw)}개 (B2F 클립 내)")

    # 좌표 변환 + self-crossing 보정 + 솔리드 생성
    z_bot = -9050 - SLAB_THICKNESS_MM  # 슬라브 하면
    z_top = -9050                       # 슬라브 상면 (B2F SL)

    shapes_with_names = []
    enriched = []
    failed = 0

    for idx, raw_pts in enumerate(slabs_raw, 1):
        # 좌표 변환
        pts = [(x + TX, y + TY) for x, y in raw_pts]

        # self-crossing 보정 (Shoelace 0이면 reorder)
        area_before = shoelace_area(pts)
        if area_before < 1.0:  # mm² 단위, 비정상
            pts = reorder_by_angle(pts)
            area_after = shoelace_area(pts)
        else:
            area_after = area_before

        area_m2 = area_after / 1_000_000.0  # mm² → m²

        # 솔리드 생성
        shape = prism_solid(pts, zb=z_bot, zt=z_top)
        slab_id = f"SL-PKG-B2F-{idx:04d}"

        if shape is None:
            failed += 1
            continue

        shapes_with_names.append((shape, slab_id))

        vol_m3 = area_m2 * (SLAB_THICKNESS_MM / 1000.0)
        enriched.append({
            "id": slab_id, "type": "SLAB", "floor": "B2F", "source": "PKG",
            "area_m2": round(area_m2, 4),
            "thickness_mm": SLAB_THICKNESS_MM,
            "volume_m3": round(vol_m3, 4),
            "z_bot": z_bot, "z_top": z_top,
            "layer": SLAB_LAYER,
        })

    print(f"솔리드 성공: {len(shapes_with_names)} / 실패: {failed}")

    # STEP 내보내기
    print(f"STEP 저장 중: {STEP_OUT} ...")
    export_step(shapes_with_names, STEP_OUT)
    size_mb = Path(STEP_OUT).stat().st_size / 1024 / 1024
    print(f"STEP 저장: {STEP_OUT} ({size_mb:.1f} MB)")

    # BOQ
    total_area = sum(e["area_m2"] for e in enriched)
    total_vol = sum(e["volume_m3"] for e in enriched)
    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "total_count": len(enriched),
        "total_area_m2": round(total_area, 2),
        "total_volume_m3": round(total_vol, 2),
        "thickness_mm": SLAB_THICKNESS_MM,
        "failed_solid": failed,
        "slabs": enriched,
    }
    with open(BOQ_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"BOQ 저장: {BOQ_OUT}")
    print(f"  총 SLAB: {len(enriched)}건, 면적: {total_area:.2f} m², 체적: {total_vol:.2f} m³")
    print(f"  소요 시간: {time.time()-t0:.1f}s")


# freecadcmd 호환
main()
