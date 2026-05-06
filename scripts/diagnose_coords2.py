"""
좌표 정합성 진단 2단계 - 상세 분석
"""
import json
import sys
import math

sys.path.insert(0, "D:/Git/FreeCAD_4TH")

JSON_PATH = "D:/Git/FreeCAD_4TH/output/poc_v3_101.json"
DXF_PATH = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

sheets_by_id = {}
for sheet in data["sheets"]:
    sheets_by_id[sheet["sheet_id"]] = sheet

s001 = sheets_by_id["S30-001"]
s002 = sheets_by_id["S30-002"]
cols001 = s001["columns"]
cols002 = s002["columns"]

xs001 = [c["abs_cx"] for c in cols001]
ys001 = [c["abs_cy"] for c in cols001]
xs002 = [c["abs_cx"] for c in cols002]
ys002 = [c["abs_cy"] for c in cols002]

print("=== S30-001 offset_x =", cols001[0]["abs_cx"] - cols001[0]["cx"])
print("=== S30-002 offset_x =", cols002[0]["abs_cx"] - cols002[0]["cx"])
print("=== offset 차이 =", (cols002[0]["abs_cx"] - cols002[0]["cx"]) - (cols001[0]["abs_cx"] - cols001[0]["cx"]))

print()
print("S30-001 X:", round(min(xs001)), "~", round(max(xs001)))
print("S30-002 X:", round(min(xs002)), "~", round(max(xs002)))
print("S30-002 -126000 X:", round(min(xs002)-126000), "~", round(max(xs002)-126000))
print()
print("S30-001 Y:", round(min(ys001)), "~", round(max(ys001)))
print("S30-002 Y:", round(min(ys002)), "~", round(max(ys002)))

# B1F vs B2F 같은 XY인지 확인 - 모든 기둥 쌍
print()
print("=== B2F vs B1F 전체 기둥 쌍 최소거리 (-126000 보정) ===")
matches = []
for c1 in cols001:
    for c2 in cols002:
        dx = c1["abs_cx"] - (c2["abs_cx"] - 126000)
        dy = c1["abs_cy"] - c2["abs_cy"]
        dist = math.hypot(dx, dy)
        if dist < 1000:
            matches.append({
                "sym001": c1["symbol"], "x001": c1["abs_cx"], "y001": c1["abs_cy"],
                "sym002": c2["symbol"], "x002": c2["abs_cx"], "y002": c2["abs_cy"],
                "x002c": c2["abs_cx"] - 126000,
                "dx": dx, "dy": dy, "dist": dist
            })
print(f"거리 1000mm 미만 쌍: {len(matches)}개")
for m in matches[:10]:
    print(f"  B2F {m['sym001']}({m['x001']:.0f},{m['y001']:.0f}) <-> "
          f"B1F {m['sym002']}({m['x002c']:.0f},{m['y002']:.0f}) dist={m['dist']:.1f}")

# DXF 분석
print()
print("=== DXF S-GIRDER 분석 ===")
import ezdxf, os
if not os.path.exists(DXF_PATH):
    print(f"DXF 없음: {DXF_PATH}")
    sys.exit()

doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()

# virtual_entities로 변환된 좌표 추출
beam_lines = []
for insert in msp.query("INSERT"):
    try:
        for ent in insert.virtual_entities():
            if ent.dxftype() == "LINE" and "S-GIRDER" in (ent.dxf.layer or "").upper():
                sx, sy = ent.dxf.start.x, ent.dxf.start.y
                ex, ey = ent.dxf.end.x, ent.dxf.end.y
                beam_lines.append((sx, sy, ex, ey))
    except Exception:
        pass

print(f"S-GIRDER LINE (virtual_entities): {len(beam_lines)}")
if beam_lines:
    gxs = [x for sx,sy,ex,ey in beam_lines for x in [sx,ex]]
    gys = [y for sx,sy,ex,ey in beam_lines for y in [sy,ey]]
    print(f"X: {min(gxs):.0f} ~ {max(gxs):.0f}")
    print(f"Y: {min(gys):.0f} ~ {max(gys):.0f}")

