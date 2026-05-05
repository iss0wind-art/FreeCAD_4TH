"""
BOQ 수량산출 — 101동 기준층 STEP 모델 분석
test_dxf_to_freecad.py로 생성된 STEP을 읽어 부재별 체적·면적 산출.

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_boq_calculation.py
"""

import os
import json
from datetime import datetime

import FreeCAD
import Part

STEP_PATH = "output/test_101dong.step"
OUT_JSON  = "output/boq_101dong.json"
OUT_MD    = "output/boq_101dong.md"

WALL_THICKNESS = 210
SLAB_THICKNESS = 210
FLOOR_HEIGHT   = 2830
WALL_HEIGHT    = FLOOR_HEIGHT - SLAB_THICKNESS  # 2620

# ── 1. STEP 로드 ─────────────────────────────────────────────
print(f"[로드] {STEP_PATH}")
shape = Part.Shape()
shape.read(STEP_PATH)
solids = shape.Solids
print(f"[로드] 솔리드 {len(solids)}개")

# ── 2. 부재 분류 (높이 기준) ──────────────────────────────────
walls = []
slabs = []
for sld in solids:
    bbox = sld.BoundBox
    z_min = bbox.ZMin
    z_max = bbox.ZMax
    height = z_max - z_min
    # 슬라브: Z범위가 SLAB_BOTTOM_Z 위에 있고 두께가 SLAB_THICKNESS
    if abs(height - SLAB_THICKNESS) < 5 and z_min > 1000:
        slabs.append(sld)
    elif abs(height - WALL_HEIGHT) < 5 and z_min < 5:
        walls.append(sld)
    else:
        # 알 수 없음 → 두께로 분류
        if height < 500:
            slabs.append(sld)
        else:
            walls.append(sld)

print(f"[분류] 벽체 {len(walls)}개 / 슬라브 {len(slabs)}개")

# ── 3. 거푸집 면적 추출 (수직 면만) ───────────────────────────
def vertical_face_area(solid):
    """Z축에 수직인 면(측면)만 합산 → 거푸집 면적 근사"""
    total = 0
    for face in solid.Faces:
        try:
            normal = face.normalAt(0.5, 0.5)
            # |Nz| < 0.1이면 수직 측면
            if abs(normal.z) < 0.1:
                total += face.Area
        except Exception:
            continue
    return total

def bottom_face_area(solid):
    """Z- 방향 바닥면 (슬라브 거푸집 밑판)"""
    total = 0
    for face in solid.Faces:
        try:
            normal = face.normalAt(0.5, 0.5)
            if normal.z < -0.9:
                total += face.Area
        except Exception:
            continue
    return total

# ── 4. 수량 집계 ─────────────────────────────────────────────
def summarize(name, solids_list, formwork_includes_bottom):
    total_vol = sum(s.Volume for s in solids_list) / 1e9       # mm³ → m³
    side_area = sum(vertical_face_area(s) for s in solids_list) / 1e6  # mm² → m²
    bot_area = sum(bottom_face_area(s) for s in solids_list) / 1e6
    formwork = side_area + (bot_area if formwork_includes_bottom else 0)
    return {
        "부재": name,
        "수량": len(solids_list),
        "콘크리트체적_m3": round(total_vol, 3),
        "측면적_m2": round(side_area, 2),
        "바닥면적_m2": round(bot_area, 2),
        "거푸집면적_m2": round(formwork, 2),
    }

wall_boq = summarize("RC 벽체", walls, formwork_includes_bottom=False)
slab_boq = summarize("RC 슬라브", slabs, formwork_includes_bottom=True)

total_vol = wall_boq["콘크리트체적_m3"] + slab_boq["콘크리트체적_m3"]
total_form = wall_boq["거푸집면적_m2"] + slab_boq["거푸집면적_m2"]

# ── 5. 출력 ─────────────────────────────────────────────────
print("\n" + "=" * 50)
print("BOQ 수량산출 결과 - 101동 기준층")
print("=" * 50)
print(f"{'부재':12s} {'수량':>5s} {'체적(m³)':>10s} {'거푸집(m²)':>12s}")
print("-" * 50)
for b in [wall_boq, slab_boq]:
    print(f"{b['부재']:12s} {b['수량']:>5d} {b['콘크리트체적_m3']:>10.3f} {b['거푸집면적_m2']:>12.2f}")
print("-" * 50)
print(f"{'합계':12s} {len(walls)+len(slabs):>5d} {total_vol:>10.3f} {total_form:>12.2f}")
print("=" * 50)

# ── 6. JSON / Markdown 저장 ──────────────────────────────────
result = {
    "프로젝트": "101동 기준층 (free_test.dxf)",
    "산출일시": datetime.now().isoformat(timespec='seconds'),
    "파라미터": {
        "벽체두께_mm": WALL_THICKNESS,
        "슬라브두께_mm": SLAB_THICKNESS,
        "층고_mm": FLOOR_HEIGHT,
        "벽체높이_mm": WALL_HEIGHT,
    },
    "부재별": [wall_boq, slab_boq],
    "합계": {
        "총수량": len(walls) + len(slabs),
        "콘크리트체적_m3": round(total_vol, 3),
        "거푸집면적_m2": round(total_form, 2),
    },
}

with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# Markdown
md = []
md.append(f"# BOQ 수량산출 — {result['프로젝트']}\n")
md.append(f"> 산출일시: {result['산출일시']}\n")
md.append("## 파라미터\n")
md.append(f"- 벽체 두께: {WALL_THICKNESS}mm")
md.append(f"- 슬라브 두께: {SLAB_THICKNESS}mm")
md.append(f"- 층고: {FLOOR_HEIGHT}mm (벽체높이 {WALL_HEIGHT}mm + 슬라브 {SLAB_THICKNESS}mm)\n")
md.append("## 부재별 수량\n")
md.append("| 부재 | 수량 | 콘크리트(m³) | 거푸집(m²) |")
md.append("|------|-----:|-------------:|-----------:|")
for b in [wall_boq, slab_boq]:
    md.append(f"| {b['부재']} | {b['수량']} | {b['콘크리트체적_m3']:.3f} | {b['거푸집면적_m2']:.2f} |")
md.append(f"| **합계** | **{len(walls)+len(slabs)}** | **{total_vol:.3f}** | **{total_form:.2f}** |\n")
md.append("## 산출 기준\n")
md.append("- 콘크리트: STEP 솔리드의 체적 합계 (mm³ → m³ 환산)")
md.append("- 거푸집:")
md.append("  - 벽체: 모든 수직면 합계 (양면 + 단부)")
md.append("  - 슬라브: 측면(둘레×두께) + 바닥면 (밑판 거푸집)")

with open(OUT_MD, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md))

print(f"\n[저장] {OUT_JSON}")
print(f"[저장] {OUT_MD}")
print("완료.")
