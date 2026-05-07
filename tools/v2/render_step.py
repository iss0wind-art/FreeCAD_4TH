"""
render_step.py — STEP → 4뷰 PNG (v4)
======================================
환경변수:
  V2_STEP — STEP 파일 경로
  V2_OUT_DIR — PNG 출력 디렉토리
"""
import os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import Part
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

STEP = os.environ.get("V2_STEP")
OUT_DIR = Path(os.environ.get("V2_OUT_DIR", "."))
OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"[로드] {STEP}")
t0 = time.time()
shape = Part.read(STEP)
print(f"  솔리드 {len(shape.Solids)}개  ({time.time()-t0:.1f}s)")

print("[메시] tessellate deflection=300 ...")
t1 = time.time()
verts, faces = shape.tessellate(300.0)
V = np.array(verts) / 1000.0
F = np.array(faces)
print(f"  v={len(V)}, f={len(F)}  ({time.time()-t1:.1f}s)")
print(f"  X: {V[:,0].min():.1f}m ~ {V[:,0].max():.1f}m  ({V[:,0].ptp():.1f}m)")
print(f"  Y: {V[:,1].min():.1f}m ~ {V[:,1].max():.1f}m  ({V[:,1].ptp():.1f}m)")
print(f"  Z: {V[:,2].min():.2f}m ~ {V[:,2].max():.2f}m  ({V[:,2].ptp():.2f}m)")

tris = V[F]
z_mean = tris[:, :, 2].mean(axis=1)
z_norm = (z_mean - z_mean.min()) / (z_mean.max() - z_mean.min() + 1e-9)
colors = plt.cm.viridis(z_norm)

VIEWS = [("iso", 30, 45), ("top", 90, -90), ("north", 0, -90), ("east", 0, 0)]

n_solids = len(shape.Solids)
title = f"v4 PKG — {n_solids} solids"

for name, elev, azim in VIEWS:
    fig = plt.figure(figsize=(18, 12))
    ax = fig.add_subplot(111, projection="3d")
    poly = Poly3DCollection(tris, facecolors=colors, edgecolor="none", alpha=0.9)
    ax.add_collection3d(poly)
    ax.set_xlim(V[:,0].min(), V[:,0].max())
    ax.set_ylim(V[:,1].min(), V[:,1].max())
    ax.set_zlim(V[:,2].min(), V[:,2].max())
    try:
        ax.set_box_aspect((V[:,0].ptp(), V[:,1].ptp(), V[:,2].ptp()))
    except Exception:
        pass
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")
    ax.set_title(f"{title} | {name.upper()} (elev={elev}, azim={azim})")
    out = OUT_DIR / f"v4_{name}.png"
    plt.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"[PNG] {out}")

print(f"완료 {time.time()-t0:.1f}s")
