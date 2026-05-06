"""
좌표 정합성 진단 스크립트
1. S30-001 vs S30-002 기둥 좌표 정합성
2. S-GIRDER 보와 S30-001 기둥의 XY 정합성
3. INSERT 변환 검증
4. 실측 검증 (C1 기둥 반경 5000mm 내 보 끝점)
"""
import json
import sys
import math
import os

sys.path.insert(0, "D:/Git/FreeCAD_4TH")

JSON_PATH = "D:/Git/FreeCAD_4TH/output/poc_v3_101.json"
DXF_PATH = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
BEAM_CLIP = (55000, 2085000, 229013, 2460000)

# ──────────────────────────────────────────────────────────────────────
# 1. JSON 로드
# ──────────────────────────────────────────────────────────────────────
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

sheets_by_id = {}
for sheet in data["sheets"]:
    sheets_by_id[sheet["sheet_id"]] = sheet

print("=" * 70)
print("1. S30-001 vs S30-002 기둥 좌표 정합성")
print("=" * 70)

for sid in ["S30-001", "S30-002", "PKG-B2", "PKG-B1"]:
    sheet = sheets_by_id.get(sid)
    if not sheet:
        print(f"  {sid}: 데이터 없음")
        continue
    cols = sheet.get("columns", [])
    if not cols:
        print(f"  {sid}: 기둥 없음")
        continue
    xs = [c["abs_cx"] for c in cols]
    ys = [c["abs_cy"] for c in cols]
    lxs = [c["cx"] for c in cols]
    lys = [c["cy"] for c in cols]
    print(f"\n  [{sid}] 기둥 수: {len(cols)}")
    print(f"    abs_cx: min={min(xs):.0f}  max={max(xs):.0f}  range={max(xs)-min(xs):.0f}")
    print(f"    abs_cy: min={min(ys):.0f}  max={max(ys):.0f}  range={max(ys)-min(ys):.0f}")
    print(f"    cx(로컬): min={min(lxs):.0f}  max={max(lxs):.0f}")
    print(f"    cy(로컬): min={min(lys):.0f}  max={max(lys):.0f}")

# sheet_offset 계산
print("\n  -- sheet_offset (abs - local) 첫 기둥 기준 --")
for sid in ["S30-001", "S30-002", "PKG-B2", "PKG-B1"]:
    sheet = sheets_by_id.get(sid)
    if not sheet:
        continue
    cols = sheet.get("columns", [])
    if not cols:
        continue
    c = cols[0]
    ox = c["abs_cx"] - c["cx"]
    oy = c["abs_cy"] - c["cy"]
    print(f"    {sid}: offset_x={ox:.0f}, offset_y={oy:.0f}")

# S30-001 vs S30-002 비교
print("\n  -- B2F(S30-001) vs B1F(S30-002) 범위 비교 --")
s001 = sheets_by_id.get("S30-001", {})
s002 = sheets_by_id.get("S30-002", {})
cols001 = s001.get("columns", [])
cols002 = s002.get("columns", [])
if cols001 and cols002:
    xs001 = [c["abs_cx"] for c in cols001]
    ys001 = [c["abs_cy"] for c in cols001]
    xs002 = [c["abs_cx"] for c in cols002]
    ys002 = [c["abs_cy"] for c in cols002]
    print(f"  S30-001 X: {min(xs001):.0f} ~ {max(xs001):.0f}")
    print(f"  S30-002 X: {min(xs002):.0f} ~ {max(xs002):.0f}")
    print(f"  S30-001 Y: {min(ys001):.0f} ~ {max(ys001):.0f}")
    print(f"  S30-002 Y: {min(ys002):.0f} ~ {max(ys002):.0f}")

    # -126000 보정 후
    xs002c = [x - 126000 for x in xs002]
    print(f"\n  S30-002 X (보정 -126000): {min(xs002c):.0f} ~ {max(xs002c):.0f}")
    x_overlap = (max(min(xs001), min(xs002c)), min(max(xs001), max(xs002c)))
    print(f"  X 겹침 범위: {x_overlap[0]:.0f} ~ {x_overlap[1]:.0f}")

    # 가장 가까운 기둥 쌍 (보정 후)
    min_dist = float("inf")
    best_pair = None
    for c1 in cols001[:10]:  # 계산 시간 단축
        for c2 in cols002[:10]:
            dist = math.hypot(c1["abs_cx"] - (c2["abs_cx"] - 126000),
                              c1["abs_cy"] - c2["abs_cy"])
            if dist < min_dist:
                min_dist = dist
                best_pair = (c1, c2)
    if best_pair:
        c1, c2 = best_pair
        print(f"\n  가장 가까운 기둥 쌍 (보정 -126000, 첫10개 한정):")
        print(f"    S30-001: abs_cx={c1['abs_cx']:.0f}, abs_cy={c1['abs_cy']:.0f} ({c1['symbol']})")
        print(f"    S30-002: abs_cx={c2['abs_cx']:.0f}→보정={c2['abs_cx']-126000:.0f}, abs_cy={c2['abs_cy']:.0f} ({c2['symbol']})")
        print(f"    거리: {min_dist:.1f} mm")

