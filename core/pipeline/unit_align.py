"""unit_align — 세대 단위 노란 골조선 형상정합 (경계 정밀 + ICP).

방부장 방식: 노란색(color 2)이 골조선. 세대 노란선 형상으로 정합.
문제였던 것: ±사각형 분할이 인접세대 섞음, 변형(기본/확장) 차이.
해법:
  1. 세대 노란선을 창호 클러스터 bbox로 타이트하게 자름 (인접 제외)
  2. rigid_align(반사포함) 후 ICP 미세조정으로 오차 축소

[AUTO] 순수 기하 — 점군 정합. 모델 추론 없음.
"""

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.pipeline.slab_engine import _entity_lines  # noqa: E402


def _rc(e, lc):
    c = e.dxf.color
    return lc.get(e.dxf.layer, 7) if c == 256 else c


# [AUTO] 노란(color 2) 골조선 세그 수집 — 블록 재귀, bbox 클리핑
def yellow_segs(doc, x0, x1, y0, y1):
    msp = doc.modelspace()
    lc = {l.dxf.name: l.dxf.color for l in doc.layers}
    segs = []

    def scan(e):
        if e.dxftype() in ("LINE", "LWPOLYLINE") and _rc(e, lc) == 2:
            for a, b in _entity_lines(e):
                mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2
                if x0 < mx < x1 and y0 < my < y1:
                    segs.append((a, b))

    for e in msp:
        scan(e)
        if e.dxftype() == "INSERT":
            try:
                for ve in e.virtual_entities():
                    scan(ve)
                    if ve.dxftype() == "INSERT":
                        for v2 in ve.virtual_entities():
                            scan(v2)
            except Exception:
                pass
    return segs


def _pts(segs):
    return np.array([p for a, b in segs for p in (a, b)]) if segs else \
        np.empty((0, 2))


# [AUTO] ICP 미세조정 — 초기 (R,t)에서 최근접 대응 Kabsch 반복
def icp(src, dst, R0, t0, iters=8):
    R, t = R0.copy(), t0.copy()
    dsamp = dst if len(dst) <= 2000 else dst[
        np.random.default_rng(0).choice(len(dst), 2000, replace=False)]
    for _ in range(iters):
        pT = src @ R.T + t
        # 최근접 대응
        idx = np.argmin(((pT[:, None, :] - dsamp[None, :, :]) ** 2).sum(2), 1)
        q = dsamp[idx]
        # 이상치 제거 (거리 상위 20%)
        d = np.sqrt(((pT - q) ** 2).sum(1))
        keep = d <= np.quantile(d, 0.8)
        P, Q = pT[keep], q[keep]
        pc, qc = P.mean(0), Q.mean(0)
        H = (P - pc).T @ (Q - qc)
        U, _, Vt = np.linalg.svd(H)
        dR = Vt.T @ U.T
        if np.linalg.det(dR) < 0:
            Vt[-1] *= -1
            dR = Vt.T @ U.T
        R = dR @ R
        t = qc - dR @ pc + dR @ t
    final = src @ R.T + t
    err = np.sqrt(((final[:, None, :] - dsamp[None, :, :]) ** 2)
                  .sum(2)).min(1).mean()
    return R, t, err


# [AUTO] 세대 정합 — A30 세대 노란선 → S30 세대위치 노란선
def align_unit(a30_segs, s30_segs):
    from core.pipeline.sheet_align import rigid_align
    src, dst = _pts(a30_segs), _pts(s30_segs)
    if len(src) < 10 or len(dst) < 10:
        return None
    R, t, err0, ang = rigid_align(src, dst)
    R, t, err = icp(src, dst, R, t)
    return {"R": R, "t": t, "err_mm": round(err),
            "err0_mm": round(err0),
            "angle_deg": round(math.degrees(math.atan2(R[1, 0], R[0, 0])), 1),
            "n_src": len(src), "n_dst": len(dst)}
