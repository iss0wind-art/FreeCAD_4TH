"""
verify_step_real.py — 87 솔리드 STEP 진짜 작동 검증 (본영 직접 작성)
방부장 친명 *"그게 제일 중요한데"* 받자와 즉시.
"""
import sys
import FreeCAD
import Part

step_path = r'd:\Git\FreeCAD_4TH\output\f1_3d_stack_102.step'
print(f'[loading] {step_path}')

doc = FreeCAD.newDocument('verify')
Part.insert(step_path, doc.Name)

# 모든 솔리드 채굴
solids = []
for obj in doc.Objects:
    if hasattr(obj, 'Shape') and obj.Shape:
        for s in obj.Shape.Solids:
            solids.append(s)

print(f'[solid count] {len(solids)} (expect 87)')

if not solids:
    print('[FAIL] no solids found in STEP')
    sys.exit(1)

# 부피·BBox·중심 통계
total_volume_m3 = 0.0
xmin = ymin = zmin = float('inf')
xmax = ymax = zmax = float('-inf')
z_floors = {}  # z 층별 솔리드 수
volumes = []

for s in solids:
    vol_mm3 = s.Volume
    total_volume_m3 += vol_mm3 / 1e9
    volumes.append(vol_mm3 / 1e9)
    bb = s.BoundBox
    xmin, xmax = min(xmin, bb.XMin), max(xmax, bb.XMax)
    ymin, ymax = min(ymin, bb.YMin), max(ymax, bb.YMax)
    zmin, zmax = min(zmin, bb.ZMin), max(zmax, bb.ZMax)
    # 솔리드 중심 Z를 100mm로 반올림하여 층 카운트
    cz = int(round(bb.Center.z / 100) * 100)
    z_floors[cz] = z_floors.get(cz, 0) + 1

print(f'[volume]   total={total_volume_m3:.3f} m3 (meta says 129.523)')
print(f'  avg={total_volume_m3/len(solids):.3f} m3/solid')
print(f'  min={min(volumes):.3f}  max={max(volumes):.3f}')
print(f'[bbox]')
print(f'  X={xmin:.0f}~{xmax:.0f}  span={xmax-xmin:.0f}mm  ({(xmax-xmin)/1000:.1f}m)')
print(f'  Y={ymin:.0f}~{ymax:.0f}  span={ymax-ymin:.0f}mm  ({(ymax-ymin)/1000:.1f}m)')
print(f'  Z={zmin:.0f}~{zmax:.0f}  span={zmax-zmin:.0f}mm  ({(zmax-zmin)/1000:.1f}m)')
print(f'  Z range expect -8800 to +13200')

print(f'[Z floor distribution]')
for z in sorted(z_floors.keys()):
    bar = '#' * z_floors[z]
    print(f'  Z={z:+6d}mm  {z_floors[z]:3d}  {bar}')

# 무결성: 모든 솔리드 isValid?
invalid = 0
for s in solids:
    if not s.isValid():
        invalid += 1
print(f'[validity] valid={len(solids)-invalid}/{len(solids)}  invalid={invalid}')

# 격자 정합 — 솔리드 중심 X/Y의 *정렬* 검사 (격자라면 동일 X·Y 다수 반복)
xs = sorted(set(int(round(s.BoundBox.Center.x / 100) * 100) for s in solids))
ys = sorted(set(int(round(s.BoundBox.Center.y / 100) * 100) for s in solids))
print(f'[grid alignment] unique X positions: {len(xs)}  unique Y: {len(ys)}')
print(f'  (격자 정렬됐으면 unique 값이 솔리드 수보다 *훨씬* 적어야 함)')
