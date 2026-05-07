"""
verify_step_real.py — 솔리드 STEP 작동 검증
"""
import sys
import FreeCAD
import Part

step_path = r'e:\Git\FREECAD_BOQ\output\final_track1.step'
print(f'[loading] {step_path}')

doc = FreeCAD.newDocument('verify')
Part.insert(step_path, doc.Name)

# 모든 솔리드 채굴
solids = []
for obj in doc.Objects:
    if hasattr(obj, 'Shape') and obj.Shape:
        for s in obj.Shape.Solids:
            solids.append(s)

print(f'[solid count] {len(solids)}')

if not solids:
    print('[FAIL] no solids found in STEP')
    sys.exit(1)

# 부피·BBox·중심 통계
total_volume_m3 = 0.0
xmin = ymin = zmin = float('inf')
xmax = ymax = zmax = float('-inf')
z_floors = {}
volumes = []

for s in solids:
    vol_mm3 = s.Volume
    total_volume_m3 += vol_mm3 / 1e9
    volumes.append(vol_mm3 / 1e9)
    bb = s.BoundBox
    xmin, xmax = min(xmin, bb.XMin), max(xmax, bb.XMax)
    ymin, ymax = min(ymin, bb.YMin), max(ymax, bb.YMax)
    zmin, zmax = min(zmin, bb.ZMin), max(zmax, bb.ZMax)
    cz = int(round(bb.Center.z / 100) * 100)
    z_floors[cz] = z_floors.get(cz, 0) + 1

print(f'[volume]   total={total_volume_m3:.3f} m3')
print(f'  avg={total_volume_m3/len(solids):.3f} m3/solid')
print(f'[bbox]')
print(f'  X={xmin:.0f}~{xmax:.0f}  span={xmax-xmin:.0f}mm')
print(f'  Y={ymin:.0f}~{ymax:.0f}  span={ymax-ymin:.0f}mm')
print(f'  Z={zmin:.0f}~{zmax:.0f}  span={zmax-zmin:.0f}mm')

invalid = 0
for s in solids:
    if not s.isValid():
        invalid += 1
print(f'[validity] valid={len(solids)-invalid}/{len(solids)}  invalid={invalid}')
