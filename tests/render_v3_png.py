"""v3 STEP → 4시점 PNG 렌더."""
import os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import Part, Mesh, FreeCAD
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

STEP = r"D:/Git/FreeCAD_4TH/output/poc_v3_101.step"
STL  = r"D:/Git/FreeCAD_4TH/output/poc_v3_101.stl"
OUT  = r"D:/Git/FreeCAD_4TH/output"

t0 = time.time()
print(f'[로드] {STEP}')
shape = Part.read(STEP)
print(f'  {len(shape.Solids)} 솔리드, {shape.Volume/1e9:.3f} m³')

mesh_tup = shape.tessellate(300.0)
verts, faces = mesh_tup
m = Mesh.Mesh()
for f in faces:
    m.addFacet(FreeCAD.Vector(*verts[f[0]]), FreeCAD.Vector(*verts[f[1]]), FreeCAD.Vector(*verts[f[2]]))
m.write(STL)
print(f'[STL] {len(verts)} verts, {len(faces)} faces, {time.time()-t0:.1f}s')

V = np.array(verts) / 1000.0
F = np.array(faces)

for name, elev, azim in [('iso',30,45),('top',90,-90),('front',0,-90)]:
    fig = plt.figure(figsize=(18,12))
    ax = fig.add_subplot(111, projection='3d')
    tris = V[F]
    z_mean = tris[:,:,2].mean(axis=1)
    z_norm = (z_mean - z_mean.min()) / (z_mean.max() - z_mean.min() + 1e-9)
    colors = plt.cm.plasma(z_norm)
    poly = Poly3DCollection(tris, facecolors=colors, edgecolor='none', alpha=0.85)
    ax.add_collection3d(poly)
    ax.set_xlim(V[:,0].min(), V[:,0].max())
    ax.set_ylim(V[:,1].min(), V[:,1].max())
    ax.set_zlim(V[:,2].min(), V[:,2].max())
    try: ax.set_box_aspect((V[:,0].ptp(), V[:,1].ptp(), V[:,2].ptp()))
    except: pass
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel('X(m)'); ax.set_ylabel('Y(m)'); ax.set_zlabel('Z(m)')
    ax.set_title(f'v3 — 7248 solids, 31747 m3 | B2F z=-9050~-5600 B1F z=-5600~370 ({name})')
    out = os.path.join(OUT, f'poc_v3_101_{name}.png')
    plt.savefig(out, dpi=120, bbox_inches='tight')
    plt.close()
    print(f'  [{name}] {out}')

print(f'[종결] {time.time()-t0:.1f}s')
