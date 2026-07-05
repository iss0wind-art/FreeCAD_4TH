"""preprocess — 정제 DXF 생성기 (방부장 작업방법 B·C단계 코드화).

방부장 「작업방법.dxf」 2026-07-05 전수 분석 결과의 구현:
  B단계: "골조선만 뽑아냄. 끊어진 선·z≠0 은 0으로 만들어줌.
          붉은X=EV 슬래브 안깔림. 계단실 X없어도 코어별도라 슬래브 안깔림"
  C단계: "SL.-50 = 화장실 50 다운. 슬라브 외곽선 끝선까지 있음"

방부장은 '왜/무엇'만 시연 → '어떻게(z=0 명령 등)'는 이천이 코드로 구현.

출력: output/정제_{동}_{층}.dxf
  레이어 재구성(부재별, z=0):
    골조선        노란 A-WALL-RC (해당층 기립 벽)
    하부벽체      파랑 S-하부벽체 (아래층 벽)
    슬라브단부    00_SLAB END 끝선
    보            S-GIRDER/BEAM
    개구_EV       X마크(장변≥1800)
    개구_샤프트   X마크(<1800)
    개구_계단     A-STAIR 클러스터 (슬래브 안깔림 — 코어 별도)
    개구_PD       S-OPEN
    화장실다운    SL.-50 마커 + 근처 폐합박스
    레벨텍스트    SL 텍스트
    연결선        끊긴선 자동연결 (감사용, 별도 색)
    미해결        폐합 실패 붉은표시

[AUTO] 전 함수 — 좌표·색·레이어 규칙 연산. z=0 강제. 추론 없음.
"""

import math
import re
import sys
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, SHEETS, SHEET_Y, bridge_collinear, cluster_stairs,
    collect_floor_data, pair_x_marks, snap_segments)

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "output"

SL_RE = re.compile(r"SL\s*[.]?\s*([+\-±][\s]*\d+|±\s*0)")

# 정제 레이어 → ACI 색 (캐드 검수 시 방부장 색 관례 존중)
LAYER_SPEC = {
    "골조선": 2,        # 노랑
    "하부벽체": 5,      # 파랑
    "슬라브단부": 9,    # 회색
    "보": 4,            # 하늘
    "개구_EV": 1,       # 빨강
    "개구_샤프트": 30,  # 주황
    "개구_계단": 6,     # 보라 (슬래브 안깔림)
    "개구_PD": 1,       # 빨강
    "화장실다운": 3,    # 초록 (SL-50)
    "레벨텍스트": 7,    # 흰검
    "연결선": 40,       # 밝은 파랑 (자동연결 — 감사용)
    "미해결": 1,        # 빨강
}


def _flatten(p):
    """z 무시 2D 좌표 (z=0 평탄화 = 방부장 B단계 '0으로 만들어줌')."""
    return (round(p[0], 2), round(p[1], 2))


# [AUTO] SL 텍스트 + 근처 폐합박스 → 화장실 다운 영역 (방부장 C단계)
def find_bathroom_downs(doc, floor):
    msp = doc.modelspace()
    x0, x1 = SHEETS[floor]
    downs, levels = [], []
    for e in msp:
        if e.dxftype() != "TEXT":
            continue
        t = e.dxf.text.strip()
        m = SL_RE.search(t)
        if not m:
            continue
        x, y = e.dxf.insert.x, e.dxf.insert.y
        if not (x0 < x < x1 and SHEET_Y[0] < y < SHEET_Y[1]):
            continue
        val = t.replace(" ", "")
        is_down = "-50" in val or ("-" in val and "±" not in val)
        levels.append({"x": x, "y": y, "text": t, "down": is_down})
    # 방부장 방식: SL.-50을 "포함하는 벽 폐합 방(=화장실)"을 찾는다.
    # 원본에 다운 박스가 따로 없고(닫힌 폴리라인 3개뿐, 다 시트밖 범례),
    # 화장실 = 벽/골조선/조적벽으로 둘러싸인 소공간. 그 face가 다운 영역.
    data = collect_floor_data(doc, floor)
    wall_segs = (data.get("standing_wall_segs", [])
                 + data.get("wall_segs", []) + data.get("slab_end_segs", []))
    # 조적벽(화장실 칸막이)도 경계에 포함
    for e in msp:
        if e.dxf.layer == "A-WALL-BRICK" and e.dxftype() in ("LINE",
                                                             "LWPOLYLINE"):
            if e.dxftype() == "LINE":
                a = _flatten((e.dxf.start.x, e.dxf.start.y))
                b = _flatten((e.dxf.end.x, e.dxf.end.y))
                if x0 < (a[0]+b[0])/2 < x1 and SHEET_Y[0] < (a[1]+b[1])/2 < SHEET_Y[1]:
                    wall_segs.append((a, b))
            else:
                pts = [_flatten((p[0], p[1])) for p in e.get_points()]
                if x0 < sum(p[0] for p in pts)/len(pts) < x1:
                    for i in range(len(pts)-1):
                        wall_segs.append((pts[i], pts[i+1]))
    geoms = snap_segments(wall_segs, 10)
    faces = [f for f in polygonize(unary_union(geoms))
             if 1.0e6 < f.area < 12.0e6]   # 화장실~작은 방 규모 1~12㎡
    for lv in levels:
        if not lv["down"]:
            continue
        host = next((f for f in faces
                     if f.contains(Point(lv["x"], lv["y"]))), None)
        if host is None:   # 포함 실패 시 최근접(500mm) 폴백 + 미확정
            host = next((f for f in faces
                         if f.distance(Point(lv["x"], lv["y"])) < 500), None)
        if host is not None:
            downs.append({"poly": list(host.exterior.coords),
                          "level_text": lv["text"], "cx": host.centroid.x,
                          "cy": host.centroid.y,
                          "area_m2": round(host.area/1e6, 2)})
    return downs, levels


