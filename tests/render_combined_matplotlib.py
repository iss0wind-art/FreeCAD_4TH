"""
통합 STEP → STL → matplotlib 3D PNG (freecadcmd 호환)
======================================================
GUI 없이 PNG 렌더링. 4 시점 (isometric, top, front, right).
"""
import os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Part, Mesh

STEP = r"D:/Git/FreeCAD_4TH/output/poc_101_combined.step"
STL = r"D:/Git/FreeCAD_4TH/output/poc_101_combined.stl"
OUT_DIR = r"D:/Git/FreeCAD_4TH/output"

t0 = time.time()
print(f'[로드] {STEP}')
shape = Part.read(STEP)
print(f'  솔리드 {len(shape.Solids)}, 부피 {shape.Volume/1e9:.3f} m³')

# tessellate → STL
print('[메시] tessellate (deflection=200mm)')
mesh_tup = shape.tessellate(200.0)
verts, faces = mesh_tup

# Mesh.Mesh로 STL 빌드
m = Mesh.Mesh()
import FreeCAD
for f in faces:
    triangle = [
        FreeCAD.Vector(*verts[f[0]]),
        FreeCAD.Vector(*verts[f[1]]),
        FreeCAD.Vector(*verts[f[2]]),
    ]
    m.addFacet(*triangle)

m.write(STL)
print(f'[STL] {STL}  vertices={len(verts)}, faces={len(faces)}, ({time.time()-t0:.1f}s)')

# matplotlib 3D 렌더
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

V = np.array(verts)  # (N, 3)
F = np.array(faces)  # (M, 3)

# 솔리드 단위 → m
V = V / 1000.0

# 시점 4개
views = [
    ('iso', 30, 45),
    ('top', 90, -90),
    ('front', 0, -90),
    ('right', 0, 0),
]

# 면 컬렉션 만들 때 효율: 임의 색상 (z 평균값으로 그라디언트)
print('[렌더] 4 시점 PNG')
for name, elev, azim in views:
    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_subplot(111, projection='3d')

    # 삼각형 좌표 배열 (M, 3, 3)
    tris = V[F]
    z_mean = tris[:, :, 2].mean(axis=1)
    z_norm = (z_mean - z_mean.min()) / (z_mean.max() - z_mean.min() + 1e-9)
    colors = plt.cm.viridis(z_norm)

    poly = Poly3DCollection(tris, facecolors=colors, edgecolor='black',
                             linewidths=0.05, alpha=0.85)
    ax.add_collection3d(poly)

    # 축 범위
    bb = V
    ax.set_xlim(bb[:, 0].min(), bb[:, 0].max())
    ax.set_ylim(bb[:, 1].min(), bb[:, 1].max())
    ax.set_zlim(bb[:, 2].min(), bb[:, 2].max())
    try:
        ax.set_box_aspect((bb[:, 0].ptp(), bb[:, 1].ptp(), bb[:, 2].ptp()))
    except Exception:
        pass

    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')
    ax.set_title(
        f'101동 + 주변 주차장 통합 — 518 솔리드, 921.851 m³ ({name})\n'
        f'BBox: {bb[:,0].ptp():.1f} × {bb[:,1].ptp():.1f} × {bb[:,2].ptp():.1f} m'
    )

    out_png = os.path.join(OUT_DIR, f'poc_101_combined_{name}.png')
    plt.savefig(out_png, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f'  [{name}] {out_png}')

print(f'\n[종결] {time.time()-t0:.1f}s')
