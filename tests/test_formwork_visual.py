"""
거푸집 공제 시각화 — 부재별 색상 + 영역 클립
- 슬라브를 8m×8m로 잘라 시연 영역만 표시
- 부재별 색상 (MATERIAL_RULES.md 따름):
  · 벽-기둥(유로폼) → 옅은 노란색
  · 슬라브 하부(합판) → 옅은 갈색
- Before(분리) / After(Fuse) 두 가지 .FCStd 파일 생성

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_formwork_visual.py
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import FreeCAD
import Part

STEP_PATH    = "output/test_102_B1F.step"
OUT_BEFORE   = "output/visual_before.FCStd"
OUT_AFTER    = "output/visual_after.FCStd"

# 색상 (MATERIAL_RULES.md)
COLOR_WALL  = (1.00, 0.95, 0.65)   # 유로폼 옅은 노란색
COLOR_SLAB  = (0.78, 0.65, 0.50)   # 합판 옅은 갈색
COLOR_FUSE  = (0.85, 0.85, 0.85)   # 통합 솔리드는 회색

SLAB_THICKNESS = 210
WALL_HEIGHT    = 4190

# ── 1. 솔리드 로드 ──────────────────────────────────────────
shape = Part.Shape()
shape.read(STEP_PATH)
solids = shape.Solids
print(f"[로드] {len(solids)}개 솔리드")

walls, slabs = [], []
for s in solids:
    bb = s.BoundBox
    h = bb.ZMax - bb.ZMin
    if abs(h - SLAB_THICKNESS) < 5 and bb.ZMin > 4000:
        slabs.append(s)
    elif abs(h - WALL_HEIGHT) < 5 and bb.ZMin < 5:
        walls.append(s)

# ── 2. 시연 영역 + 슬라브 클립 ──────────────────────────────
def count_in(x0, y0, x1, y1):
    def hit(s):
        b = s.BoundBox
        cx = (b.XMin + b.XMax) / 2
        cy = (b.YMin + b.YMax) / 2
        return x0 <= cx <= x1 and y0 <= cy <= y1
    return sum(1 for s in walls if hit(s))

best = None
for slab in slabs:
    sb = slab.BoundBox
    if sb.XLength * sb.YLength < 5e6:
        continue
    for i in range(5):
        for j in range(5):
            cx = sb.XMin + (i + 0.5) * sb.XLength / 5
            cy = sb.YMin + (j + 0.5) * sb.YLength / 5
            x0, x1 = cx - 4000, cx + 4000
            y0, y1 = cy - 4000, cy + 4000
            nw = count_in(x0, y0, x1, y1)
            if nw >= 4:
                if best is None or nw > best[0]:
                    best = (nw, slab, x0, y0, x1, y1)

assert best, "적합 영역 없음"
nw, base_slab, x0, y0, x1, y1 = best
print(f"[시연영역] X={x0:.0f}~{x1:.0f}, Y={y0:.0f}~{y1:.0f}, 벽 {nw}개")

# 슬라브를 시연 영역으로 클립
slab_bb = base_slab.BoundBox
clip_box = Part.makeBox(x1 - x0, y1 - y0, slab_bb.ZLength,
                        FreeCAD.Vector(x0, y0, slab_bb.ZMin))
clipped_slab = base_slab.common(clip_box)
print(f"[클립] 슬라브 → {clipped_slab.Volume / 1e9:.3f} m³")

zone_walls = []
for w in walls:
    b = w.BoundBox
    cx = (b.XMin + b.XMax) / 2
    cy = (b.YMin + b.YMax) / 2
    if x0 <= cx <= x1 and y0 <= cy <= y1:
        zone_walls.append(w)
print(f"[수집] 벽-기둥 {len(zone_walls)}개")

# ── 3. Before 문서 (부재별 색상, 분리) ───────────────────────
print("\n[Before] 부재별 색상 적용 + 저장")
doc_before = FreeCAD.newDocument("Before")

for i, w in enumerate(zone_walls):
    obj = doc_before.addObject("Part::Feature", f"Wall_{i+1:03d}")
    obj.Shape = w
    obj.ViewObject.ShapeColor = COLOR_WALL  # 유로폼 노란색

slab_obj = doc_before.addObject("Part::Feature", "Slab")
slab_obj.Shape = clipped_slab
slab_obj.ViewObject.ShapeColor = COLOR_SLAB  # 합판 갈색

doc_before.recompute()
doc_before.saveAs(OUT_BEFORE)
print(f"  저장: {OUT_BEFORE}")

# ── 4. After 문서 (Fuse 통합 솔리드) ─────────────────────────
print("\n[After] Boolean Fuse + 저장")
all_zone = zone_walls + [clipped_slab]
fused = all_zone[0]
for s in all_zone[1:]:
    try:
        fused = fused.fuse(s)
    except Exception as ex:
        print(f"  fuse 실패: {ex}")

doc_after = FreeCAD.newDocument("After")
fuse_obj = doc_after.addObject("Part::Feature", "FusedFormwork")
fuse_obj.Shape = fused
fuse_obj.ViewObject.ShapeColor = COLOR_FUSE
doc_after.recompute()
doc_after.saveAs(OUT_AFTER)
print(f"  저장: {OUT_AFTER}")
print(f"  통합 솔리드 면 수: {len(fused.Faces)}")

# ── 5. 면적 비교 ────────────────────────────────────────────
def vert_area(s):
    return sum(f.Area for f in s.Faces if abs(f.normalAt(0.5, 0.5).z) < 0.1) / 1e6

def down_area(s):
    return sum(f.Area for f in s.Faces if f.normalAt(0.5, 0.5).z < -0.9) / 1e6

before_form = sum(vert_area(s) for s in zone_walls) + vert_area(clipped_slab) + down_area(clipped_slab)
after_form  = vert_area(fused) + down_area(fused)
print(f"\n[비교] 거푸집: {before_form:.2f} → {after_form:.2f} m² (공제 {before_form-after_form:.2f} m²)")
print("완료.")
