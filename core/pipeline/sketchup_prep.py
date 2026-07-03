"""sketchup_prep — 스케치업 빌드용 정규화 지오메트리 생성.

[AUTO] 순수 좌표 연산 — 시트별 modelspace 좌표를 층 겹침 좌표계로 정규화
(x' = x - 시트 x0, 시트 피치 126000mm 실측 검증). 모델 추론 없음.

출력: output/sketchup_build_101동.json
  { floors: { B2F: {z, storey_h, slab_thk, slab_thk_source,
                    slabs[], wall_faces[], columns[], openings[]} } }
"""

import json
import sys
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shapely.ops import polygonize, unary_union  # noqa: E402
from core.pipeline.slab_engine import (  # noqa: E402
    DXF_S30_101, FLOOR_ANCHOR, bridge_collinear, collect_floor_data,
    snap_segments)
from core.pipeline.frame_parser import detect_columns  # noqa: E402


# [AUTO] 계단 트레드 박스 결정론 생성 — 방향은 A-STAIR 최장선 각도 실측.
# 실측: 단높이 157.22, 런당 9단(디딤 8), 디딤 270, 2런, 중간참 z=1415.
def stair_tread_boxes(poly_coords, angle_deg):
    xs = [p[0] for p in poly_coords]
    ys = [p[1] for p in poly_coords]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    along_x = angle_deg < 45 or angle_deg > 135   # 런 진행축 (실측 각도)
    boxes = []
    riser, tread, n = 157.22, 270.0, 8
    if along_x:
        half = (y1 - y0) / 2.0
        for i in range(n):
            boxes.append({"x0": x0 + i*tread, "y0": y0,
                          "x1": x0 + (i+1)*tread, "y1": y0 + half,
                          "dz": riser * (i+1)})
            boxes.append({"x0": x1 - (i+1)*tread, "y0": y0 + half,
                          "x1": x1 - i*tread, "y1": y1,
                          "dz": 1415.0 + riser * (i+1)})
        boxes.append({"x0": x0 + n*tread, "y0": y0, "x1": x1, "y1": y1,
                      "dz": 1415.0})   # 중간참
    else:
        half = (x1 - x0) / 2.0
        for i in range(n):
            boxes.append({"x0": x0, "y0": y0 + i*tread,
                          "x1": x0 + half, "y1": y0 + (i+1)*tread,
                          "dz": riser * (i+1)})
            boxes.append({"x0": x0 + half, "y0": y1 - (i+1)*tread,
                          "x1": x1, "y1": y1 - i*tread,
                          "dz": 1415.0 + riser * (i+1)})
        boxes.append({"x0": x0, "y0": y0 + n*tread, "x1": x1, "y1": y1,
                      "dz": 1415.0})
    return [{k: round(v, 1) for k, v in b.items()} for b in boxes]


# [AUTO] 해당층 기립 벽 face — 골조선(노랑) 페어 폐합 슬리버 추출
def standing_wall_faces(doc, floor):
    """반환: (벽 발자국 목록, 창구간 브리지 목록) — 브리지 = 창 위치 실측."""
    data = collect_floor_data(doc, floor)
    segs = data.get("standing_wall_segs", [])
    if not segs:
        return [], []
    bridges = bridge_collinear(segs, max_gap=2600, ang_tol=2.0,
                               lateral_tol=60)
    faces = polygonize(unary_union(snap_segments(segs + bridges, 5)))
    out = []
    for f in faces:
        if f.area < 0.05e6 or f.area > 60e6:
            continue
        if f.buffer(-150).is_empty:          # 슬리버 = 벽 발자국
            out.append(list(f.exterior.coords))
    return out, bridges


