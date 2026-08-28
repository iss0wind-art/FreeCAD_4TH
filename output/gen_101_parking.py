"""
Generate FreeCAD model: 101dong building + surrounding parking
"""
import json
from pathlib import Path

data = json.loads(Path(__file__).parent.joinpath("build_101동.json").read_text(encoding="utf-8"))
levels = data.get("levels", {})
cols = data.get("columns", [])
beams = data.get("beams", [])
walls = data.get("walls", [])
slabs = data.get("slabs", [])

L = []
L.append('import FreeCAD, Part, Mesh')
L.append('from FreeCAD import Vector')
L.append('import math')
L.append('doc = FreeCAD.newDocument("101dong_parking")')
L.append('')

# No coordinate offset - use original coords
# FreeCAD viewFit will handle zooming
L.append('')

def v(x, y, z):
    return f"Vector({x},{y},{z})"

# Levels
for fl, sl in sorted(levels.items(), key=lambda x: str(x[1])):
    L.append(f'# {fl}: SL={sl}mm')

# Include all data - FreeCAD viewFit handles zoom

# ---- COLUMNS ----
rc_cols = cols
L.append(f'# COLUMNS: {len(rc_cols)}')
L.append('rc_g = doc.addObject("App::DocumentObjectGroup", "Columns_RC")')
for i, c in enumerate(rc_cols[:800]):
    cx, cy, w, h = c.get("cx", 0), c.get("cy", 0), c.get("w", 500), c.get("h", 500)
    L.append(f'c=Part.makeBox({w},{h},2830,{v(cx-w/2,cy-h/2,-5600)});o=doc.addObject("Part::Feature","C{i}");o.Shape=c;rc_g.addObject(o)')

# ---- BEAMS ----
rc_beams = beams
L.append(f'# BEAMS: {len(rc_beams)}')
L.append('bg = doc.addObject("App::DocumentObjectGroup", "Beams_RC")')
for i, b in enumerate(rc_beams[:800]):
    x0, y0 = b.get("x0", 0), b.get("y0", 0)
    x1, y1 = b.get("x1", 0), b.get("y1", 0)
    w, h = b.get("width", 500), b.get("height", 600)
    L.append(f'p1={v(x0,y0,-5600)};p2={v(x1,y1,-5600)};d=p2.sub(p1);bm=Part.makeBox({w},{h},int(d.Length),{v(x0-w/2,y0,-5600)});o=doc.addObject("Part::Feature","B{i}");o.Shape=bm;bg.addObject(o)')

# ---- SLABS ----
L.append(f'# SLABS: {len(slabs)}')
L.append('sg = doc.addObject("App::DocumentObjectGroup", "Slabs")')
for i, slab in enumerate(slabs):
    pts = slab.get("pts", [])
    if len(pts) < 3: continue
    pts_str = ",".join(v(p[0],p[1],-5600) for p in pts)
    L.append(f'wire=Part.makePolygon([{pts_str}]);face=Part.Face(wire);sl=face.extrude(Vector(0,0,210));o=doc.addObject("Part::Feature","S{i}");o.Shape=sl;sg.addObject(o)')

# ---- WALLS (shear walls around core) ----
rc_walls = walls
L.append(f'# WALLS: {len(rc_walls)}')
L.append('wg = doc.addObject("App::DocumentObjectGroup", "Walls")')
for i, w in enumerate(rc_walls[:300]):
    p1, p2 = w.get("p1", [0,0]), w.get("p2", [0,0])
    t = w.get("thickness", 200)
    L.append(f'wl=Part.makeBox({t},{w.get("length",3000)},3450,{v(p1[0],p1[1],-9050)});o=doc.addObject("Part::Feature","W{i}");o.Shape=wl;wg.addObject(o)')

L.append('')
L.append('doc.recompute()')

L.append('print(f"101dong+parking: {len(doc.Objects)} objects")')
L.append('import os; doc.saveAs(os.path.join(os.path.dirname(__file__), "101dong_parking.fcstd"))')
L.append('print("Saved: 101dong_parking.fcstd")')

script = "\n".join(L)
out_path = Path(__file__).parent / "101dong_parking.py"
out_path.write_text(script, encoding="utf-8")
print(f"Generated: {out_path.name}")
print(f"  Columns: {len(rc_cols)}")
print(f"  Beams: {len(rc_beams)}")
print(f"  Walls: {len(rc_walls)}")
print(f"  Slabs: {len(slabs)}")