def build_clean_dxf(floor="TYP"):
    src = ezdxf.readfile(str(DXF_S30_101))
    data = collect_floor_data(src, floor)

    out = ezdxf.new(setup=True)
    msp = out.modelspace()
    for name, aci in LAYER_SPEC.items():
        if name not in out.layers:
            out.layers.add(name, color=aci)

    def add_segs(segs, layer):
        for a, b in segs:
            msp.add_line(_flatten(a), _flatten(b), dxfattribs={"layer": layer})

    stat = {}
    # 1. 골조선(노랑) + 하부벽체 — z=0 평탄화하며 기입
    add_segs(data.get("standing_wall_segs", []), "골조선")
    add_segs(data.get("wall_segs", []), "하부벽체")
    stat["골조선"] = len(data.get("standing_wall_segs", []))
    stat["하부벽체"] = len(data.get("wall_segs", []))

    # 2. 슬라브 단부선 + 보
    add_segs(data.get("slab_end_segs", []), "슬라브단부")
    add_segs(data.get("beam_segs", []), "보")
    stat["슬라브단부"] = len(data.get("slab_end_segs", []))
    stat["보"] = len(data.get("beam_segs", []))

    # 3. 끊긴선 연결 (골조선 대상) — 별도 레이어(감사용)
    wall = data.get("standing_wall_segs") or data.get("wall_segs", [])
    bridges = bridge_collinear(wall, max_gap=2600, ang_tol=2.0, lateral_tol=60)
    add_segs(bridges, "연결선")
    stat["연결선"] = len(bridges)

    # 4. 개구부 — EV/샤프트/계단/PD (방부장: 전부 슬래브 안깔림)
    xmarks = pair_x_marks(data.get("diag_all", []))
    for m in xmarks:
        lay = "개구_EV" if m["kind"] == "EV" else "개구_샤프트"
        c = list(m["poly"].exterior.coords)
        msp.add_lwpolyline([_flatten(p) for p in c], close=True,
                           dxfattribs={"layer": lay})
    stairs = cluster_stairs(data.get("stair_segs", []))
    for s in stairs:
        msp.add_lwpolyline([_flatten(p) for p in s["poly"].exterior.coords],
                           close=True, dxfattribs={"layer": "개구_계단"})
    for p in data.get("pd_polys", []):
        msp.add_lwpolyline([_flatten(c) for c in p.exterior.coords],
                           close=True, dxfattribs={"layer": "개구_PD"})
    stat["개구_EV"] = sum(1 for m in xmarks if m["kind"] == "EV")
    stat["개구_샤프트"] = sum(1 for m in xmarks if m["kind"] != "EV")
    stat["개구_계단"] = len(stairs)
    stat["개구_PD"] = len(data.get("pd_polys", []))

    # 5. 화장실 다운 (SL.-50 + 폐합박스) + 레벨텍스트
    downs, levels = find_bathroom_downs(src, floor)
    for d in downs:
        msp.add_lwpolyline([_flatten(p) for p in d["poly"]], close=True,
                           dxfattribs={"layer": "화장실다운"})
    for lv in levels:
        msp.add_text(lv["text"], dxfattribs={"layer": "레벨텍스트",
                     "height": 200}).set_placement(_flatten((lv["x"], lv["y"])))
    stat["화장실다운"] = len(downs)
    stat["레벨텍스트(SL)"] = len(levels)

    out_path = OUT_DIR / f"정제_101동_{floor}.dxf"
    out.saveas(str(out_path))
    return out_path, stat


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    floors = [a for a in argv if a in SHEETS] or ["TYP"]
    for fl in floors:
        path, stat = build_clean_dxf(fl)
        print(f"=== 정제 DXF [{fl}] (z=0, 부재별 레이어) ===")
        for k, v in stat.items():
            print(f"  {k}: {v}")
        print(f"  → {path}  (오토캐드로 검수)")


if __name__ == "__main__":
    main(sys.argv[1:])
