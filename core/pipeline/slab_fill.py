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
import sys
from datetime import datetime
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, FLOOR_ANCHOR, SHEETS, cluster_stairs, collect_floor_data,
    pair_x_marks)

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "output" / "slab_fill_101동.json"

GAP_BRIDGE_MM = 200      # 외곽선 끊김 흡수 버퍼 (창구간·폐합실패 자동 메움) [T]
MIN_HOLE_M2 = 0.3        # 이보다 작은 공제는 노이즈로 무시 [T]


# [AUTO] 순수 기하 — 외곽선 안쪽 통짜 폴리곤 (기본 전면 피복)
def outer_plate(segs, buf=GAP_BRIDGE_MM):
    """골조선 buffer→union→exterior ring = 내부 구멍 전부 메운 통짜 슬라브.

    buffer가 창구간·폐합실패 끊김을 자동으로 이어주므로 벽 폐합 불필요.
    """
    if not segs:
        return None
    band = unary_union([LineString([a, b]).buffer(buf) for a, b in segs])
    if band.geom_type == "MultiPolygon":
        band = max(band.geoms, key=lambda g: g.area)   # 최대 연결성분(=건물)
    plate = Polygon(band.exterior)                     # 내부 홀 전부 메움
    plate = plate.buffer(-buf)                         # 버퍼분 되돌림
    if plate.geom_type == "MultiPolygon":              # 침식으로 갈라지면 본체만
        plate = max(plate.geoms, key=lambda g: g.area)
    return plate


# [AUTO] 순수 규칙 — 도면 표기에서 비피복 구역 수집
def uncovered_zones(data):
    """안 덮이는 곳 4종 수집. 반환 [(kind, polygon, note)]."""
    zones = []
    for m in pair_x_marks(data.get("diag_all", [])):
        kind = "EV실" if m["kind"] == "EV" else "X표시(샤프트·설비)"
        zones.append((kind, m["poly"], f"{round(m['w'])}x{round(m['h'])}mm"))
    for s in cluster_stairs(data.get("stair_segs", [])):
        zones.append(("계단실", s["poly"], f"계단선 {s['n_lines']}본"))
    for p in data.get("pd_polys", []):
        zones.append(("X표시(S-OPEN)", p, "S-OPEN 개구부"))
    return zones


def run_floor(doc, floor):
    data = collect_floor_data(doc, floor)
    segs = data.get("wall_segs") or []
    segs = segs + data.get("slab_end_segs", [])
    plate = outer_plate(segs)
    if plate is None or plate.is_empty:
        return {"floor": floor, "status": "미확정: 골조선 0건"}, None

    gross = plate.area
    slab = plate
    cuts = []
    for kind, poly, note in uncovered_zones(data):
        if poly.area / 1e6 < MIN_HOLE_M2:
            continue
        before = slab.area
        slab = slab.difference(poly)
        cut = before - slab.area
        cuts.append({"kind": kind, "note": note,
                     "zone_m2": round(poly.area / 1e6, 2),
                     "cut_m2": round(cut / 1e6, 2),
                     "cx": round(poly.centroid.x, 1),
                     "cy": round(poly.centroid.y, 1)})

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
        "cuts": [{**c, "x": round(c["cx"] - ax, 1), "y": round(c["cy"] - ay, 1)}
                 for c in cuts],
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
            print(f"  {rep['pit_note']}")
    if out:
        OUT_PATH.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
