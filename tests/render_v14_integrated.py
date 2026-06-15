"""
render_v14_integrated.py — v4 정합 STEP → 4방향 PNG 렌더링
=========================================================
matplotlib headless 렌더 (freecadcmd 환경).

산출:
  output/v14_integrated_iso.png   — 등각투영 (30°, 45°)
  output/v14_integrated_top.png   — 평면 (90°, -90°)

실행:
  "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/render_v14_integrated.py
"""
import os, sys, time
os.chdir('D:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, FreeCAD
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

STEP = 'output/v14_integrated.step'

print(f'[로드] {STEP}')
t0 = time.time()
shape = Part.read(STEP)
print(f'  솔리드 {len(shape.Solids)}개 ({time.time()-t0:.1f}s)')

print('[메시] tessellate deflection=200mm ...')
t1 = time.time()
verts, faces = shape.tessellate(200.0)
V = np.array(verts) / 1000.0
F = np.array(faces)
print(f'  v={len(V)}, f={len(F)} ({time.time()-t1:.1f}s)')
print(f'  X: {V[:,0].min():.1f}m ~ {V[:,0].max():.1f}m')
print(f'  Y: {V[:,1].min():.1f}m ~ {V[:,1].max():.1f}m')
print(f'  Z: {V[:,2].min():.1f}m ~ {V[:,2].max():.1f}m')

tris = V[F]
# Z값으로 색칠 (지층 시각화)
z_mean = tris[:, :, 2].mean(axis=1)
z_norm = (z_mean - z_mean.min()) / (z_mean.max() - z_mean.min() + 1e-9)
colors = plt.cm.viridis(z_norm)

VIEWS = [
    ('iso',   30,   45),
    ('top',   90,  -90),
]

n_solids = len(shape.Solids)
title_base = f'v14 정밀 통합 — 101동+인접주차장 (솔리드 {n_solids}개)'

for name, elev, azim in VIEWS:
    fig = plt.figure(figsize=(18, 12))
    ax = fig.add_subplot(111, projection='3d')
    poly = Poly3DCollection(tris, facecolors=colors, edgecolor='none', alpha=0.9)
    ax.add_collection3d(poly)
    ax.set_xlim(V[:,0].min(), V[:,0].max())
    ax.set_ylim(V[:,1].min(), V[:,1].max())
    ax.set_zlim(V[:,2].min(), V[:,2].max())
    try:
        ax.set_box_aspect((V[:,0].ptp(), V[:,1].ptp(), V[:,2].ptp()))
    except Exception:
        pass
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)'); ax.set_zlabel('Z (m)')
    ax.set_title(f'{title_base}\n뷰: {name.upper()} (elev={elev}, azim={azim})  '
                 f'| 영역 {V[:,0].ptp():.0f}m × {V[:,1].ptp():.0f}m × {V[:,2].ptp():.2f}m')
    out = f'output/v14_integrated_{name}.png'
    plt.savefig(out, dpi=100, bbox_inches='tight')
    plt.close(fig)
    print(f'[PNG] {out}')

print(f'완료, 총 {time.time()-t0:.1f}s')
