"""window_opener — 골조선 끊김으로 세대창/문 위치 확정 → A50 규격 매칭 → 오픈.

방부장 확정 2026-07-05: "골조선 끊김으로 세대창 위치 잡고 진행."
  세대 정합(A30 회전배치) 불필요 — 골조선이 이미 제자리.

절차:
  1. 골조선 끊김(bridge_collinear) = 창/문 후보 (위치 + 폭)
  2. 슬라브 단부선 근접 필터 = 진짜 개구부 (골조선 자체 노이즈 제외)
  3. 폭 → A50 창호일람표 규격 매칭 (근사 폭)
  4. 제미나이 레벨공식: 개구 = sill ~ sill+H, 상부 인방보/하부 역보

[AUTO] 순수 기하·규칙 연산. 모델 추론 없음. 매칭 실패는 미확정 플래그.
"""

import json
import math
import sys
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, bridge_collinear, collect_floor_data)
from core.dxf_parser.window_extractor import parse_schedule, DXF_SCHED_UNIT  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "window_openings_TYP.json"

SLAB_NEAR = 400        # 슬라브 단부선 이 거리 내 = 진짜 개구부 [T]
MIN_W, MAX_W = 500, 3500   # 창/문 폭 범위 [T] — 2026-07-21 방부장 확정(거실창 PW1 3,320 실측, 구 3,000은 6곳 누락)


# [AUTO] A50 규격 테이블 → 폭 리스트 (폭 매칭용)
def a50_width_table():
    tbl = parse_schedule(DXF_SCHED_UNIT)
    rows = []
    for sym, r in tbl.items():
        if r.get("w_mm"):
            rows.append({"symbol": sym, "w": r["w_mm"], "h": r["h_mm"],
                         "type": r["type_name"]})
    return rows


def _match_width(w, table, tol=200):
    """끊김 폭 → 가장 가까운 A50 규격 (tol 내). 없으면 None."""
    best = min(table, key=lambda r: abs(r["w"] - w), default=None)
    if best and abs(best["w"] - w) <= tol:
        return best
    return None


def find_windows(floor="TYP", doc=None):
    if doc is None:
        doc = ezdxf.readfile(str(DXF_S30_101))
    data = collect_floor_data(doc, floor)
    segs = data["standing_wall_segs"]

    # 슬라브 단부선 버퍼 (개구부 판정 기준)
    slab_end = data.get("slab_end_segs", [])
    slab_line = unary_union([LineString([a, b]).buffer(SLAB_NEAR)
                             for a, b in slab_end]) if slab_end else None

    table = a50_width_table()
    brs = bridge_collinear(segs, max_gap=MAX_W, ang_tol=2, lateral_tol=60)
    openings = []
    for a, b in brs:
        w = math.hypot(b[0]-a[0], b[1]-a[1])
        if not (MIN_W <= w <= MAX_W):
            continue
        mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2
        # 슬라브 경계 근접 = 외벽/발코니 창, 아니면 내부문 후보
        on_slab = slab_line.contains(Point(mx, my)) if slab_line else False
        spec = _match_width(w, table)
        openings.append({
            "x1": round(a[0], 1), "y1": round(a[1], 1),
            "x2": round(b[0], 1), "y2": round(b[1], 1),
            "mx": round(mx, 1), "my": round(my, 1),
            "width_mm": round(w),
            "on_slab_edge": on_slab,
            "loc": "외벽/발코니" if on_slab else "내부",
            "match": spec["symbol"] if spec else None,
            "match_w": spec["w"] if spec else None,
            "match_h": spec["h"] if spec else None,
            "match_type": spec["type"] if spec else None,
            "status": "확정" if spec else "미확정(A50 규격 없음)",
        })
    return {"floor": floor, "n": len(openings), "openings": openings,
            "a50_specs": len(table)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    r = find_windows("TYP")
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    from collections import Counter
    on = sum(1 for o in r["openings"] if o["on_slab_edge"])
    matched = sum(1 for o in r["openings"] if o["match"])
    print("=== 세대창 오픈 (골조선 끊김 기반) ===")
    print(f"  A50 규격 {r['a50_specs']}종")
    print(f"  골조선 끊김 개구부: {r['n']}곳 "
          f"(외벽/발코니 {on} / 내부 {r['n']-on})")
    print(f"  A50 규격 매칭: {matched}/{r['n']}")
    tc = Counter(o["match_type"] for o in r["openings"] if o["match"])
    print(f"  매칭 타입: {dict(tc)}")
    wc = Counter(o["match"] for o in r["openings"] if o["match"])
    print(f"  부호 분포: {dict(wc.most_common(10))}")
    print(f"  저장: {OUT}")


if __name__ == "__main__":
    main()