# [AUTO] 창 오픈 — 방부장 방식: 벽체 형성(브리지) 후 창 위치만큼 공제.
# 브리지 세그 = 골조선이 끊긴 창 구간 실측. 1차는 전높이 오픈,
# 인방·씰 높이는 [미확정 — A50 창호도 단면 파싱 후 채움].
def subtract_windows(faces_coords, bridges, pad=200, min_w=400):
    from shapely.geometry import LineString, Polygon as SPoly
    # 창 판정: 브리지 길이 >= min_w (미세 끊김 10~400mm는 벽 연결선 — 공제 제외)
    bridges = [(a, b) for a, b in bridges
               if ((b[0]-a[0])**2 + (b[1]-a[1])**2) ** 0.5 >= min_w]
    if not bridges:
        return faces_coords, []
    zones = [LineString([a, b]).buffer(pad, cap_style=2) for a, b in bridges]
    zone_u = unary_union(zones)
    out = []
    for fc in faces_coords:
        try:
            poly = SPoly(fc)
            if not poly.is_valid:
                poly = poly.buffer(0)
            d = poly.difference(zone_u)
            geoms = list(d.geoms) if d.geom_type == "MultiPolygon" else [d]
            out += [list(g.exterior.coords) for g in geoms
                    if not g.is_empty and g.area > 0.02e6]
        except Exception:
            out.append(fc)
    openings = [{"x1": round(a[0], 1), "y1": round(a[1], 1),
                 "x2": round(b[0], 1), "y2": round(b[1], 1),
                 "width_mm": round(((b[0]-a[0])**2 + (b[1]-a[1])**2) ** 0.5)}
                for a, b in bridges]
    return out, openings

ROOT = Path(__file__).resolve().parents[2]
GEO_PATH = ROOT / "output" / "slab_precise_101동.json"
OUT_PATH = ROOT / "output" / "sketchup_build_101동.json"

# 레벨: build_101동.json levels (S30 SL 표기 실측). 기준층 피치 2830.
LEVELS = {"B2F": -9050, "B1F": -5600, "1F": 370, "2F": 3300,
          "3F": 6130, "4F": 8960, "5F": 11790, "6F": 14620, "7F": 17450,
          "8F": 20280, "9F": 23110, "10F": 25940, "11F": 28770,
          "12F": 31600, "13F": 34430, "14F": 37260, "15F": 40090,
          "PH": 43020}
TYP_PITCH = 2830
# 벽 수직 구간 관례 (방부장 교본):
#  - S-하부벽체(파랑) 블록 = 슬라브를 받치는 아래층 벽: SL(N-1)~SL(N)
#  - XR 노란 골조선 = 해당층에 서는 벽: SL(N)~SL(N+1)
WALL_SPAN = {
    "B2F": (None, -9050),      # 기초: 하단 미확정 (발자국만, 붉은플래그)
    "B1F": (-9050, -5600),     # B2F 벽 (하부벽체 블록)
    "1F": (-5600, 370),        # B1F 벽 (하부벽체 블록)
    "2F": (3300, 6130),        # 2F 골조선 벽 — 해당층 기립
    "TYP": None,               # 3F~15F 반복 배치에서 층별 산정
    "16F": (None, 43020),      # 지붕 슬라브 — 벽 데이터 미확정(옥탑 별도)
}
# 기준층 반복 대상: 3F~15F (TYP 지오메트리 재사용)
TYP_FLOORS = ["3F", "4F", "5F", "6F", "7F", "8F", "9F", "10F",
              "11F", "12F", "13F", "14F", "15F"]
# 슬라브 두께: beam_slab_floor_parsed.json 층별 최빈값 (실측 파싱 소스 명기)
SLAB_THK = {
    "B2F": (250, "beam_slab_floor_parsed.json B2F 최빈 250(16/22)"),
    "B1F": (150, "beam_slab_floor_parsed.json B1F 최빈 150(17/18)"),
    "1F": (210, "beam_slab_floor_parsed.json 1F 최빈 210(3/4)"),
    "2F": (210, "build_101동.json slab_types.unit_standard 210"),
    "TYP": (210, "build_101동.json slab_types.unit_standard 210"),
    "16F": (200, "build_101동.json slab_types.roof 200"),
}


