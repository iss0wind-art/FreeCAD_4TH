"""
지하주차장 통합 도면 v3 트림 — 1단계: 통계 파악

대상: 260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf (15.4 MB)
목적: 레이어별 분포 + 전체 BoundBox + 슬라브 폴리곤 클러스터링 가능성 확인
"""

import os, sys, time
sys.path.insert(0, r'd:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF_PATH = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"

t0 = time.time()
print(f"[로딩] {os.path.basename(DXF_PATH)}")
import ezdxf
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()
print(f"[로딩 완료] {time.time()-t0:.1f}초")

# 레이어별 통계
from collections import Counter
layer_count = Counter()
type_count = Counter()
layer_bbox = {}  # layer -> [minx, miny, maxx, maxy]

t1 = time.time()
all_x, all_y = [], []
for e in msp:
    layer = e.dxf.layer
    dxftype = e.dxftype()
    layer_count[layer] += 1
    type_count[dxftype] += 1

    # 좌표 수집 (BoundBox용)
    pts = []
    if dxftype == 'LINE':
        pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    elif dxftype == 'LWPOLYLINE':
        try:
            pts = [(x, y) for x, y, *_ in e.get_points()]
        except: pass
    elif dxftype == 'TEXT':
        try:
            pts = [(e.dxf.insert.x, e.dxf.insert.y)]
        except: pass
    elif dxftype == 'INSERT':
        try:
            pts = [(e.dxf.insert.x, e.dxf.insert.y)]
        except: pass
    elif dxftype == 'CIRCLE' or dxftype == 'ELLIPSE':
        try:
            pts = [(e.dxf.center.x, e.dxf.center.y)]
        except: pass

    if pts:
        for x, y in pts:
            all_x.append(x); all_y.append(y)
            if layer not in layer_bbox:
                layer_bbox[layer] = [x, y, x, y]
            else:
                bb = layer_bbox[layer]
                bb[0] = min(bb[0], x); bb[1] = min(bb[1], y)
                bb[2] = max(bb[2], x); bb[3] = max(bb[3], y)

print(f"[스캔 완료] {time.time()-t1:.1f}초, 총 {sum(layer_count.values())}개 엔티티")

# 전체 BoundBox
if all_x and all_y:
    minx, miny, maxx, maxy = min(all_x), min(all_y), max(all_x), max(all_y)
    print(f"\n[전체 BoundBox]")
    print(f"  X: {minx:.1f} ~ {maxx:.1f}  (폭 {(maxx-minx)/1000:.1f} m)")
    print(f"  Y: {miny:.1f} ~ {maxy:.1f}  (높이 {(maxy-miny)/1000:.1f} m)")
    print(f"  영역: {(maxx-minx)/1000 * (maxy-miny)/1000:.0f} m² (전체 단지 외곽)")

# 엔티티 타입별
print(f"\n[엔티티 타입]")
for t, c in type_count.most_common(15):
    print(f"  {t:20s}: {c:6d}")

# 레이어별 (상위 25)
print(f"\n[레이어 상위 25]")
for layer, c in layer_count.most_common(25):
    bb = layer_bbox.get(layer)
    if bb:
        w = (bb[2]-bb[0])/1000; h = (bb[3]-bb[1])/1000
        print(f"  {layer[:35]:35s}: {c:6d}  영역 {w:6.1f}×{h:6.1f} m")
    else:
        print(f"  {layer[:35]:35s}: {c:6d}")

# 슬라브 외곽선 분석 ('00_SLAB END + ETC' 폴리곤 폐합 가능성)
print(f"\n[슬라브 외곽선 분석 — 클러스터링 가능성]")
slab_lines = []
slab_lwpolys = []
for e in msp:
    if e.dxf.layer != '00_SLAB END + ETC':
        continue
    if e.dxftype() == 'LINE':
        slab_lines.append(((e.dxf.start.x, e.dxf.start.y),
                           (e.dxf.end.x, e.dxf.end.y)))
    elif e.dxftype() == 'LWPOLYLINE':
        try:
            pts = [(x, y) for x, y, *_ in e.get_points()]
            slab_lwpolys.append((pts, e.is_closed))
        except: pass
print(f"  LINE {len(slab_lines)}개, LWPOLYLINE {len(slab_lwpolys)}개")
print(f"  closed LWPOLY: {sum(1 for _, c in slab_lwpolys if c)}개")

# 폴리곤 클러스터 시도
from shapely.geometry import Polygon as ShPoly
from shapely.validation import make_valid

closed_polys = []
for pts, closed in slab_lwpolys:
    if not closed or len(pts) < 4:
        continue
    try:
        p = ShPoly(pts)
        if not p.is_valid:
            p = make_valid(p)
            if hasattr(p, 'geoms'):
                p = max((g for g in p.geoms if g.geom_type == 'Polygon'),
                        key=lambda g: g.area, default=None)
        if p and hasattr(p, 'area') and p.area > 100_000_000:  # 100 m² 이상
            closed_polys.append(p)
    except: pass

print(f"  100m² 이상 closed 슬라브 폴리곤: {len(closed_polys)}개")
if closed_polys:
    closed_polys.sort(key=lambda p: -p.area)
    print(f"  상위 10개 면적:")
    for i, p in enumerate(closed_polys[:10]):
        cx, cy = p.centroid.x, p.centroid.y
        print(f"    #{i+1}: {p.area/1e6:8.1f} m²  중심 ({cx:.0f}, {cy:.0f})")

# 4분할 영역 분석
print(f"\n[4분할 분석 — 가설 A]")
midx = (minx + maxx) / 2
midy = (miny + maxy) / 2
quad_count = {'LL': 0, 'LR': 0, 'UL': 0, 'UR': 0}
for e in msp:
    if e.dxftype() != 'LINE':
        continue
    cx = (e.dxf.start.x + e.dxf.end.x) / 2
    cy = (e.dxf.start.y + e.dxf.end.y) / 2
    if cx < midx and cy < midy: quad_count['LL'] += 1
    elif cx >= midx and cy < midy: quad_count['LR'] += 1
    elif cx < midx and cy >= midy: quad_count['UL'] += 1
    else: quad_count['UR'] += 1
print(f"  좌하 LL {quad_count['LL']}, 우하 LR {quad_count['LR']}, 좌상 UL {quad_count['UL']}, 우상 UR {quad_count['UR']}")

print(f"\n[총 소요] {time.time()-t0:.1f}초")