# ──────────────────────────────────────────────────────────────────────
# 2. S-GIRDER 보 추출 및 S30-001 기둥과 정합성 확인
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("2. S-GIRDER 보 좌표 범위 및 S30-001 기둥과 정합성")
print("=" * 70)

try:
    import ezdxf

    if not os.path.exists(DXF_PATH):
        print(f"  DXF 파일 없음: {DXF_PATH}")
    else:
        doc = ezdxf.readfile(DXF_PATH)
        msp = doc.modelspace()

        # BEAM_CLIP
        bx0, by0, bx1, by1 = BEAM_CLIP
        print(f"  BEAM_CLIP: x={bx0}~{bx1}, y={by0}~{by1}")

        # S-GIRDER 레이어에서 LINE 추출 (iter_all 사용)
        girder_lines = []
        for entity in msp.query("LINE"):
            if "S-GIRDER" in (entity.dxf.layer or "").upper():
                sx, sy = entity.dxf.start.x, entity.dxf.start.y
                ex, ey = entity.dxf.end.x, entity.dxf.end.y
                # BEAM_CLIP 내부인지 확인 (끝점 기준)
                if (bx0 <= sx <= bx1 and by0 <= sy <= by1) or \
                   (bx0 <= ex <= bx1 and by0 <= ey <= by1):
                    girder_lines.append((sx, sy, ex, ey))

        # INSERT를 통한 LINE도 확인
        insert_lines = []
        for insert in msp.query("INSERT"):
            block_name = insert.dxf.name
            try:
                block = doc.blocks[block_name]
                ins_x = insert.dxf.insert.x
                ins_y = insert.dxf.insert.y
                rot = getattr(insert.dxf, "rotation", 0)
                sx_scale = getattr(insert.dxf, "xscale", 1)
                sy_scale = getattr(insert.dxf, "yscale", 1)
                for ent in block:
                    if ent.dxftype() == "LINE" and "S-GIRDER" in (ent.dxf.layer or "").upper():
                        # 변환 없이 로컬 좌표
                        insert_lines.append({
                            "insert": (ins_x, ins_y),
                            "rot": rot,
                            "scale": (sx_scale, sy_scale),
                            "local_start": (ent.dxf.start.x, ent.dxf.start.y),
                            "local_end": (ent.dxf.end.x, ent.dxf.end.y),
                        })
            except Exception:
                pass

        print(f"\n  직접 modelspace LINE (S-GIRDER, BEAM_CLIP 내): {len(girder_lines)}개")
        if girder_lines:
            gxs = [x for sx, sy, ex, ey in girder_lines for x in [sx, ex]]
            gys = [y for sx, sy, ex, ey in girder_lines for y in [sy, ey]]
            print(f"    X 범위: {min(gxs):.0f} ~ {max(gxs):.0f}")
            print(f"    Y 범위: {min(gys):.0f} ~ {max(gys):.0f}")
        else:
            print("    → BEAM_CLIP 필터 없이 재시도")
            all_girder = []
            for entity in msp.query("LINE"):
                if "S-GIRDER" in (entity.dxf.layer or "").upper():
                    sx, sy = entity.dxf.start.x, entity.dxf.start.y
                    ex, ey = entity.dxf.end.x, entity.dxf.end.y
                    all_girder.append((sx, sy, ex, ey))
            print(f"    S-GIRDER LINE 전체: {len(all_girder)}개")
            if all_girder:
                gxs = [x for sx, sy, ex, ey in all_girder for x in [sx, ex]]
                gys = [y for sx, sy, ex, ey in all_girder for y in [sy, ey]]
                print(f"    X 범위: {min(gxs):.0f} ~ {max(gxs):.0f}")
                print(f"    Y 범위: {min(gys):.0f} ~ {max(gys):.0f}")

        print(f"\n  INSERT 블록 내 S-GIRDER LINE: {len(insert_lines)}개")
        if insert_lines:
            print(f"  샘플 5개:")
            for il in insert_lines[:5]:
                print(f"    INSERT({il['insert'][0]:.0f},{il['insert'][1]:.0f}) "
                      f"rot={il['rot']:.1f} scale={il['scale']} "
                      f"local_start=({il['local_start'][0]:.0f},{il['local_start'][1]:.0f}) "
                      f"local_end=({il['local_end'][0]:.0f},{il['local_end'][1]:.0f})")

        # ──────────────────────────────────────────────────────────────
        # 3. INSERT 변환 검증 — iter_all 방식
        # ──────────────────────────────────────────────────────────────
        print("\n" + "=" * 70)
        print("3. INSERT iter_all 변환 검증")
        print("=" * 70)

        # ezdxf iter_all 사용 (실제 모델 공간 좌표 반환 여부 확인)
        try:
            from ezdxf.query import EntityQuery
            iter_all_lines = []
            for entity in msp.query("INSERT"):
                try:
                    for ent in entity.virtual_entities():
                        if ent.dxftype() == "LINE" and "S-GIRDER" in (ent.dxf.layer or "").upper():
                            sx, sy = ent.dxf.start.x, ent.dxf.start.y
                            ex, ey = ent.dxf.end.x, ent.dxf.end.y
                            iter_all_lines.append((sx, sy, ex, ey))
                except Exception:
                    pass

            print(f"  virtual_entities() S-GIRDER LINE: {len(iter_all_lines)}개")
            if iter_all_lines:
                gxs = [x for sx, sy, ex, ey in iter_all_lines for x in [sx, ex]]
                gys = [y for sx, sy, ex, ey in iter_all_lines for y in [sy, ey]]
                print(f"  X 범위: {min(gxs):.0f} ~ {max(gxs):.0f}")
                print(f"  Y 범위: {min(gys):.0f} ~ {max(gys):.0f}")
                print(f"  → S30-001 기둥 X: {min(xs001):.0f}~{max(xs001):.0f}, Y: {min(ys001):.0f}~{max(ys001):.0f}")
                x_diff = min(gxs) - min(xs001)
                y_diff = min(gys) - min(ys001)
                print(f"  → X 최솟값 차이: {x_diff:.0f}, Y 최솟값 차이: {y_diff:.0f}")
        except Exception as e:
            print(f"  virtual_entities 실패: {e}")

        # ──────────────────────────────────────────────────────────────
        # 4. 실측 검증 — C1(abs_cx=129241, abs_cy=2381804) 반경 5000mm
        # ──────────────────────────────────────────────────────────────
        print("\n" + "=" * 70)
        print("4. 실측 검증: C1 기둥(129241, 2381804) 반경 5000mm 내 S-GIRDER 끝점")
        print("=" * 70)

        c1_x, c1_y = 129240.87, 2381804.31

        # 모든 S-GIRDER 소스 통합
        all_beams = list(girder_lines)
        if iter_all_lines:
            all_beams.extend(iter_all_lines)
        print(f"  사용 보 데이터: {len(all_beams)}개 LINE")

        if all_beams:
            nearby = []
            for sx, sy, ex, ey in all_beams:
                d_start = math.hypot(sx - c1_x, sy - c1_y)
                d_end = math.hypot(ex - c1_x, ey - c1_y)
                min_d = min(d_start, d_end)
                if min_d < 5000:
                    nearby.append({
                        "start": (sx, sy),
                        "end": (ex, ey),
                        "d_start": d_start,
                        "d_end": d_end,
                        "min_d": min_d,
                    })
            nearby.sort(key=lambda b: b["min_d"])
            print(f"  반경 5000mm 내 보 끝점: {len(nearby)}개")
            for b in nearby[:5]:
                print(f"    start=({b['start'][0]:.0f},{b['start'][1]:.0f}) d={b['d_start']:.0f}  "
                      f"end=({b['end'][0]:.0f},{b['end'][1]:.0f}) d={b['d_end']:.0f}")

            # 전체 최소거리 통계
            all_min_dists = []
            for sx, sy, ex, ey in all_beams:
                d_start = math.hypot(sx - c1_x, sy - c1_y)
                d_end = math.hypot(ex - c1_x, ey - c1_y)
                all_min_dists.append(min(d_start, d_end))
            all_min_dists.sort()
            print(f"\n  모든 보까지 최소거리 통계:")
            print(f"    최소: {all_min_dists[0]:.0f}")
            print(f"    상위 5: {[round(d) for d in all_min_dists[:5]]}")
            print(f"    중앙값: {all_min_dists[len(all_min_dists)//2]:.0f}")
        else:
            print("  보 데이터 없음 — DXF에서 S-GIRDER를 찾지 못했음")

        # 레이어 목록 확인
        print("\n  -- DXF 레이어 중 GIRDER/BEAM 포함 --")
        for layer in doc.layers:
            name = layer.dxf.name
            if any(k in name.upper() for k in ["GIRDER", "BEAM", "BEAM"]):
                print(f"    {name}")

        # S-GIRDER 포함 레이어 정확 확인
        print("\n  -- 레이어별 LINE 개수 (상위 20) --")
        layer_count = {}
        for entity in msp.query("LINE"):
            lyr = entity.dxf.layer
            layer_count[lyr] = layer_count.get(lyr, 0) + 1
        for lyr, cnt in sorted(layer_count.items(), key=lambda x: -x[1])[:20]:
            print(f"    {lyr}: {cnt}")

except ImportError:
    print("  ezdxf 없음 — pip install ezdxf 필요")
except Exception as e:
    import traceback
    print(f"  오류: {e}")
    traceback.print_exc()

print("\n" + "=" * 70)
print("진단 완료")
print("=" * 70)
