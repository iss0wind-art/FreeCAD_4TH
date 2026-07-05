"""unit_placer — 단위세대 창호를 기준층 각 세대 위치에 방향 맞춰 배치.

방부장 방식 2026-07-05:
  A30 타입별 창호(unit_windows.json) + S30 세대참조(위치·타입·회전각)
  → 각 세대에 타입 창호를 회전 배치 → A50 규격·sill 조인 → 골조선 끊김 검증.

방향(rot)은 S30 세대참조 텍스트의 rotation에 실측으로 존재.
반전(mirror) 여부는 골조선 끊김(opening_finder)과 대조해 자동 판정.

[AUTO] 순수 좌표 연산 (회전·평행이동). 모델 추론 없음.
"""

import json
import math
import re
import sys
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, SHEET_Y, SHEETS, bridge_collinear, collect_floor_data)
from core.dxf_parser.unit_extractor import load_or_extract  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "unit_placed_TYP.json"
REF_RE = re.compile(r"(\d{2,3}[A-Z])\s*단위세대")


# [AUTO] S30 기준층 세대참조 (타입·위치·회전각)
def floor_units(doc, floor="TYP"):
    msp = doc.modelspace()
    x0, x1 = SHEETS[floor]
    units = []
    for e in msp:
        if e.dxftype() != "TEXT":
            continue
        m = REF_RE.search(e.dxf.text.strip())
        if not m:
            continue
        x, y = e.dxf.insert.x, e.dxf.insert.y
        if x0 < x < x1 and SHEET_Y[0] < y < SHEET_Y[1]:
            units.append({"type": m.group(1), "x": x, "y": y,
                          "rot": e.dxf.rotation})
    return units


# [AUTO] 로컬 창호를 세대 위치에 회전(+선택 반전) 배치
def place(symbols, origin, cx, cy, rot_deg, mirror=False):
    a = math.radians(rot_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for s in symbols:
        lx = s["lx"]
        ly = -s["ly"] if mirror else s["ly"]
        gx = cx + (lx * ca - ly * sa)
        gy = cy + (lx * sa + ly * ca)
        out.append({**s, "gx": round(gx, 1), "gy": round(gy, 1)})
    return out


def _type_keys(unit_types, type_code):
    """세대타입(59A)의 모든 변형 키 (기본형/확장형/주거약자)."""
    return [k for k in unit_types if k.startswith(type_code + "_")]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    doc = ezdxf.readfile(str(DXF_S30_101))
    units = floor_units(doc, "TYP")
    unit_db = load_or_extract()["types"]

    # 골조선 끊김(창/문 실위치) — 배치 검증용
    data = collect_floor_data(doc, "TYP")
    segs = data["standing_wall_segs"]
    gaps = [(( a[0]+b[0])/2, (a[1]+b[1])/2)
            for a, b in bridge_collinear(segs, max_gap=2600, ang_tol=2,
                                         lateral_tol=60)
            if math.hypot(b[0]-a[0], b[1]-a[1]) >= 400]

    placed = []
    for u in units:
        keys = _type_keys(unit_db, u["type"])
        if not keys:
            placed.append({**u, "status": "미확정: A30 타입 없음"})
            continue
        # 변형(기본/확장) × 반전(정/미러) 전조합 중 골조끊김 최적 채택
        best = None
        for key in keys:
            db = unit_db[key]
            for mirror in (False, True):
                pts = place(db["symbols"], db["origin"], u["x"], u["y"],
                            u["rot"], mirror)
                wins = [p for p in pts if p["kind"] == "창"]
                if not wins:
                    continue
                score = sum(min((math.hypot(p["gx"]-g[0], p["gy"]-g[1])
                                 for g in gaps), default=9e9)
                            for p in wins) / len(wins)
                if best is None or score < best[0]:
                    best = (score, key, mirror, wins)
        if best is None:
            placed.append({**u, "status": "미확정: 창 없음"})
            continue
        avg, key, mirror, wins = best
        placed.append({
            "type": u["type"], "key": key, "x": u["x"], "y": u["y"],
            "rot": u["rot"], "mirror": mirror,
            "n_window": len(wins),
            "avg_gap_dist_mm": round(avg),
            "match": "OK" if avg < 2000 else "확인요망",
            "windows": [{"symbol": p["symbol"], "gx": p["gx"], "gy": p["gy"],
                         "w_mm": p["w_mm"], "h_mm": p["h_mm"]} for p in wins],
        })
    OUT.write_text(json.dumps({"floor": "TYP", "units": placed},
                              ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 단위세대 창호 배치 (방향 정합) ===")
    print(f"  기준층 세대 {len(units)}개 / 골조선 끊김 {len(gaps)}곳")
    for p in placed:
        if "windows" in p:
            print(f"  [{p['type']}] rot{p['rot']:.0f}° mirror={p['mirror']} "
                  f"창 {p['n_window']}개 / 골조선끊김 평균거리 "
                  f"{p['avg_gap_dist_mm']}mm [{p['match']}]")
        else:
            print(f"  [{p['type']}] {p['status']}")
    print(f"  저장: {OUT}")


if __name__ == "__main__":
    main()
