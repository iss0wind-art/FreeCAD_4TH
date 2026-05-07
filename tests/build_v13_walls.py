"""
build_v13_walls.py — Track 1-A: WALL 솔리드 생성
==================================================
members_accumulated.json의 WALL 17,057건 → STEP.

실행:
  "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/build_v13_walls.py

산출:
  output/v13_walls.step  — WALL 전수 솔리드
  output/v13_walls_boq.json — 통합 BOQ (WALL만)
"""
from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

# 환경 설정
ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.pipeline.boq_solid_builder import beam_solid, export_step
from core.pipeline.member_data import Member, MemberCollection
from core.pipeline.wall_thickness import estimate_wall_thickness

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

MEMBER_JSON = "output/members_accumulated.json"
STEP_OUT    = "output/v13_walls.step"
BOQ_OUT     = "output/v13_walls.json"

# WALL 길이 필터: 100mm 미만 무시
MIN_WALL_LEN_MM = 100.0


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    print("=" * 60)
    print("v13: WALL 솔리드 빌드 (Track 1-A)")
    print("=" * 60)

    coll = MemberCollection.load_json(MEMBER_JSON)
    walls = coll.filter(type_="WALL")
    print(f"WALL 로드: {len(walls)}건")

    shapes_with_names = []
    failed = 0
    skipped_short = 0

    for w in walls:
        # 길이 필터
        length = float(w.length_mm or 0.0)
        if length < MIN_WALL_LEN_MM:
            skipped_short += 1
            continue

        # 두께 추정
        thickness = estimate_wall_thickness(w.layer)

        # 시작·끝점 계산 (중심 + 길이·각도)
        ang = math.radians(float(w.angle_deg or 0.0))
        x0 = w.x - (length / 2) * math.cos(ang)
        y0 = w.y - (length / 2) * math.sin(ang)
        x1 = w.x + (length / 2) * math.cos(ang)
        y1 = w.y + (length / 2) * math.sin(ang)

        # 보 솔리드 함수 재사용 (벽=두꺼운 보)
        shape = beam_solid(
            x0=x0, y0=y0, x1=x1, y1=y1,
            bw=thickness, bh=thickness,  # bh는 사용 안 함 (높이 zb→zt로)
            zb=float(w.z_bot), zt=float(w.z_top),
        )

        if shape is None:
            failed += 1
            continue

        shapes_with_names.append((shape, w.id))

    print(f"솔리드 생성 성공: {len(shapes_with_names)}개")
    print(f"실패: {failed}개 / 짧음 스킵: {skipped_short}개")

    # STEP 내보내기
    print(f"STEP 저장 중: {STEP_OUT} ...")
    export_step(shapes_with_names, STEP_OUT)
    size_mb = Path(STEP_OUT).stat().st_size / 1024 / 1024
    print(f"STEP 저장: {STEP_OUT} ({size_mb:.1f} MB)")

    # 두께 보강해서 WALL volume 다시 계산
    enriched = []
    for w in walls:
        length = float(w.length_mm or 0.0)
        if length < MIN_WALL_LEN_MM:
            continue
        thickness = estimate_wall_thickness(w.layer)
        height = w.height_mm if w.height_mm else w.height_z_mm
        vol_m3 = (length / 1000.0) * (thickness / 1000.0) * (height / 1000.0)
        enriched.append({
            "id": w.id, "type": "WALL", "floor": w.floor, "source": w.source,
            "length_mm": length, "thickness_mm": thickness, "height_mm": height,
            "volume_m3": round(vol_m3, 4), "layer": w.layer,
        })

    import json
    total_vol = sum(e["volume_m3"] for e in enriched)
    out = {
        "generated": __import__('datetime').datetime.now().isoformat(timespec="seconds"),
        "total_count": len(enriched),
        "total_volume_m3": round(total_vol, 2),
        "skipped_short": skipped_short,
        "failed_solid": failed,
        "walls": enriched,
    }
    with open(BOQ_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"BOQ 저장: {BOQ_OUT}")
    print(f"  총 WALL: {len(enriched)}건, 체적 합계: {total_vol:.2f} m³")
    print(f"  소요 시간: {time.time()-t0:.1f}s")


# freecadcmd는 __name__을 파일명으로 설정하므로 직접 호출
main()
