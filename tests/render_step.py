"""
render_step.py — STEP → PNG 범용 렌더러 (headless)
===================================================
실행: "C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/render_step.py <STEP파일>

인자 없으면 output/ 에서 가장 최근 .step 파일을 렌더링.
출력: <STEP명>_top.png, <STEP명>_iso.png
"""
import os, sys, time, glob
os.chdir('D:/Git/FreeCAD_4TH')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, FreeCAD
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# STEP 파일 결정: 환경변수 RENDER_STEP 또는 최신 output/*.step
STEP = os.environ.get('RENDER_STEP', '')
if not STEP:
    steps = sorted(glob.glob('output/*.step'), key=os.path.getmtime)
    if not steps:
        print('[ERROR] output/*.step 없음'); sys.exit(1)
    STEP = steps[-1]

BASE = os.path.splitext(STEP)[0]
print(f'[STEP] {STEP}')
t0 = time.time()

shape = Part.read(STEP)
print(f'  솔리드 {len(shape.Solids)}개  ({time.time()-t0:.1f}s)')

print('[메시] tessellate deflection=800mm ...')
verts, faces = shape.tessellate(800.0)
V = np.array(verts) / 1000.0
F = np.array(faces)
print(f'  v={len(V)}, f={len(F)}  ({time.time()-t0:.1f}s)')
print(f'  X {V[:,0].min():.1f}~{V[:,0].max():.1f}m  '
      f'Y {V[:,1].min():.1f}~{V[:,1].max():.1f}m  '
      f'Z {V[:,2].min():.2f}~{V[:,2].max():.2f}m')

tris   = V[F]
z_mean = tris[:, :, 2].mean(axis=1)
z_norm = (z_mean - z_mean.min()) / (z_mean.max() - z_mean.min() + 1e-9)
colors = plt.cm.plasma(z_norm)

label = os.path.basename(STEP)
VIEWS = [('top', 90, -90, (14, 10)), ('iso', 30, 45, (16, 10))]

for name, elev, azim, figsize in VIEWS:
    fig = plt.figure(figsize=figsize)
    ax  = fig.add_subplot(111, projection='3d')
    poly = Poly3DCollection(tris, facecolors=colors, edgecolor='none', alpha=0.9)
    ax.add_collection3d(poly)
    ax.set_xlim(V[:,0].min(), V[:,0].max())
    ax.set_ylim(V[:,1].min(), V[:,1].max())
    ax.set_zlim(V[:,2].min(), V[:,2].max())
    try:
        ax.set_box_aspect((V[:,0].ptp(), V[:,1].ptp(), V[:,2].ptp()))
    except: pass
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)'); ax.set_zlabel('Z (m)')
    ax.set_title(f'{label} [{name.upper()}]  '
                 f'{V[:,0].ptp():.0f}x{V[:,1].ptp():.0f}x{V[:,2].ptp():.1f}m')
    out = f'{BASE}_{name}.png'
    plt.savefig(out, dpi=110, bbox_inches='tight')
    plt.close(fig)
    print(f'[PNG] {out}')

print(f'완료 ({time.time()-t0:.1f}s)')
