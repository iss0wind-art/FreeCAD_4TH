"""
거푸집 공제 시연 (트림)
- 102_B1F 모델에서 작은 영역 추출
- Boolean fuse → 부재 접촉면 자동 인식
- 공제 전/후 거푸집 면적 비교

핵심 가설: FreeCAD의 OCCT 솔리드 → 정확한 트림 가능

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_formwork_deduction.py
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import FreeCAD
import Part

STEP_PATH = "output/test_102_B1F.step"
OUT_PATH  = "output/test_formwork_dedu.step"

SLAB_THICKNESS = 210
GIRDER_HEIGHT  = 700
WALL_HEIGHT    = 4190

# ── 1. STEP 로드 + 부재 분류 ─────────────────────────────────
print(f"[로드] {STEP_PATH}")
shape = Part.Shape()
shape.read(STEP_PATH)
all_solids = shape.Solids
print(f"[로드] 솔리드 {len(all_solids)}개")

walls, girders, slabs = [], [], []
for s in all_solids:
    bb = s.BoundBox
    h = bb.ZMax - bb.ZMin
    z_min = bb.ZMin
    if abs(h - SLAB_THICKNESS) < 5 and z_min > 4000:
        slabs.append(s)
    elif abs(h - GIRDER_HEIGHT) < 5 and z_min > 3000:
        girders.append(s)
    elif abs(h - WALL_HEIGHT) < 5 and z_min < 5:
        walls.append(s)

print(f"[분류] 벽-기둥 {len(walls)} / 거더 {len(girders)} / 슬라브 {len(slabs)}")

# ── 2. 시연 영역: 슬라브 + 거더 + 벽 모두 있는 곳 자동 탐색 ─
def count_in_zone(x0, y0, x1, y1):
    def hit(s):
        b = s.BoundBox
        cx = (b.XMin + b.XMax) / 2
        cy = (b.YMin + b.YMax) / 2
        return x0 <= cx <= x1 and y0 <= cy <= y1
    return sum(hit(s) for s in slabs), sum(hit(s) for s in girders), sum(hit(s) for s in walls)

best = None
for slab in slabs:
    sb = slab.BoundBox
    if sb.XLength * sb.YLength < 5e6:  # 너무 작은 다운슬라브 제외
        continue
    # 슬라브 내부를 grid 분할
    for i in range(5):
        for j in range(5):
            cx = sb.XMin + (i + 0.5) * sb.XLength / 5
            cy = sb.YMin + (j + 0.5) * sb.YLength / 5
            x0, x1 = cx - 4000, cx + 4000
            y0, y1 = cy - 4000, cy + 4000
            ns, ng, nw = count_in_zone(x0, y0, x1, y1)
            # 슬라브 + 벽 조합도 허용 (거더가 같은 영역에 없을 수 있음)
            if ns >= 1 and (ng + nw) >= 3:
                score = ns * 100 + ng * 10 + nw
                if best is None or score > best[0]:
                    best = (score, x0, y0, x1, y1, ns, ng, nw)

if best is None:
    raise RuntimeError("적합한 시연 영역 없음")
_, xmin, ymin, xmax, ymax, ns, ng, nw = best
print(f"[자동탐색] 영역: 슬라브 {ns}, 거더 {ng}, 벽-기둥 {nw}")

print(f"\n[시연영역] X={xmin:.0f}~{xmax:.0f}, Y={ymin:.0f}~{ymax:.0f}")
print(f"[시연영역] 크기: {xmax-xmin:.0f} x {ymax-ymin:.0f} mm")

def in_zone(s):
    b = s.BoundBox
    cx = (b.XMin + b.XMax) / 2
    cy = (b.YMin + b.YMax) / 2
    return xmin <= cx <= xmax and ymin <= cy <= ymax

zone_slabs = [s for s in slabs if in_zone(s)]
zone_girders = [s for s in girders if in_zone(s)]
zone_walls = [s for s in walls if in_zone(s)]

print(f"[시연영역 내] 벽-기둥 {len(zone_walls)} / 거더 {len(zone_girders)} / 슬라브 {len(zone_slabs)}")

# ── 3. 거푸집 면적 측정 헬퍼 ─────────────────────────────────
def total_surface(solid):
    """솔리드의 전체 표면적 (mm²)"""
    return sum(f.Area for f in solid.Faces)

def vertical_surface(solid):
    """수직면(측면)만 합산 - 거푸집 근사"""
    total = 0
    for f in solid.Faces:
        try:
            n = f.normalAt(0.5, 0.5)
            if abs(n.z) < 0.1:
                total += f.Area
        except Exception:
            pass
    return total

def upward_surface(solid):
    """위쪽 향한 면 (Z+) - 슬라브 윗면 등"""
    total = 0
    for f in solid.Faces:
        try:
            n = f.normalAt(0.5, 0.5)
            if n.z > 0.9:
                total += f.Area
        except Exception:
            pass
    return total

def downward_surface(solid):
    """아래쪽 향한 면 (Z-) - 슬라브 밑판"""
    total = 0
    for f in solid.Faces:
        try:
            n = f.normalAt(0.5, 0.5)
            if n.z < -0.9:
                total += f.Area
        except Exception:
            pass
    return total

# ── 4. 공제 전 (각 부재 독립) ────────────────────────────────
print("\n[Before] 각 부재 독립 — 공제 안 함")
all_zone = zone_walls + zone_girders + zone_slabs

total_concrete = sum(s.Volume for s in all_zone) / 1e9
total_full_surf = sum(total_surface(s) for s in all_zone) / 1e6

# 거푸집 면적 (관행적 공식)
wall_form = sum(vertical_surface(s) for s in zone_walls) / 1e6
girder_side = sum(vertical_surface(s) for s in zone_girders) / 1e6
girder_bot = sum(downward_surface(s) for s in zone_girders) / 1e6
slab_bot = sum(downward_surface(s) for s in zone_slabs) / 1e6
slab_side = sum(vertical_surface(s) for s in zone_slabs) / 1e6

before_form = wall_form + girder_side + girder_bot + slab_bot + slab_side
print(f"  콘크리트 체적: {total_concrete:.4f} m³")
print(f"  거푸집 (공제 전):")
print(f"    벽-기둥 측면: {wall_form:.2f} m²")
print(f"    거더 측면+하면: {girder_side+girder_bot:.2f} m²")
print(f"    슬라브 하면+측면: {slab_bot+slab_side:.2f} m²")
print(f"    합계: {before_form:.2f} m²")

# ── 5. Boolean Fuse → 통합 솔리드 ────────────────────────────
print("\n[Fuse] Boolean Union 시도...")
try:
    if len(all_zone) == 0:
        print("  영역 내 부재 없음, 종료")
        sys.exit(0)
    fused = all_zone[0]
    for i, s in enumerate(all_zone[1:], 1):
        try:
            fused = fused.fuse(s)
        except Exception as ex:
            print(f"  fuse 실패 {i}: {ex}")
            continue
    print(f"  통합 솔리드 면 수: {len(fused.Faces)}")

    fused_concrete = fused.Volume / 1e9
    fused_full_surf = total_surface(fused) / 1e6

    fused_vert = vertical_surface(fused) / 1e6
    fused_down = downward_surface(fused) / 1e6
    fused_up = upward_surface(fused) / 1e6

    # 거푸집 면적 (공제 후): 외피만 계산
    # 윗면(슬라브 위)은 거푸집 아님 (콘크리트 노출 마감)
    after_form = fused_vert + fused_down

    print(f"\n[After] Boolean Fuse 후 — 접촉면 자동 공제")
    print(f"  콘크리트 체적: {fused_concrete:.4f} m³ (공제 전과 동일해야 정상)")
    print(f"  거푸집 (공제 후):")
    print(f"    측면(외피): {fused_vert:.2f} m²")
    print(f"    하면: {fused_down:.2f} m²")
    print(f"    합계: {after_form:.2f} m²")

    deduction = before_form - after_form
    rate = (deduction / before_form * 100) if before_form > 0 else 0

    print("\n" + "=" * 50)
    print(f"공제량 = {deduction:.2f} m² ({rate:.1f}% 절감)")
    print("=" * 50)

    fused.exportStep(OUT_PATH)
    print(f"\n[저장] {OUT_PATH}")
except Exception as ex:
    print(f"[오류] Boolean fuse 실패: {ex}")
    import traceback
    traceback.print_exc()

print("완료.")
