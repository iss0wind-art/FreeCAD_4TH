"""
Generate FreeCAD model: GRID LINES + COLUMNS only, clean tracing
"""
import math
from pathlib import Path

OUT = Path(__file__).parent

CX1, CY1, CX2, CY2 = 69013, 2241258, 229013, 2401258

L = []
L.append("import FreeCAD, Part")
L.append("from FreeCAD import Vector")
L.append('doc = FreeCAD.newDocument("101dong_frames")')
L.append("")

# Group
L.append('grid_g = doc.addObject("App::DocumentObjectGroup", "Grid")')
L.append('col_g = doc.addObject("App::DocumentObjectGroup", "Columns")')
L.append("")

# Grid lines at Z=0
for i in range(20):
    x = CX1 + i * 8000
    L.append(f"l=Part.LineSegment(Vector({x},{CY1},0),Vector({x},{CY2},0)).toShape();o=doc.addObject('Part::Feature','GX{i}');o.Shape=l;grid_g.addObject(o)")

for i in range(22):
    y = CY1 + i * 7600
    L.append(f"l=Part.LineSegment(Vector({CX1},{y},0),Vector({CX2},{y},0)).toShape();o=doc.addObject('Part::Feature','GY{i}');o.Shape=l;grid_g.addObject(o)")

# Columns at grid intersections (400x800, 3450mm tall, Z=-9050)
for ix in range(20):
    for iy in range(22):
        x = CX1 + ix * 8000
        y = CY1 + iy * 7600
        L.append(f"c=Part.makeBox(400,800,3450,Vector({x-200},{y-400},-9050));o=doc.addObject('Part::Feature','C_{ix}_{iy}');o.Shape=c;col_g.addObject(o)")

L.append("")
L.append("doc.recompute()")
L.append('print(f"Frames: grid lines + {20*22} columns")')
L.append('import os; doc.saveAs(os.path.join(os.path.dirname(__file__), "101dong_frames.fcstd"))')
L.append('print("Saved: 101dong_frames.fcstd")')

script = "\n".join(L)
out_path = OUT / "101dong_frames.py"
out_path.write_text(script, encoding="utf-8")
print(f"Generated: {out_path.name}")
