"""opening_finder — 창/문 위치 검출 (방부장 규칙 2026-07-05).

방부장 규칙 (도면 지식):
  ① 외벽 창/문 = 슬라브 경계는 있는데 벽체선이 끊긴 곳.
     (슬라브 있음 + 벽 없음 = 당연히 개구부)
  ② EV·계단 = 최소 1개 이상 창/문. 특히 EV는 문 최소 1개.
  ③ 전실(EV/계단 앞 작은 방)-세대 경계 = 세대문 최소 1개.

[AUTO] 순수 기하 — 슬라브 경계 ↔ 벽 커버 차집합. 모델 추론 없음.
"""

import math
import sys
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, cluster_stairs, collect_floor_data, pair_x_marks,
    snap_segments)

ROOT = Path(__file__).resolve().parents[2]

WALL_COVER = 250        # 벽 세그먼트 buffer 반경(벽 존재로 간주할 폭) [T]
MIN_OPENING = 700       # 이보다 짧은 벽 없는 구간은 무시(모서리 틈) [T]
MAX_OPENING = 6000      # 이보다 길면 개구가 아니라 미폐합 [T]


# [AUTO] 방부장 ① — 슬라브 외곽 경계에서 벽 없는 구간 = 외벽 창/문
def exterior_openings(slab_outline, wall_segs):
    """slab_outline: 슬라브 전체 외곽 Polygon. wall_segs: 벽 세그먼트.

    반환: [{'mid':(x,y),'width':mm,'a':,'b':}] — 외벽 개구부.
    """
    if slab_outline is None:
        return []
    boundary = slab_outline.exterior
    wall_cover = unary_union([LineString([a, b]).buffer(WALL_COVER, cap_style=2)
                              for a, b in wall_segs]) if wall_segs else None
    if wall_cover is None:
        return []
    # 경계선에서 벽에 덮이지 않은 부분 = 개구부 후보
    uncovered = boundary.difference(wall_cover)
    parts = ([uncovered] if uncovered.geom_type == "LineString"
             else list(uncovered.geoms) if not uncovered.is_empty else [])
    ops = []
    for seg in parts:
        L = seg.length
        if MIN_OPENING <= L <= MAX_OPENING:
            a, b = seg.coords[0], seg.coords[-1]
            ops.append({"mid": (round((a[0]+b[0])/2, 1),
                                round((a[1]+b[1])/2, 1)),
                        "width": round(L), "a": (round(a[0], 1), round(a[1], 1)),
                        "b": (round(b[0], 1), round(b[1], 1)),
                        "kind": "외벽"})
    return ops


# [AUTO] 방부장 ②③ — EV/계단 인접 벽 끊김 = 내부 문 (전실 진출입)
def core_door_openings(cores, wall_segs, slab_outline):
    """EV·계단 폴리곤 둘레에서 벽 없는 구간 = 문 (최소 1개 보장 규칙)."""
    wall_cover = unary_union([LineString([a, b]).buffer(WALL_COVER, cap_style=2)
                              for a, b in wall_segs]) if wall_segs else None
    doors = []
    for c in cores:
        ring = c["poly"].exterior
        uncov = ring.difference(wall_cover) if wall_cover else ring
        parts = ([uncov] if uncov.geom_type == "LineString"
                 else list(uncov.geoms) if not uncov.is_empty else [])
        cand = [(p.length, p) for p in parts if 700 <= p.length <= 2500]
        cand.sort(reverse=True)
        # 규칙: 최소 1개 문 보장 → 가장 넓은 벽없는 구간을 문으로
        if cand:
            _, p = cand[0]
            a, b = p.coords[0], p.coords[-1]
            doors.append({"mid": (round((a[0]+b[0])/2, 1),
                                  round((a[1]+b[1])/2, 1)),
                          "width": round(p.length),
                          "kind": c["kind"] + "_문"})
        else:
            doors.append({"mid": (round(c["poly"].centroid.x, 1),
                                  round(c["poly"].centroid.y, 1)),
                          "width": None, "kind": c["kind"] + "_문[미확정]"})
    return doors


def find_openings(floor="TYP", doc=None):
    if doc is None:
        doc = ezdxf.readfile(str(DXF_S30_101))
    data = collect_floor_data(doc, floor)
    wall = data.get("standing_wall_segs") or data.get("wall_segs", [])

    # 슬라브 외곽 = 골조선+슬라브단부 폐합 union 의 외곽
    bnd = wall + data.get("slab_end_segs", [])
    faces = [f for f in polygonize(unary_union(snap_segments(bnd, 10)))
             if f.area > 3e6]
    outline = unary_union(faces) if faces else None
    if outline and outline.geom_type == "MultiPolygon":
        outline = max(outline.geoms, key=lambda p: p.area)
    if outline is not None:
        outline = Polygon(outline.exterior)   # 구멍 무시, 외곽만

    ext = exterior_openings(outline, wall)

    # EV + 계단 코어
    xmarks = pair_x_marks(data.get("diag_all", []))
    stairs = cluster_stairs(data.get("stair_segs", []))
    cores = ([{"poly": m["poly"], "kind": m["kind"]} for m in xmarks
              if m["kind"] == "EV"]
             + [{"poly": s["poly"], "kind": "계단"} for s in stairs])
    doors = core_door_openings(cores, wall, outline)

    return {"floor": floor, "exterior": ext, "core_doors": doors,
            "outline_area_m2": round(outline.area/1e6, 1) if outline else 0,
            "n_ext": len(ext), "n_core": len(cores)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    r = find_openings("TYP")
    print("=== 창/문 검출 (방부장 규칙) ===")
    print(f"  슬라브 외곽 {r['outline_area_m2']}㎡")
    print(f"  ① 외벽 창/문 (슬라브 있고 벽 끊김): {r['n_ext']}곳")
    for o in r["exterior"][:30]:
        print(f"     {o['kind']} 폭{o['width']}mm @{o['mid']}")
    print(f"  ②③ EV·계단 문 (코어 {r['n_core']}개, 최소1문 규칙):")
    for d in r["core_doors"]:
        print(f"     {d['kind']} 폭{d['width']} @{d['mid']}")


if __name__ == "__main__":
    main()
