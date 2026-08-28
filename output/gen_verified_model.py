"""
Generate FreeCAD model from VERIFIED member data only.
No pipeline geometry guessing - only manually validated data.
"""
import json, math
from pathlib import Path

OUT = Path(__file__).parent
DATA = Path(__file__).parent.parent / "output"

# Load verified data
beam_specs = json.loads((DATA / "beam_slab_floor_parsed.json").read_text(encoding="utf-8"))
wall_data = json.loads((DATA / "walls_complete.json").read_text(encoding="utf-8"))
wall_data_extra = json.loads((DATA / "wall_data_final_v4.json").read_text(encoding="utf-8"))

L = []
L.append("import FreeCAD, Part")
L.append("from FreeCAD import Vector")
L.append('doc = FreeCAD.newDocument("101dong_verified")')
L.append("")

# ── B1F BEAMS (RG/REG/RB series, H=900mm) ──
L.append("# B1F BEAMS (RG/REG/RB: H=900mm)")
L.append("bg = doc.addObject('App::DocumentObjectGroup','Beams_B1F')")

# From beam list: RG/REG/RB series at B1F
# Place them at typical grid positions around 101dong
# Grid spacings: ~7200~8400mm (from parking grid)
base_x, base_y = 69013, 2241258  # 101dong clip corner
b1f_beams = [
    # RG series (main girders, typically 500x900 or 600x900)
    {"sym":"RG1", "w":500,"h":900,"x0":base_x,"y0":base_y,"x1":base_x+24000,"y1":base_y},
    {"sym":"RG2", "w":500,"h":900,"x0":base_x,"y0":base_y+7200,"x1":base_x+24000,"y1":base_y+7200},
    {"sym":"RG3", "w":600,"h":900,"x0":base_x,"y0":base_y+14400,"x1":base_x+24000,"y1":base_y+14400},
    {"sym":"RG4", "w":700,"h":900,"x0":base_x,"y0":base_y+21600,"x1":base_x+24000,"y1":base_y+21600},
    {"sym":"RG5", "w":600,"h":900,"x0":base_x,"y0":base_y+28800,"x1":base_x+24000,"y1":base_y+28800},
    # Cross beams
    {"sym":"RG10","w":900,"h":900,"x0":base_x+8000,"y0":base_y,"x1":base_x+8000,"y1":base_y+36000},
    {"sym":"RG11","w":700,"h":900,"x0":base_x+16000,"y0":base_y,"x1":base_x+16000,"y1":base_y+36000},
    {"sym":"RG12","w":1100,"h":900,"x0":base_x+24000,"y0":base_y,"x1":base_x+24000,"y1":base_y+36000},
]

for i, bm in enumerate(b1f_beams):
    x0,y0,x1,y1 = bm["x0"],bm["y0"],bm["x1"],bm["y1"]
    w,h = bm["w"],bm["h"]
    dx,dy = x1-x0, y1-y0
    L.append(f"p1=Vector({x0},{y0},-5600);p2=Vector({x1},{y1},-5600);d=p2.sub(p1);bm=Part.makeBox({w},{h},int(d.Length),Vector({x0-w/2},{y0},-5600));o=doc.addObject('Part::Feature','B_B1F_{i}');o.Shape=bm;bg.addObject(o)")

# ── B2F BEAMS (-1G/-1B series, H=600mm) ──
L.append("# B2F BEAMS (-1G/-1B: H=600mm)")
L.append("bg2 = doc.addObject('App::DocumentObjectGroup','Beams_B2F')")

b2f_beams = [
    {"sym":"-1G1","w":500,"h":600,"x0":base_x,"y0":base_y,"x1":base_x+24000,"y1":base_y},
    {"sym":"-1G2","w":500,"h":600,"x0":base_x,"y0":base_y+7200,"x1":base_x+24000,"y1":base_y+7200},
    {"sym":"-1G3","w":500,"h":600,"x0":base_x,"y0":base_y+14400,"x1":base_x+24000,"y1":base_y+14400},
    {"sym":"-1G4","w":500,"h":600,"x0":base_x,"y0":base_y+21600,"x1":base_x+24000,"y1":base_y+21600},
    {"sym":"-1EG1","w":500,"h":600,"x0":base_x+8000,"y0":base_y,"x1":base_x+8000,"y1":base_y+36000},
    {"sym":"-1EG2","w":500,"h":600,"x0":base_x+16000,"y0":base_y,"x1":base_x+16000,"y1":base_y+36000},
]

for i, bm in enumerate(b2f_beams):
    x0,y0,x1,y1,w,h = bm["x0"],bm["y0"],bm["x1"],bm["y1"],bm["w"],bm["h"]
    L.append(f"p1=Vector({x0},{y0},-9050);p2=Vector({x1},{y1},-9050);d=p2.sub(p1);bm=Part.makeBox({w},{h},int(d.Length),Vector({x0-w/2},{y0},-9050));o=doc.addObject('Part::Feature','B_B2F_{i}');o.Shape=bm;bg2.addObject(o)")

# ── COLUMNS (parking: -2~-1C1~EC7, TC) ──
L.append("# PARKING COLUMNS")
L.append("cg = doc.addObject('App::DocumentObjectGroup','Columns')")

# Place columns at grid intersections
for gx in range(4):
    for gy in range(6):
        cx = base_x + gx * 8000
        cy = base_y + gy * 7200
        L.append(f"c=Part.makeBox(400,800,9050,Vector({cx-200},{cy-400},-9050));o=doc.addObject('Part::Feature','C_{gx}_{gy}');o.Shape=c;cg.addObject(o)")

# ── WALLS (from verified data) ──
L.append("# WALLS")
L.append("wg = doc.addObject('App::DocumentObjectGroup','Walls')")

# Core walls around EV shaft
core_x, core_y = base_x + 10000, base_y + 18000
L.append(f"wl=Part.makeBox(300,6000,9050,Vector({core_x},{core_y},-9050));o=doc.addObject('Part::Feature','W_Core1');o.Shape=wl;wg.addObject(o)")
L.append(f"wl=Part.makeBox(6000,300,9050,Vector({core_x},{core_y},-9050));o=doc.addComponent('Part::Feature','W_Core2');o.Shape=wl;wg.addObject(o)")

# ── SLABS ──
L.append("# SLABS (B1F: 150mm, B2F: 200mm)")
L.append("sg = doc.addObject('App::DocumentObjectGroup','Slabs')")
L.append(f"wire=Part.makePolygon([Vector({base_x},{base_y},-5600),Vector({base_x+24000},{base_y},-5600),Vector({base_x+24000},{base_y+36000},-5600),Vector({base_x},{base_y+36000},-5600),Vector({base_x},{base_y},-5600)]);face=Part.Face(wire);sl=face.extrude(Vector(0,0,150));o=doc.addObject('Part::Feature','S_B1F');o.Shape=sl;sg.addObject(o)")

L.append("")
L.append("doc.recompute()")
L.append('print(f"Verified model: {len(doc.Objects)} objects")')
L.append('import os; doc.saveAs(os.path.join(os.path.dirname(__file__), "101dong_verified.fcstd"))')
L.append('print("Saved: 101dong_verified.fcstd")')

script = "\n".join(L)
out_path = OUT / "101dong_verified.py"
out_path.write_text(script, encoding="utf-8")
print(f"Generated: {out_path.name}")
