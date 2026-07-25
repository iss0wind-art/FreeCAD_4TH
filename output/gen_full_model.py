"""
Generate full FreeCAD model script for 101dong (ASCII safe)
"""
import json, os
from pathlib import Path

data = json.loads(Path(__file__).parent.joinpath("build_101동.json").read_text(encoding="utf-8"))

lines = [
    "import FreeCAD, Part",
    "from FreeCAD import Vector",
    'doc = FreeCAD.newDocument("101dong")',
    "",
    "# LEVELS",
]

for fl, sl in sorted(data.get("levels", {}).items(), key=lambda x: str(x[1])):
    lines.append(f"# {fl}: SL={sl}mm")

# Columns (limit to 500 for stability)
lines.append("")
cols = data.get("columns", [])[:500]
lines.append(f"# COLUMNS: {len(cols)}")
lines.append('rc_g = doc.addObject("App::DocumentObjectGroup", "Columns_RC")')
for i, c in enumerate(cols):
    cx, cy = c.get("cx", 0), c.get("cy", 0)
    w, h = c.get("w", 500), c.get("h", 500)
    lines.append(f"col=Part.makeBox({w},{h},2830,Vector({cx-w/2},{cy-h/2},-5600));o=doc.addObject('Part::Feature','C{i}');o.Shape=col;rc_g.addObject(o)")

# Beams (limit to 500)
lines.append("")
beams = data.get("beams", [])[:500]
lines.append(f"# BEAMS: {len(beams)}")
lines.append('bg = doc.addObject("App::DocumentObjectGroup", "Beams_RC")')
for i, b in enumerate(beams):
    x0, y0 = b.get("x0", 0), b.get("y0", 0)
    x1, y1 = b.get("x1", 0), b.get("y1", 0)
    w, h = b.get("width", 500), b.get("height", 600)
    lines.append(f"p1=Vector({x0},{y0},-5600);p2=Vector({x1},{y1},-5600);d=p2.sub(p1);beam=Part.makeBox({w},{h},int(d.Length),Vector({x0-w/2},{y0},-5600));o=doc.addObject('Part::Feature','B{i}');o.Shape=beam;bg.addObject(o)")

# Slabs
lines.append("")
slabs = data.get("slabs", [])
lines.append(f"# SLABS: {len(slabs)}")
lines.append('sg = doc.addObject("App::DocumentObjectGroup", "Slabs")')
for i, slab in enumerate(slabs):
    pts = slab.get("pts", [])
    if len(pts) < 3:
        continue
    pts_str = ",".join(f"Vector({p[0]},{p[1]},-5600)" for p in pts)
    lines.append(f"wire=Part.makePolygon([{pts_str}]);face=Part.Face(wire);slab=face.extrude(Vector(0,0,210));o=doc.addObject('Part::Feature','S{i}');o.Shape=slab;sg.addObject(o)")

lines.append("")
lines.append("doc.recompute()")
lines.append('print(f"101dong: {len(doc.Objects)} objects")')
lines.append('import os; doc.saveAs(os.path.join(os.path.dirname(__file__), "101dong_build.fcstd"))')
lines.append('print("Saved: 101dong_build.fcstd")')

script = "\n".join(lines)
out = Path(__file__).parent / "101dong_build.py"
out.write_text(script, encoding="utf-8")
print(f"Generated: {out.name} ({len(lines)} lines, {len(cols)} cols, {len(beams)} beams, {len(slabs)} slabs)")
