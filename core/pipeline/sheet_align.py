"""sheet_align — 도면 세트 간 좌표 정합 (S30 구조 ↔ A40 건축).

방부장 워크플로 2026-07-05:
  골조선 끊긴 곳(S30) = 창/문 위치 → 그 자리 창호부호(A40) → 크기(A50).
  S30·A40 좌표계가 다르므로 정합이 관문. 양 도면의 동일 건물(101동 기준층)
  골조선(A-WALL-RC 노랑)을 형상 정합(Kabsch/PCA)해 변환 T를 산출.

[AUTO] 순수 기하 — 점군 정합. 회전+평행이동(강체). 모델 추론 없음.
검증: EV·계단 코어 대응 오차 mm 출력.
"""

import math
import sys
from pathlib import Path

import ezdxf
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import (  # noqa: E402
    SHEETS, SHEET_Y, collect_floor_data)

ROOT = Path(__file__).resolve().parents[2]
_DRAW = next((p for p in [ROOT / "input_drawings",
                          Path(r"D:\Git\FreeCAD_4TH\input_drawings")]
              if p.exists()), None)
DXF_S30 = _DRAW / "S30-001~010-101동 구조평면도.dxf"
DXF_A40 = _DRAW / "A40-003~237 101동~108동 평면도.dxf"

# A40 101동 기준층 시트 대역 (타이틀 593176,1348376 기준)
A40_TYP_ZONE = (530000, 656000, 1345000, 1412000)


def _seg_pts(e):
    if e.dxftype() == "LINE":
        return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    if e.dxftype() == "LWPOLYLINE":
        return [(p[0], p[1]) for p in e.get_points()]
    return []


# [AUTO] A40 기준층 골조선(A-WALL-RC 노랑) 점군 — 재귀 explode
def a40_wall_points(doc):
    msp = doc.modelspace()
    x0, x1, y0, y1 = A40_TYP_ZONE
    pts = []

    def walk(e, depth):
        if e.dxftype() == "INSERT" and depth < 4:
            try:
                for s in e.virtual_entities():
                    walk(s, depth + 1)
            except Exception:
                pass
            return
        lay = e.dxf.layer.split("$0$")[-1]
        if lay != "A-WALL-RC":
            return
        for p in _seg_pts(e):
            if x0 < p[0] < x1 and y0 < p[1] < y1:
                pts.append(p)

    for ins in msp.query("INSERT"):
        if "XR101" in ins.dxf.name and "기준" in ins.dxf.name:
            walk(ins, 0)
    return np.array(pts) if pts else np.empty((0, 2))


# [AUTO] S30 기준층 골조선 점군
def s30_wall_points(doc):
    data = collect_floor_data(doc, "TYP")
    segs = data.get("standing_wall_segs", [])
    pts = []
    for a, b in segs:
        pts.append(a)
        pts.append(b)
    return np.array(pts)


# [AUTO] 강체 정합 — centroid + PCA 주축(4방향 후보) → 최소 최근접거리
def rigid_align(src, dst):
    """src 점군을 dst 점군에 맞추는 강체변환 (R, t) 산출.

    회전은 PCA 주축 정렬 + 4방향(0/180 × 반사) 후보 중 최근접합 최소 채택.
    반환: (R 2x2, t 2, 평균최근접오차mm, 후보각도).
    """
    cs, cd = src.mean(0), dst.mean(0)
    S, D = src - cs, dst - cd

    def pca_angle(P):
        cov = np.cov(P.T)
        w, v = np.linalg.eigh(cov)
        major = v[:, np.argmax(w)]
        return math.atan2(major[1], major[0])

    a_s, a_d = pca_angle(S), pca_angle(D)
    # dst 최근접 조회용 그리드 (샘플링)
    dsamp = D[np.random.default_rng(0).choice(
        len(D), min(len(D), 1500), replace=False)] if len(D) > 1500 else D

    best = None
    for extra in (0, math.pi):
        ang = a_d - a_s + extra
        R = np.array([[math.cos(ang), -math.sin(ang)],
                      [math.sin(ang), math.cos(ang)]])
        Srot = S @ R.T
        # 평균 최근접거리 (Srot → dsamp)
        ssub = Srot[np.random.default_rng(1).choice(
            len(Srot), min(len(Srot), 1500), replace=False)] \
            if len(Srot) > 1500 else Srot
        d = np.sqrt(((ssub[:, None, :] - dsamp[None, :, :]) ** 2)
                    .sum(2)).min(1).mean()
        if best is None or d < best[0]:
            best = (d, R, ang)
    err, R, ang = best
    t = cd - R @ cs
    return R, t, err, math.degrees(ang)


def make_transform():
    s30 = ezdxf.readfile(str(DXF_S30))
    a40 = ezdxf.readfile(str(DXF_A40))
    src = s30_wall_points(s30)          # S30 골조선
    dst = a40_wall_points(a40)          # A40 골조선
    R, t, err, ang = rigid_align(src, dst)
    return {"R": R, "t": t, "err_mm": err, "angle_deg": ang,
            "n_s30": len(src), "n_a40": len(dst)}


def s30_to_a40(pt, tr):
    v = tr["R"] @ np.array([pt[0], pt[1]]) + tr["t"]
    return (float(v[0]), float(v[1]))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tr = make_transform()
    print("=== S30 → A40 좌표 정합 (골조선 형상 강체정합) ===")
    print(f"  S30 골조선점 {tr['n_s30']} / A40 골조선점 {tr['n_a40']}")
    print(f"  회전 {tr['angle_deg']:.2f}° / 평균 최근접오차 {tr['err_mm']:.0f}mm")
    # 검증: S30 EV 3점 → A40 변환 후 A40 ELEV 텍스트와 거리
    from core.pipeline.slab_engine import pair_x_marks
    s30 = ezdxf.readfile(str(DXF_S30))
    data = collect_floor_data(s30, "TYP")
    evs = [(m["cx"], m["cy"]) for m in pair_x_marks(data["diag_all"])
           if m["kind"] == "EV"]
    a40_elev = [(567356, 1301899), (575930, 1374222), (565188, 1392387)]
    print("  EV 검증 (S30 EV → A40 변환 vs A40 ELEV 텍스트):")
    for ev in evs:
        pa = s30_to_a40(ev, tr)
        d = min(math.hypot(pa[0]-e[0], pa[1]-e[1]) for e in a40_elev)
        print(f"    S30({ev[0]:.0f},{ev[1]:.0f}) → A40({pa[0]:.0f},{pa[1]:.0f}) "
              f"최근접ELEV {d:.0f}mm")
    return tr


if __name__ == "__main__":
    main()
