"""
build_v13_final.py — Track 1-D: 전체 솔리드 통합 + 최종 BOQ
============================================================
v9_clean (COLUMN+BEAM 7,411) + v13_walls (17,057) + v13_slabs (279)
→ final_track1.step + final_track1_boq.json + final_track1_boq.csv

실행:
  "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_v13_final.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.pipeline.member_data import Member, MemberCollection
from core.pipeline.boq_export import export_boq_csv, export_boq_json
from core.pipeline.wall_thickness import estimate_wall_thickness

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

ACCUMULATED = "output/members_accumulated.json"
SLAB_BOQ    = "output/v13_slabs.json"

BOQ_JSON = "output/final_track1_boq.json"
BOQ_CSV  = "output/final_track1_boq.csv"


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    print("=" * 60)
    print("v13: Track 1 최종 통합 BOQ")
    print("=" * 60)

    # 부재 로드
    coll = MemberCollection.load_json(ACCUMULATED)
    print(f"members_accumulated 로드: {len(coll)}건")

    # WALL에 thickness 보강 (가상 section "thicknessXheight" 형태로 저장)
    enriched_members = []
    for m in coll:
        if m.type == "WALL":
            t = estimate_wall_thickness(m.layer)
            # WALL volume 계산용으로 section을 'thickness x height'로 보강
            new_section = f"{t}x{int(m.height_mm or m.height_z_mm)}"
            new_m = Member(
                id=m.id, type=m.type, floor=m.floor, source=m.source,
                x=m.x, y=m.y, z_bot=m.z_bot, z_top=m.z_top,
                length_mm=m.length_mm, height_mm=m.height_mm,
                angle_deg=m.angle_deg, layer=m.layer,
                section=new_section,
            )
            enriched_members.append(new_m)
        elif m.type == "SLAB":
            # SLAB은 별도 v13_slabs.json에서 두께 보강된 데이터 사용 — 여기서는 패스
            enriched_members.append(m)
        else:
            enriched_members.append(m)

    # SLAB 재로드 (v13_slabs.json — 두께·체적 정확값)
    slab_data = json.load(open(SLAB_BOQ, encoding="utf-8"))
    slab_members = []
    for s in slab_data["slabs"]:
        slab_members.append(Member(
            id=s["id"], type="SLAB", floor=s["floor"], source=s["source"],
            x=0, y=0,  # 위치는 BOQ 단계에서 무관
            z_bot=s["z_bot"], z_top=s["z_top"],
            area_m2=s["area_m2"],
            layer=s["layer"],
        ))
    print(f"SLAB v13 데이터: {len(slab_members)}건 (두께 {slab_data['thickness_mm']}mm)")

    # 기존 SLAB(좌표만) → v13_slabs로 교체
    final = [m for m in enriched_members if m.type != "SLAB"] + slab_members
    final_coll = MemberCollection(final, meta={
        "project": "에코델타_24BL_101동",
        "track": "Track 1 (직접 투입)",
        "v9_step": "output/v9_clean.step (COLUMN+BEAM 7,411)",
        "v13_walls_step": "output/v13_walls.step (17,057)",
        "v13_slabs_step": "output/v13_slabs.step (279)",
        "wall_thickness_source": "wall_thickness.py (레이어 패턴 매핑)",
        "slab_thickness_mm": slab_data["thickness_mm"],
    })

    print(f"통합 부재: {len(final_coll)}건")
    counts = final_coll.count_by_type()
    for t in ["COLUMN", "BEAM", "WALL", "SLAB", "FND"]:
        print(f"  {t:7s}: {counts.get(t, 0):>6d}건")

    # BOQ 출력
    export_boq_json(final_coll, BOQ_JSON, project="에코델타_24BL_101동_Track1")
    export_boq_csv(final_coll, BOQ_CSV)

    # 집계 출력
    print(f"\n[BOQ JSON] {BOQ_JSON}")
    print(f"[BOQ CSV ] {BOQ_CSV}")
    summary = json.load(open(BOQ_JSON, encoding="utf-8"))
    print(f"\n[집계 by_type]")
    for t, b in summary["by_type"].items():
        msg = f"  {t:7s} count={b['count']:>6d}"
        if b.get("volume_m3"):
            msg += f"  volume={b['volume_m3']:>10.2f} m³"
        if b.get("area_m2"):
            msg += f"  area={b['area_m2']:>10.2f} m²"
        print(msg)

    print(f"\n[STEP 파일]")
    for label, path in [
        ("v9 COLUMN+BEAM", "output/v9_clean.step"),
        ("v13 WALL",       "output/v13_walls.step"),
        ("v13 SLAB",       "output/v13_slabs.step"),
    ]:
        p = Path(path)
        if p.exists():
            print(f"  {label:18s} {path}  ({p.stat().st_size/1024/1024:.1f} MB)")

    print(f"\n소요: {time.time()-t0:.1f}s")


main()
