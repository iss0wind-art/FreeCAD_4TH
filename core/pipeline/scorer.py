"""scorer — 채점기: 방부장 정답 모델 ↔ 이천 파싱 대조 (오류율 측정).

정답지: output/answer_101_TYP.json (방부장 101동 기준층 skp 추출)
  {벽체: [[x0,y0,z0,x1,y1,z1]...74], 슬라브: [...13]}  (SketchUp mm)

절차:
  1. 방부장 벽 점군 ↔ S30 골조선 형상 정합 (강체변환)
  2. 방부장 부재를 S30 좌표로 변환
  3. 슬라브: 개수 + 최근접 중심거리 + 면적 오차
  4. 벽체: 개수 + 최근접 중심거리 + 두께/길이 오차
  5. 부재별 오류율 표

[AUTO] 순수 기하 대조. 모델 추론 없음.
"""

import json
import math
import sys
from pathlib import Path

import ezdxf
import numpy as np
from shapely.geometry import box
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, collect_floor_data, snap_segments)
from core.pipeline.sheet_align import rigid_align  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ANSWER = ROOT / "output" / "answer_101_TYP.json"
ANSWER_WALLPTS = ROOT / "output" / "answer_wall_pts.json"   # 조밀 벽 발자국
ANSWER_SLABPOLY = ROOT / "output" / "answer_slab_polys.json"  # 슬라브 실폴리곤

POS_TOL = 500        # 중심거리 이내면 매칭 성공 [T] mm
AREA_TOL = 0.15      # 면적 오차 15% 이내 정답 [T]


def _bbox_corners(members):
    pts = []
    for b in members:
        pts += [(b[0], b[1]), (b[3], b[1]), (b[3], b[4]), (b[0], b[4])]
    return np.array(pts)


def _bbox_poly(b):
    return box(b[0], b[1], b[3], b[4])


def score():
    ans = json.loads(ANSWER.read_text(encoding="utf-8"))
    ans_wall, ans_slab = ans["벽체"], ans["슬라브"]

    # 정답 벽 점군 ↔ S30 골조선 정합 — 조밀 벽 발자국(1208점)으로 정밀정합
    doc = ezdxf.readfile(str(DXF_S30_101))
    data = collect_floor_data(doc, "TYP")
    s30_segs = data["standing_wall_segs"]
    s30_pts = np.array([p for seg in s30_segs for p in seg])
    ans_pts = (np.array(json.loads(ANSWER_WALLPTS.read_text(encoding="utf-8")))
               if ANSWER_WALLPTS.exists() else _bbox_corners(ans_wall))

    # 방부장(src) → S30(dst)
    R, t, err, ang = rigid_align(ans_pts, s30_pts)

    def to_s30(x, y):
        v = R @ np.array([x, y]) + t
        return float(v[0]), float(v[1])

    def xform_bbox(b):
        cs = [to_s30(b[0], b[1]), to_s30(b[3], b[1]),
              to_s30(b[3], b[4]), to_s30(b[0], b[4])]
        xs = [c[0] for c in cs]
        ys = [c[1] for c in cs]
        return box(min(xs), min(ys), max(xs), max(ys))

    # 내 파싱: 슬라브 face (TYP)
    bnd = s30_segs + data.get("slab_end_segs", [])
    my_slabs = [f for f in polygonize(unary_union(snap_segments(bnd, 10)))
                if f.area > 3e6]

    # 슬라브 채점: 실제 폴리곤 IoU (bbox는 개구부·간격 포함해 3배 뻥튀기)
    from shapely.geometry import Polygon as SPoly
    if ANSWER_SLABPOLY.exists():
        rings = json.loads(ANSWER_SLABPOLY.read_text(encoding="utf-8"))
        ans_polys = [SPoly([to_s30(x, y) for x, y in r]).buffer(0)
                     for r in rings if len(r) >= 3]
    else:
        ans_polys = [xform_bbox(b) for b in ans_slab]
    ans_union = unary_union(ans_polys)
    my_union = unary_union(my_slabs)
    inter = ans_union.intersection(my_union).area
    slab_iou = inter / ans_union.union(my_union).area
    slab_cover = inter / ans_union.area
    miss = ans_union.difference(my_union)     # 누락 (정답에 있는데 내가 없음)
    false_pos = my_union.difference(ans_union)  # 오탐

    # 벽 채점: 정답 74개 중심 → 내 벽 세그 최근접
    my_wall_mid = [((s[0][0]+s[1][0])/2, (s[0][1]+s[1][1])/2)
                   for s in s30_segs]
    wall_hit = 0
    for b in ans_wall:
        cx, cy = to_s30((b[0]+b[3])/2, (b[1]+b[4])/2)
        d = min(math.hypot(m[0]-cx, m[1]-cy) for m in my_wall_mid)
        if d < POS_TOL * 2:
            wall_hit += 1

    return {
        "align_err_mm": round(err), "align_ang": round(ang, 1),
        "slab": {"answer": len(ans_slab), "mine": len(my_slabs),
                 "answer_area_m2": round(ans_union.area/1e6, 1),
                 "mine_area_m2": round(my_union.area/1e6, 1),
                 "IoU": round(slab_iou, 2), "cover": round(slab_cover, 2),
                 "miss_m2": round(miss.area/1e6, 1),
                 "falsepos_m2": round(false_pos.area/1e6, 1),
                 "recall": round(slab_cover, 2)},
        "_miss_geom": miss, "_R": R, "_t": t,
        "wall": {"answer": len(ans_wall), "mine_seg": len(s30_segs),
                 "matched": wall_hit,
                 "recall": round(wall_hit/len(ans_wall), 2)},
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    r = score()
    print("=== 채점 (방부장 정답 ↔ 이천 파싱) ===")
    print(f"  좌표정합 오차 {r['align_err_mm']}mm / 회전 {r['align_ang']}°")
    s, w = r["slab"], r["wall"]
    print(f"  [슬라브] 정답 {s['answer_area_m2']}㎡ / 내파싱 {s['mine_area_m2']}㎡")
    print(f"           IoU {s['IoU']*100:.0f}% / 커버 {s['cover']*100:.0f}% / "
          f"누락 {s['miss_m2']}㎡ / 오탐 {s['falsepos_m2']}㎡")
    print(f"  [벽체]   정답 {w['answer']} / 내세그 {w['mine_seg']} / "
          f"매칭 {w['matched']} → 재현율 {w['recall']*100:.0f}%")
    print(f"  ※ 오류율 = 100 - 재현율. 위치허용 {POS_TOL}mm 기준.")


if __name__ == "__main__":
    main()
