# -*- coding: utf-8 -*-
"""slab_fill — 슬라브 전면피복 방식 (방부장 원칙 2026-07-20).

  "슬라브는 생각해볼 것도 없었다. 기본적으로 모든 골조 외곽선을 기준으로
   층마다 다 덮힌다. 벽체를 구하거나 보를 구할 필요가 없다.
   문제는 안 덮히는 곳을 찾는 거다."

기존 방식(폐합 기반)의 실패 원인: 벽 폐합이 안 되면 슬라브 생성 자체가 실패.
본 방식: 외곽선 안쪽을 통째로 덮은 뒤(기본값), 안 덮이는 곳만 공제.

안 덮이는 곳 4종:
  1. E/V실                      — X마크(장변≥1800) 검출
  2. 계단실·램프                — 계단선 클러스터. 램프는 램프도면 별도(본 층 해당 없음)
  3. X 표시(슬라브 깔지 마라)   — X마크(샤프트)·S-OPEN 개구부. 설비배관·오픈부 대부분
  4. 우수조·PIT (층고차)        — 표고 다름. 구멍이 아니라 별도 레벨 → 본 산출에선 미공제,
                                  [미확정] 플래그로 보고 (평면도 판별 필요)

[AUTO] 순수 기하 연산. 추론 없음 — 공제 대상은 전부 도면 표기(X마크·계단선·S-OPEN)에서 옴.
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, FLOOR_ANCHOR, SHEETS, cluster_stairs, collect_floor_data,
    pair_x_marks)

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "output" / "slab_fill_101동.json"

GAP_BRIDGE_MM = 200      # 외곽선 끊김 흡수 버퍼 (창구간·폐합실패 자동 메움) [T]
# 방부장 규칙 2026-07-20: "전실 샤프트는 통상 가로세로 1m2 이내는 수량에서 제외한다.
# 큰 구멍이 아닌 곳은 굳이 구멍을 내지 않아도 된다. 하지만 큰 구멍은 뚫어야 한다."
MIN_HOLE_M2 = 1.0        # 1㎡ 이하 개구는 공제하지 않음 (통상 관행)


# [AUTO] 순수 기하 — 외곽선 안쪽 통짜 폴리곤 (기본 전면 피복)
def outer_plate(segs, buf=GAP_BRIDGE_MM):
    """골조선 buffer→union→exterior ring = 내부 구멍 전부 메운 통짜 슬라브.

    buffer가 창구간·폐합실패 끊김을 자동으로 이어주므로 벽 폐합 불필요.
    """
    if not segs:
        return None
    # mitre 조인 — 둥근 모서리가 20~180mm 자투리를 수백 개 만들던 문제 차단
    # (방부장 2026-07-20 지적: "전혀 뜬금없는 초록 짜투리")
    band = unary_union([LineString([a, b]).buffer(buf, join_style=2, mitre_limit=2.0)
                        for a, b in segs])
    if band.geom_type == "MultiPolygon":
        band = max(band.geoms, key=lambda g: g.area)   # 최대 연결성분(=건물)
    plate = Polygon(band.exterior)                     # 내부 홀 전부 메움
    plate = plate.buffer(-buf, join_style=2, mitre_limit=2.0)
    if plate.geom_type == "MultiPolygon":              # 침식으로 갈라지면 본체만
        plate = max(plate.geoms, key=lambda g: g.area)
    return plate.simplify(30)                          # 잔여 미세 정점 정리 [T]


ROOM_TOL = 150           # 국소 폐합 버퍼 — 2*150=300mm 틈까지 메움 [T]
ROOM_PAD = 6000          # 씨앗 주변 골조선 수집 반경 [T]


# [AUTO] 순수 기하 — 씨앗 주변 국소 골조선으로 '닫힌 방' 추출.
# 방부장 지시(2026-07-20): "X마크·계단선은 신호일 뿐, 슬라브선은 골조선에서 따와라."
# band=union(buffer(국소 벽선))의 내부 구멍 = 벽으로 둘러싸인 방.
# 방이 안 닫히면 None → 공제하지 않고 [미해결] 보고 (원칙⑤ 모르면 방부장 토스).
# 실증(2026-07-20 부장 실검수): 방이 잡힌 2건만 O, 안 잡힌 8건은 전부 X 판정.
def local_room(segs, seed, tol=ROOM_TOL, pad=ROOM_PAD):
    win = box(*seed.bounds).buffer(pad)
    loc = [LineString([a, b]) for a, b in segs
           if win.intersects(LineString([a, b]))]
    if not loc:
        return None
    band = unary_union([l.buffer(tol) for l in loc])
    polys = band.geoms if band.geom_type == "MultiPolygon" else [band]
    c = seed.centroid
    for p in polys:
        for r in p.interiors:
            room = Polygon(r)
            if room.contains(c):
                return room.buffer(tol)      # 벽 중심선까지 복원
    return None


EV_MAX_M2 = 20.0         # 이보다 큰 방은 EV로 보지 않음 [T]
STAIR_MAX_M2 = 60.0      # 계단실 상한 — 초과하면 벽 미폐합으로 방이 층 전체로 번진 것 [T]
                         # (B2F에서 980㎡ 계단실이 층 전체를 도려낸 사고 방지)
LABEL_R = 1600           # 부호 텍스트 인정 반경 [T]


# [AUTO] 순수 수집 — 해당 층 시트의 텍스트(부호) 위치.
# 방부장 2026-07-20: "구조도면과 건축도면은 교차로 봐야한다."
# 1차로 구조도면 자체의 부호를 쓴다 — EB1(EV), DN/SS(계단), SL.-xx(슬라브 레벨).
def sheet_texts(doc, floor):
    x0, x1 = SHEETS[floor]
    out = []

    def grab(e, d=0):
        t = e.dxftype()
        if t in ("TEXT", "MTEXT"):
            try:
                v = (e.plain_text() if t == "MTEXT" else e.dxf.text).strip()
                pt = e.dxf.insert
                if v and x0 < pt.x < x1:
                    out.append((v, pt.x, pt.y))
            except Exception:
                pass
        elif t == "INSERT" and d < 4:
            try:
                for ve in e.virtual_entities():
                    grab(ve, d + 1)
            except Exception:
                pass

    for e in doc.modelspace():
        grab(e)
    return out


# [AUTO] 순수 수집 — 해당 층 시트의 HATCH 경계 폴리곤.
# 방부장 2026-07-20: "해치를 읽어내야 정확히 어디가 화장실 자리인지,
#   어디만큼 다운해야 하는지 알 수 있다." — 종전엔 LINE/LWPOLYLINE만 읽어 놓쳤음.
# 화장실·전실 레벨다운 구역은 SOLID 해치로 칠해져 있고 곁에 SL.-xx 텍스트가 붙는다.
def sheet_hatches(doc, floor):
    x0, x1 = SHEETS[floor]
    out = []

    def walk(e, d=0):
        t = e.dxftype()
        if t == "HATCH":
            try:
                for path in e.paths:
                    vs = [(v[0], v[1]) for v in (getattr(path, "vertices", []) or [])]
                    if len(vs) < 3:
                        continue
                    poly = Polygon(vs)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    if poly.is_empty:
                        continue
                    if x0 < poly.centroid.x < x1:
                        out.append(poly)
            except Exception:
                pass
        elif t == "INSERT" and d < 4:
            try:
                for ve in e.virtual_entities():
                    walk(ve, d + 1)
            except Exception:
                pass

    for e in doc.modelspace():
        walk(e)
    return out


def _has_label(texts, geom, pattern, r=LABEL_R):
    c = geom.centroid
    return any(pattern in v.upper() and math.hypot(x - c.x, y - c.y) < r
               for v, x, y in texts)


# [AUTO] 순수 기하 — 도면 전체에서 벽으로 둘러싸인 닫힌 방 추출
def closed_rooms(segs, tol=ROOM_TOL):
    band = unary_union([LineString([a, b]).buffer(tol) for a, b in segs])
    polys = band.geoms if band.geom_type == "MultiPolygon" else [band]
    rooms = []
    for p in polys:
        for r in p.interiors:
            rm = Polygon(r).buffer(tol)
            if not rm.is_empty:
                rooms.append(rm)
    return rooms


# [AUTO] 순수 규칙 — 닫힌 방을 '도면 부호'로 분류. 추론 없음.
#   계단선 클러스터        → 계단실 [예외규칙: 도면상 슬라브 있으나 계단 별도 모델링 위해 비움]
#   대각선 2본+ & EB1 부호 → EV실   (EB1 없으면 EV 아님 — 가짜 X 제거)
#   SL.-50 부호 근처 빗금  → 슬라브 '레벨 다운' 구역 (구멍 아님! 화장실·전실 마감 단차)
def uncovered_zones(data, segs, texts, hatches):
    rooms = closed_rooms(segs)
    stair_pts = [s["poly"].centroid for s in cluster_stairs(data.get("stair_segs", []))]
    diag_pts = [Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                for a, b in (data.get("diag_all") or [])]
    zones, claimed, oversize = [], [], []
    for rm in rooms:
        n_st = sum(1 for q in stair_pts if rm.contains(q))
        n_dg = sum(1 for q in diag_pts if rm.contains(q))
        if n_st:
            if rm.area / 1e6 > STAIR_MAX_M2:
                oversize.append({"type": "계단실 경계 미확정(방 과대)",
                                 "note": f"계단선 {n_st}개 → 방 {round(rm.area/1e6)}㎡ "
                                         f"(상한 {STAIR_MAX_M2:.0f}㎡ 초과, 벽 미폐합)",
                                 "cx": round(rm.centroid.x, 1),
                                 "cy": round(rm.centroid.y, 1),
                                 "seed_m2": round(rm.area / 1e6, 2)})
                continue                 # 공제하지 않음 — 원칙⑤ 방부장 토스
            zones.append(("계단실", rm, f"계단선 클러스터 {n_st}개 [예외규칙: 도면상 "
                                        f"슬라브 있으나 계단 별도 모델링 위해 비움]"))
            claimed.append(rm)
        elif n_dg >= 2 and rm.area <= EV_MAX_M2 * 1e6 and _has_label(texts, rm, "EB1"):
            zones.append(("EV실", rm, f"EB1 부호 + 방 안 대각선 {n_dg}본"))
            claimed.append(rm)

    # 레벨다운 구역: SL.-xx 텍스트 곁의 해치 = 화장실·전실 마감 단차 (구멍 아님)
    level_zones = []
    for h in hatches:
        if h.area / 1e6 > 12:            # 과대 해치(세대구획 등) 제외 [T]
            continue
        if _has_label(texts, h, "SL.", r=2000):
            c = h.centroid
            level_zones.append({"type": "레벨다운(해치+SL 부호)",
                                "note": f"해치 {round(h.area/1e6, 2)}㎡",
                                "cx": round(c.x, 1), "cy": round(c.y, 1),
                                "seed_m2": round(h.area / 1e6, 2),
                                "ring": [[round(x, 1), round(y, 1)]
                                         for x, y in h.exterior.coords]})
    unresolved = list(oversize)
    for m in pair_x_marks(data.get("diag_all", [])):
        poly, c = m["poly"], m["poly"].centroid
        if any(rm.contains(c) for rm in claimed):
            continue
        rec = {"note": f"X마크 {round(m['w'])}x{round(m['h'])}mm",
               "cx": round(c.x, 1), "cy": round(c.y, 1),
               "seed_m2": round(poly.area / 1e6, 2)}
        if _has_label(texts, poly, "SL."):
            continue                     # 레벨다운 구역 — 해치로 이미 잡음
        if poly.area / 1e6 <= MIN_HOLE_M2:
            rec["type"] = "소형샤프트(1㎡이하 제외)"
            rec["excluded"] = True       # 통상 규칙상 공제 안 함
        else:
            rec["type"] = "미확정 X표시(1㎡초과 — 뚫어야 함)"
        unresolved.append(rec)
    return zones, unresolved, level_zones


def run_floor(doc, floor):
    data = collect_floor_data(doc, floor)
    segs = data.get("wall_segs") or []
    segs = segs + data.get("slab_end_segs", [])
    plate = outer_plate(segs)
    if plate is not None and not plate.is_valid:
        plate = plate.buffer(0)
    if plate is None or plate.is_empty:
        return {"floor": floor, "status": "미확정: 골조선 0건"}, None

    gross = plate.area
    slab = plate
    cuts = []
    texts = sheet_texts(doc, floor)
    hatches = sheet_hatches(doc, floor)
    zones, unresolved, level_zones = uncovered_zones(data, segs, texts, hatches)
    for kind, poly, note in zones:
        if poly.area / 1e6 < MIN_HOLE_M2:
            continue
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        before = slab.area
        try:
            slab = slab.difference(poly)
        except Exception as e:            # 기하 예외로 층 전체가 죽지 않게
            print(f"    [경고] {kind} 공제 실패({e.__class__.__name__}) — 건너뜀")
            continue
        cut = before - slab.area
        cuts.append({"kind": kind, "note": note,
                     "zone_m2": round(poly.area / 1e6, 2),
                     "cut_m2": round(cut / 1e6, 2),
                     "cx": round(poly.centroid.x, 1),
                     "cy": round(poly.centroid.y, 1),
                     "ring": [[round(x, 1), round(y, 1)]
                              for x, y in poly.exterior.coords]})

    parts = list(slab.geoms) if slab.geom_type == "MultiPolygon" else [slab]
    report = {
        "floor": floor,
        "method": "전면피복 - 비피복공제 (방부장 원칙 2026-07-20)",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "gross_m2": round(gross / 1e6, 2),
        "net_m2": round(slab.area / 1e6, 2),
        "cut_total_m2": round((gross - slab.area) / 1e6, 2),
        "cuts": cuts,
        "parts": len(parts),
        "unresolved": unresolved,
        "level_zones": level_zones,
        "pit_note": "[미확정] 우수조·PIT 층고차 구역 미반영 — 평면도 판별 필요",
    }
    ax, ay = FLOOR_ANCHOR[floor]
    geo = {
        "floor": floor,
        "plate_outline": [[round(x - ax, 1), round(y - ay, 1)]
                          for x, y in plate.exterior.coords],
        "slab_parts": [{"exterior": [[round(x - ax, 1), round(y - ay, 1)]
                                     for x, y in p.exterior.coords],
                        "holes": [[[round(x - ax, 1), round(y - ay, 1)]
                                   for x, y in r.coords] for r in p.interiors]}
                       for p in parts],
        "cuts": [{**c, "x": round(c["cx"] - ax, 1), "y": round(c["cy"] - ay, 1),
                  "ring_rel": [[round(x - ax, 1), round(y - ay, 1)] for x, y in c["ring"]]}
                 for c in cuts],
        "unresolved": [{**u, "x": round(u["cx"] - ax, 1), "y": round(u["cy"] - ay, 1)}
                       for u in unresolved],
        "level_zones": [{**z, "x": round(z["cx"] - ax, 1), "y": round(z["cy"] - ay, 1)}
                        for z in level_zones],
    }
    return report, geo


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    floors = [a for a in argv if a in SHEETS] or list(SHEETS)
    doc = ezdxf.readfile(str(DXF_S30_101))
    out = {}
    for fl in floors:
        rep, geo = run_floor(doc, fl)
        if geo:
            out[fl] = geo
        print(f"\n=== {fl} === {rep.get('method', rep.get('status'))}")
        if "gross_m2" in rep:
            print(f"  전면피복 {rep['gross_m2']}㎡ - 공제 {rep['cut_total_m2']}㎡ "
                  f"= 순 슬라브 {rep['net_m2']}㎡ (조각 {rep['parts']})")
            for c in rep["cuts"]:
                print(f"    - {c['kind']}: {c['zone_m2']}㎡ 중 {c['cut_m2']}㎡ 공제 ({c['note']})")
            for z in rep.get("level_zones", []):
                print(f"    ~ [레벨다운] {z['seed_m2']}㎡ ({z['note']}) — 슬라브 있음, 단차만 (통상 -50)")
            for u in rep.get("unresolved", []):
                print(f"    ! {u['type']} {u['seed_m2']}㎡ ({u['note']})")
            print(f"  {rep['pit_note']}")
    if out:
        OUT_PATH.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