# INSERT 삽입점들 확인
print()
print("=== INSERT 삽입점들 (S-GIRDER 포함 블록) ===")
insert_pts = {}
for insert in msp.query("INSERT"):
    try:
        block = doc.blocks[insert.dxf.name]
        has_girder = any("S-GIRDER" in (e.dxf.layer or "").upper()
                         for e in block if e.dxftype() == "LINE")
        if has_girder:
            key = (round(insert.dxf.insert.x), round(insert.dxf.insert.y))
            insert_pts[key] = insert_pts.get(key, 0) + 1
    except Exception:
        pass
print(f"고유 삽입점 수: {len(insert_pts)}")
for pt, cnt in sorted(insert_pts.items())[:10]:
    print(f"  INSERT({pt[0]}, {pt[1]}) x{cnt}개 LINE")

# 삽입점 오프셋이 적용된 좌표 범위 확인
print()
print("=== 로컬 좌표 + INSERT 오프셋 변환 검증 ===")
sample_insert = None
for insert in msp.query("INSERT"):
    try:
        block = doc.blocks[insert.dxf.name]
        girder_ents = [e for e in block if e.dxftype() == "LINE"
                       and "S-GIRDER" in (e.dxf.layer or "").upper()]
        if girder_ents:
            sample_insert = (insert, girder_ents[0])
            break
    except Exception:
        pass

if sample_insert:
    ins, ent = sample_insert
    ix, iy = ins.dxf.insert.x, ins.dxf.insert.y
    lsx, lsy = ent.dxf.start.x, ent.dxf.start.y
    lex, ley = ent.dxf.end.x, ent.dxf.end.y
    print(f"  INSERT: ({ix:.0f}, {iy:.0f})")
    print(f"  로컬 start: ({lsx:.0f}, {lsy:.0f})")
    print(f"  로컬 end: ({lex:.0f}, {ley:.0f})")
    print(f"  수동변환 start: ({ix+lsx:.0f}, {iy+lsy:.0f})")
    print(f"  수동변환 end: ({ix+lex:.0f}, {iy+ley:.0f})")
    # virtual_entities 첫 번째
    for ve in ins.virtual_entities():
        if ve.dxftype() == "LINE" and "S-GIRDER" in (ve.dxf.layer or "").upper():
            print(f"  virtual_entities start: ({ve.dxf.start.x:.0f}, {ve.dxf.start.y:.0f})")
            print(f"  virtual_entities end: ({ve.dxf.end.x:.0f}, {ve.dxf.end.y:.0f})")
            break

# C1 기둥 (129241, 2381804) 근처 보
print()
print("=== C1(129241, 2381804) 반경 10000mm 내 보 끝점 ===")
c1x, c1y = 129240.87, 2381804.31
nearby = []
for sx, sy, ex, ey in beam_lines:
    d_s = math.hypot(sx - c1x, sy - c1y)
    d_e = math.hypot(ex - c1x, ey - c1y)
    if min(d_s, d_e) < 10000:
        nearby.append((min(d_s, d_e), sx, sy, ex, ey, d_s, d_e))
nearby.sort()
print(f"반경 10000mm 내: {len(nearby)}개")
for md, sx, sy, ex, ey, ds, de in nearby[:10]:
    print(f"  start=({sx:.0f},{sy:.0f}) d={ds:.0f}  end=({ex:.0f},{ey:.0f}) d={de:.0f}")

# Y 범위 불일치 분석
print()
print("=== 좌표계 불일치 분석 ===")
print(f"S-GIRDER Y 범위: {min(gys):.0f} ~ {max(gys):.0f}" if beam_lines else "보 없음")
print(f"S30-001  Y 범위: {min(ys001):.0f} ~ {max(ys001):.0f}")
if beam_lines:
    print(f"Y 차이 (보 min - 기둥 min): {min(gys)-min(ys001):.0f}")
    print(f"Y 차이 (보 max - 기둥 max): {max(gys)-max(ys001):.0f}")

    # 기둥이 보 범위 내에 있는지 확인
    cols_in_beam_range = [c for c in cols001
                          if min(gxs) <= c["abs_cx"] <= max(gxs)
                          and min(gys) <= c["abs_cy"] <= max(gys)]
    print(f"S30-001 기둥 중 S-GIRDER X,Y 범위 내 기둥: {len(cols_in_beam_range)}/{len(cols001)}")

print()
print("=== 완료 ===")
