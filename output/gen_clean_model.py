"""
Generate clean FreeCAD model - only realistic beams/columns
"""
import json, math
from pathlib import Path

data = json.loads(Path(__file__).parent.joinpath("build_101동.json").read_text(encoding="utf-8"))
cols = data.get("columns", [])
beams = data.get("beams", [])
walls = data.get("walls", [])
slabs = data.get("slabs", [])
levels = data.get("levels", {})

# Filter: only reasonable beams (2m~15m = realistic span)
real_beams = []
for b in beams:
    dx = b.get("x1", 0) - b.get("x0", 0)
    dy = b.get("y1", 0) - b.get("y0", 0)
    l = math.hypot(dx, dy)
    if 2000 <= l <= 15000:
        real_beams.append(b)

# Filter: reasonable columns (not too small, not too large)
real_cols = [c for c in cols if 200 <= c.get("w", 0) <= 2000 and 200 <= c.get("h", 0) <= 2000]

# Limit counts for FreeCAD
real_cols = real_cols[:500]
real_beams = real_beams[:500]
real_walls = walls[:200]

L = []
L.append("import FreeCAD, Part")
L.append("from FreeCAD import Vector")
L.append('doc = FreeCAD.newDocument("101dong_clean")')
L.append("")

# Levels
for fl, sl in sorted(levels.items(), key=lambda x: str(x[1])):
    L.append(f"# {fl}: SL={sl}mm")

# Columns
L.append(f"# COLUMNS: {len(real_cols)} (filtered)")
L.append('rc_g = doc.addObject("App::DocumentObjectGroup", "Columns_RC")')
for i, c in enumerate(real_cols):
    cx, cy, w, h = c.get("cx", 0), c.get("cy", 0), c.get("w", 500), c.get("h", 500)
    L.append(f"c=Part.makeBox({w},{h},2830,Vector({cx-w/2},{cy-h/2},-5600));o=doc.addObject('Part::Feature','C{i}');o.Shape=c;rc_g.addObject(o)")

# Beams (filtered)
L.append(f"# BEAMS: {len(real_beams)} (2~15m filter)")
L.append('bg = doc.addObject("App::DocumentObjectGroup", "Beams_RC")')
for i, b in enumerate(real_beams):
    x0, y0 = b.get("x0", 0), b.get("y0", 0)
    x1, y1 = b.get("x1", 0), b.get("y1", 0)
    w, h = b.get("width", 500), b.get("height", 600)
    dx, dy = x1 - x0, y1 - y0
    L.append(f"p1=Vector({x0},{y0},-5600);p2=Vector({x1},{y1},-5600);d=p2.sub(p1);bm=Part.makeBox({w},{h},int(d.Length),Vector({x0-w/2},{y0},-5600));o=doc.addObject('Part::Feature','B{i}');o.Shape=bm;bg.addObject(o)")

# Slabs
L.append(f"# SLABS: {len(slabs)}")
L.append('sg = doc.addObject("App::DocumentObjectGroup", "Slabs")')
for i, slab in enumerate(slabs):
    pts = slab.get("pts", [])
    if len(pts) < 3: continue
    pts_str = ",".join(f"Vector({p[0]},{p[1]},-5600)" for p in pts)
    L.append(f"wire=Part.makePolygon([{pts_str}]);face=Part.Face(wire);sl=face.extrude(Vector(0,0,210));o=doc.addObject('Part::Feature','S{i}');o.Shape=sl;sg.addObject(o)")

# Walls
L.append(f"# WALLS: {len(real_walls)} (limited)")
L.append('wg = doc.addObject("App::DocumentObjectGroup", "Walls")')
for i, w in enumerate(real_walls):
    p1, p2 = w.get("p1", [0,0]), w.get("p2", [0,0])
    t = w.get("thickness", 200)
    L.append(f"wl=Part.makeBox({t},{w.get('length',3000)},3450,Vector({p1[0]},{p1[1]},-9050));o=doc.addObject('Part::Feature','W{i}');o.Shape=wl;wg.addObject(o)")

L.append("")
L.append("doc.recompute()")
L.append('print(f"Clean model: {len(doc.Objects)} objects")')
L.append('import os; doc.saveAs(os.path.join(os.path.dirname(__file__), "101dong_clean.fcstd"))')
L.append('print("Saved: 101dong_clean.fcstd")')

script = "\n".join(L)
out_path = Path(__file__).parent / "101dong_clean.py"
out_path.write_text(script, encoding="utf-8")
print(f"Generated: {out_path.name}")
print(f"  Columns: {len(real_cols)}")
print(f"  Beams: {len(real_beams)} (from {len(beams)})")
print(f"  Walls: {len(real_walls)} (from {len(walls)})")
print(f"  Slabs: {len(slabs)}")