# 수직 정합: 층별 EV코어 앵커 기준 (시트원점 방식은 B2F 1000mm 오차 유발했음)
def _shift(coords, anchor):
    ax, ay = anchor
    return [[round(x - ax, 1), round(y - ay, 1)] for x, y in coords]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    geo = json.loads(GEO_PATH.read_text(encoding="utf-8"))
    doc = ezdxf.readfile(str(DXF_S30_101))
    build = {"floors": {}}
    for fl in ("B2F", "B1F", "1F", "2F", "TYP", "16F"):
        g = geo.get(fl)
        if not g or not g.get("slab_panels"):
            continue
        anc = FLOOR_ANCHOR[fl]      # EV코어 앵커 정합 → 층 겹침
        cols = detect_columns(doc, fl) or []
        thk, thk_src = SLAB_THK[fl]
        if fl == "TYP":
            # 기준층: 3F~15F 반복 배치. 골조선 벽 = 해당층 기립(+2830)
            z_sl = None
            wz0, wz1 = None, None
            repeat = [{"floor": tf, "z_sl": LEVELS[tf],
                       "wall_z0": LEVELS[tf], "wall_z1": LEVELS[tf] + TYP_PITCH}
                      for tf in TYP_FLOORS]
        else:
            z_sl = LEVELS.get(fl, LEVELS["PH"] if fl == "16F" else None)
            wz0, wz1 = WALL_SPAN[fl]
            repeat = None
        # 창 오픈: 골조선 벽 층(2F/TYP/16F) — 브리지 구간을 벽에서 공제
        wall_faces_raw = g.get("wall_faces", [])
        win_open = []
        if fl in ("2F", "TYP", "16F"):
            fdata = collect_floor_data(doc, fl)
            wb = fdata.get("window_bridges", [])
            wall_faces_raw, win_open = subtract_windows(wall_faces_raw, wb)
        build["floors"][fl] = {
            "z_sl": z_sl,
            "repeat": repeat,
            "wall_z0": wz0,          # None = 기초(하단 미확정, 발자국만)
            "wall_z1": wz1,
            "wall_note": ("아래층 벽 (구조평면 관례: N층 시트=N-1층 벽)"
                          if wz0 is not None else
                          "기초 발자국 — 깊이 미확정, 붉은 플래그"),
            "slab_thk": thk,
            "slab_thk_source": thk_src,
            "window_bridge_count": len(win_open),
            "window_openings": [
                {**w, "x1": round(w["x1"]-anc[0], 1),
                 "y1": round(w["y1"]-anc[1], 1),
                 "x2": round(w["x2"]-anc[0], 1),
                 "y2": round(w["y2"]-anc[1], 1),
                 "note": "전높이 오픈 — 인방·씰 [미확정: A50 단면 필요]"}
                for w in win_open],
            "slabs": [{"exterior": _shift(p["exterior"], anc),
                       "holes": [_shift(h, anc) for h in p["holes"]]}
                      for p in g["slab_panels"]],
            "wall_faces": [_shift(w, anc) for w in wall_faces_raw],
            "columns": [{"cx": round(c["cx"] - anc[0], 1),
                         "cy": round(c["cy"] - anc[1], 1),
                         "w": c["w"], "h": c["h"]} for c in cols],
            "openings": [{"type": o["type"],
                          "poly": _shift(o["poly"], anc),
                          **({"angle": o["angle"]} if "angle" in o else {})}
                         for o in g.get("openings", [])],
        }
        # 1F: 해당층 기립 벽(골조선 612본) 추가 — 창구간 공제 포함
        if fl == "1F":
            sw, sw_bridges = standing_wall_faces(doc, "1F")
            sw, sw_open = subtract_windows(sw, sw_bridges)
            build["floors"][fl]["standing_walls"] = {
                "z0": 370, "z1": 3300,
                "faces": [_shift(w, anc) for w in sw],
                "window_openings": len(sw_open),
                "note": "1F 골조선 기립 벽 — 창구간 공제 적용",
            }
        # 계단: 방부장 순서 — ①오픈(정확) 유지, ②채움은 코어 도면 실측 매핑 후.
        # 코아#1 실측(2026-07-03): UP런 서측열 +Y 8단 / DN런 동측열 -Y,
        # 디딤 270x8EA, 중간참 북측 — 코어별 S30 매핑 후 형상 생성 예정.
        stair_ops = [o for o in build["floors"][fl]["openings"]
                     if o["type"] == "STAIR"]
        f = build["floors"][fl]
        ztxt = f['z_sl'] if f['z_sl'] is not None else f"반복{len(f['repeat'] or [])}개층"
        print(f"[{fl}] z={ztxt} 슬라브 {len(f['slabs'])} / "
              f"벽면 {len(f['wall_faces'])} / 기둥 {len(f['columns'])} / "
              f"개구부 {len(f['openings'])}"
              + (f" / 기립벽 {len(build['floors'][fl].get('standing_walls', {}).get('faces', []))}"
                 if fl == "1F" else "")
              + (f" / 계단개구 {len(stair_ops)} 트레드박스 "
                 f"{len(build['floors'][fl].get('stair_boxes', []))}"
                 if stair_ops else ""))
    OUT_PATH.write_text(json.dumps(build, ensure_ascii=False),
                        encoding="utf-8")
    print(f"저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
