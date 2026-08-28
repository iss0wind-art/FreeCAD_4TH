"""
Generate clean FreeCAD model with proper filtering
Matched to codex + validated member specs
"""
import json, math
from pathlib import Path
from collections import defaultdict

data = json.loads(Path(__file__).parent.joinpath("build_101동.json").read_text(encoding="utf-8"))

cols = data.get("columns", [])
beams = data.get("beams", [])
walls = data.get("walls", [])
slabs = data.get("slabs", [])
levels = data.get("levels", {})

# Filter 1: Columns with reasonable size (400~1500mm, typical parking column)
real_cols = []
for c in cols:
    w, h = c.get("w", 0), c.get("h", 0)
    if 300 <= w <= 2000 and 300 <= h <= 2000:
        # Remove extreme outliers
        if abs(w - h) < 1500:
            real_cols.append(c)

# Filter 2: Beams with realistic span (3~12m) and known WxH
codex_widths = {400, 500, 600, 700, 800, 900, 1000, 1100, 1200}
codex_heights = {600, 700, 800, 900, 1000, 1200, 1250, 1400, 1500}

real_beams = []
for b in beams:
    w, h = b.get("width", 0), b.get("height", 0)
    dx = b.get("x1", 0) - b.get("x0", 0)
    dy = b.get("y1", 0) - b.get("y0", 0)
    l = math.hypot(dx, dy)
    
    # Must have realistic span AND codex-matching dimensions
    if 3000 <= l <= 15000:
        # Round to nearest 100
        wr = round(w / 100) * 100
        hr = round(h / 100) * 100
        if wr in codex_widths and hr in codex_heights:
            real_beams.append(b)

# Filter 3: Walls with reasonable thickness
real_walls = []
for w in walls:
    t = w.get("thickness", 0)
    l = w.get("length", 0)
    if 150 <= t <= 600 and l > 1000:
        real_walls.append(w)

# Limit all to manageable count
real_cols = real_cols[:400]
real_beams = real_beams[:400]
real_walls = real_walls[:200]

print(f"Filtered: {len(cols)}→{len(real_cols)} cols, {len(beams)}→{len(real_beams)} beams, {len(walls)}→{len(real_walls)} walls")

L = []
L.append("import FreeCAD, Part")
L.append("from FreeCAD import Vector")
L.append('doc = FreeCAD.newDocument("101dong_filtered")')
L.append("")

for fl, sl in sorted(levels.items(), key=lambda x: str(x[1])):
    L.append(f"# {fl}: SL={sl}mm")

# COLLECT (do all first, then addObject)
L.append("")

# Columns
L.append(f"# COLUMNS: {len(real_cols)}")
L.append("rc_g = doc.addObject('App::DocumentObjectGroup', 'Columns')")
for i, c in enumerate(real_cols):
    cx, cy = c.get("cx", 0), c.get("cy", 0)
    w, h = c.get("w", 500), c.get("h", 500)
    L.append(f"col=Part.makeBox({w},{h},3450,Vector({cx-w/2},{cy-h/2},-9050));o=doc.addObject('Part::Feature','C{i}');o.Shape=col;rc_g.addObject(o)")

# Beams
L.append(f"# BEAMS: {len(real_beams)}")
L.append("bg = doc.addObject('App::DocumentObjectGroup', 'Beams')")
for i, b in enumerate(real_beams):
    x0,y0 = b.get("x0",0),b.get("y0",0)
    x1,y1 = b.get("x1",0),b.get("y1",0)
    w,h = b.get("width",500),b.get("height",600)
    L.append(f"p1=Vector({x0},{y0},-5600);p2=Vector({x1},{y1},-5600);d=p2.sub(p1);bm=Part.makeBox({w},{h},int(d.Length),Vector({x0-w/2},{y0},-5600));o=doc.addObject('Part::Feature','B{i}');o.Shape=bm;bg.addObject(o)")

# Slabs
L.append(f"# SLABS: {len(slabs)}")
L.append("sg = doc.addObject('App::DocumentObjectGroup', 'Slabs')")
for i, slab in enumerate(slabs):
    pts = slab.get("pts", [])
    if len(pts) < 3: continue
    pts_str = ",".join(f"Vector({p[0]},{p[1]},-5600)" for p in pts)
    L.append(f"wire=Part.makePolygon([{pts_str}]);face=Part.Face(wire);sl=face.extrude(Vector(0,0,210));o=doc.addObject('Part::Feature','S{i}');o.Shape=sl;sg.addObject(o)")

# Walls
L.append(f"# WALLS: {len(real_walls)}")
L.append("wg = doc.addObject('App::DocumentObjectGroup', 'Walls')")
for i, w in enumerate(real_walls):
    p1=p2=w.get("p1",[0,0]); p2=w.get("p2",[0,0])
    t=w.get("thickness",200)
    L.append(f"wl=Part.makeBox({t},{w.get('length',3000)},3450,Vector({p1[0]},{p1[1]},-9050));o=doc.addObject('Part::Feature','W{i}');o.Shape=wl;wg.addObject(o)")

L.append("")
L.append("doc.recompute()")
L.append('print(f"Filtered model: {len(doc.Objects)} objects")')
L.append('import os; doc.saveAs(os.path.join(os.path.dirname(__file__), "101dong_filtered.fcstd"))')
L.append('print("Saved: 101dong_filtered.fcstd")')

script = "\n".join(L)
p = Path(__file__).parent / "101dong_filtered.py"
p.write_text(script, encoding="utf-8")
print(f"Generated: {p.name}")
