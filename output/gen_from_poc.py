"""
Generate FreeCAD model from PREVIOUS working pipeline output (poc_v3_101)
This produced 7,248 solids correctly in the past.
"""
import json
from pathlib import Path

poc = json.loads(Path(__file__).parent.joinpath("poc_v3_101.json").read_text(encoding="utf-8"))

L = []
L.append("import FreeCAD, Part")
L.append("from FreeCAD import Vector")
L.append('doc = FreeCAD.newDocument("101dong_poc")')
L.append("")

total_solids = 0

for sheet in poc.get("sheets", []):
    title = sheet.get("title", "?")
    z_bottom = sheet.get("z_floor_bottom", -9050)
    z_top = sheet.get("z_floor_top", -5600)
    
    L.append(f"# === {title} === (z={z_bottom}~{z_top})")
    
    sg_name = f"Slab_{title[:10]}"
    L.append(f"sg = doc.addObject('App::DocumentObjectGroup','{sg_name}')")
    
    for slab in sheet.get("slabs", []):
        pts = slab
        z = z_bottom
        if isinstance(pts, dict):
            z = pts.get("z", z_bottom)
            pts = pts.get("pts", pts)
        if len(pts) < 3: continue
        pts_str = ",".join(f"Vector({p[0]},{p[1]},{z})" for p in pts[:20])
        L.append(f"wire=Part.makePolygon([{pts_str}]);face=Part.Face(wire);sl=face.extrude(Vector(0,0,{z_top-z_bottom}));o=doc.addObject('Part::Feature','S');o.Shape=sl;sg.addObject(o)")
        total_solids += 1
    
    cg_name = f"Columns_{title[:10]}"
    L.append(f"cg = doc.addObject('App::DocumentObjectGroup','{cg_name}')")
    for col in sheet.get("columns", []):
        cx = col.get("cx", 0)
        cy = col.get("cy", 0)
        w = col.get("w", 500)
        h = col.get("h", 500)
        L.append(f"c=Part.makeBox({w},{h},{z_top-z_bottom},Vector({cx-w/2},{cy-h/2},{z_bottom}));o=doc.addObject('Part::Feature','C');o.Shape=c;cg.addObject(o)")
        total_solids += 1
    
    bg_name = f"Girders_{title[:10]}"
    L.append(f"bg = doc.addObject('App::DocumentObjectGroup','{bg_name}')")
    for beam in sheet.get("beams", []):
        if isinstance(beam, dict):
            x0 = beam.get("x0", beam.get("start", [0,0])[0])
            y0 = beam.get("y0", beam.get("start", [0,0])[1])
            x1 = beam.get("x1", beam.get("end", [0,0])[0])
            y1 = beam.get("y1", beam.get("end", [0,0])[1])
            w = beam.get("width", 500)
            h = beam.get("height", 700)
            L.append(f"p1=Vector({x0},{y0},{z_bottom});p2=Vector({x1},{y1},{z_bottom});d=p2.sub(p1);bm=Part.makeBox({w},{h},int(d.Length),Vector({x0-w/2},{y0},{z_bottom}));o=doc.addObject('Part::Feature','G');o.Shape=bm;bg.addObject(o)")
            total_solids += 1
    
    for wall in sheet.get("walls", []):
        if isinstance(wall, dict):
            p1 = wall.get("p1", [0,0])
            p2 = wall.get("p2", [0,0])
            t = wall.get("thickness", 200)
            ll = wall.get("length", 3000)
            L.append(f"wl=Part.makeBox({t},{ll},{z_top-z_bottom},Vector({p1[0]},{p1[1]},{z_bottom}));o=doc.addObject('Part::Feature','W');o.Shape=wl;bg.addObject(o)")
            total_solids += 1

L.append("")
L.append("doc.recompute()")
L.append('print(f"POC model: " + str(len(doc.Objects)) + " objects")')
L.append('import os; doc.saveAs(os.path.join(os.path.dirname(__file__), "101dong_poc.fcstd"))')
L.append('print("Saved: 101dong_poc.fcstd")')

script = "\n".join(L)
Path(__file__).parent.joinpath("101dong_poc.py").write_text(script, encoding="utf-8")
print(f"Generated script from poc_v3 data (est. {total_solids}+ solids)")
