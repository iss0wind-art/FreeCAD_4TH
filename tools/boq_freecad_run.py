"""
BOQ FreeCAD 3D Model Runner
============================
Generates and optionally runs FreeCAD build.

Usage:
    python tools/boq_freecad_run.py 101동          # generate + print script
    python tools/boq_freecad_run.py 101동 --save    # save .py for freecadcmd
    python tools/boq_freecad_run.py 101동 --run     # run FreeCAD (if installed)
"""

import sys, json, os
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "output"

# PC keywords for layer-based classification
PC_LAYERS = {"S-PC-GIRDER", "S-PC-SLAB", "S-PC-BEAM", "PC-GIRDER", "00_PC", "PC_COLUMN"}
PC_SYMBOLS = {"PC"}


def classify_member(layer="", symbol=""):
    """Return 'pc' if member is precast, 'rc' otherwise."""
    layer_upper = layer.upper() if layer else ""
    sym_upper = symbol.upper() if symbol else ""
    for pc in PC_LAYERS:
        if pc in layer_upper:
            return "pc"
    for pc in PC_SYMBOLS:
        if sym_upper.startswith(pc):
            return "pc"
    return "rc"


def generate_model(dong_name, build_data):
    """Generate FreeCAD script from build data."""
    levels = build_data.get("levels", {})
    beams = build_data.get("beams", [])
    columns = build_data.get("columns", [])
    walls = build_data.get("walls", [])
    slabs = build_data.get("slabs", [])
    
    lines = [f'"""FreeCAD 3D Model — {dong_name} (generated)"""']
    lines.append("import FreeCAD, Part")
    lines.append("from FreeCAD import Vector")
    lines.append(f'doc = FreeCAD.newDocument("{dong_name}")')
    lines.append("")
    
    # Floor levels labeled
    for fl, sl in sorted(levels.items(), key=lambda x: str(x[1])):
        lines.append(f"# {fl}: SL = {sl}mm")
    
    lines.append("")
    
    # ── COLUMNS: RC vs PC ──
    col_rc = []
    col_pc = []
    for c in columns:
        layer = c.get("layer", "")
        mtype = classify_member(layer, c.get("symbol", ""))
        if mtype == "pc":
            col_pc.append(c)
        else:
            col_rc.append(c)
    
    lines.append(f"# COLUMNS: RC={len(col_rc)} PC={len(col_pc)}")
    lines.append(f"rc_group = doc.addObject('App::DocumentObjectGroup', 'Columns_RC')")
    lines.append(f"pc_group = doc.addObject('App::DocumentObjectGroup', 'Columns_PC')")
    
    for i, c in enumerate(col_rc[:100]):
        cx, cy = c.get("cx", 0), c.get("cy", 0)
        w, h = c.get("w", 500), c.get("h", 500)
        lines.append(f"""
col = Part.makeBox({w}, {h}, 2830, Vector({cx-w/2}, {cy-h/2}, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_{i}')
obj.Shape = col
rc_group.addObject(obj)""")
    
    for i, c in enumerate(col_pc[:50]):
        cx, cy = c.get("cx", 0), c.get("cy", 0)
        w, h = c.get("w", 500), c.get("h", 500)
        lines.append(f"""
col = Part.makeBox({w}, {h}, 2830, Vector({cx-w/2}, {cy-h/2}, -5600))
obj = doc.addObject('Part::Feature', 'C_PC_{i}')
obj.Shape = col
pc_group.addObject(obj)""")
    
    lines.append("")
    
    # ── BEAMS: RC vs PC ──
    beam_rc = []
    beam_pc = []
    for b in beams:
        layer = b.get("layer", "")
        mtype = classify_member(layer, b.get("symbol", ""))
        if mtype == "pc":
            beam_pc.append(b)
        else:
            beam_rc.append(b)
    
    lines.append(f"# BEAMS: RC={len(beam_rc)} PC={len(beam_pc)}")
    lines.append(f"beam_rc_g = doc.addObject('App::DocumentObjectGroup', 'Beams_RC')")
    lines.append(f"beam_pc_g = doc.addObject('App::DocumentObjectGroup', 'Beams_PC')")
    
    for i, b in enumerate(beam_rc[:200]):
        x0, y0 = b.get("x0", 0), b.get("y0", 0)
        x1, y1 = b.get("x1", 0), b.get("y1", 0)
        w = b.get("width", 500)
        h = b.get("height", 600)
        lines.append(f"""
p1 = Vector({x0}, {y0}, -5600)
p2 = Vector({x1}, {y1}, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox({w}, {h}, length, Vector({x0-w/2}, {y0-h/2}, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_{i}')
obj.Shape = beam
beam_rc_g.addObject(obj)""")
    
    for i, b in enumerate(beam_pc[:50]):
        x0, y0 = b.get("x0", 0), b.get("y0", 0)
        x1, y1 = b.get("x1", 0), b.get("y1", 0)
        lines.append(f"""
beam = Part.makeBox(500, 600, 8000, Vector({x0}, {y0}, -5600))
obj = doc.addObject('Part::Feature', 'B_PC_{i}')
obj.Shape = beam
beam_pc_g.addObject(obj)""")
    
    lines.append("")
    
    # ── SLABS ──
    lines.append(f"# SLABS: {len(slabs)}")
    lines.append(f"slab_g = doc.addObject('App::DocumentObjectGroup', 'Slabs')")
    for i, slab in enumerate(slabs):
        pts = slab.get("pts", [])
        if len(pts) < 3:
            continue
        pts_str = ", ".join(f"Vector({p[0]}, {p[1]}, -5600)" for p in pts)
        thk = 210
        lines.append(f"""
wire = Part.makePolygon([{pts_str}])
face = Part.Face(wire)
slab = face.extrude(Vector(0, 0, {thk}))
obj = doc.addObject('Part::Feature', 'Slab_{i}')
obj.Shape = slab
slab_g.addObject(obj)""")
    
    lines.append("")
    lines.append("doc.recompute()")
    lines.append(f"print('Model {dong_name} ready')")
    
    return "\n".join(lines)


if __name__ == "__main__":
    dong = sys.argv[1] if len(sys.argv) > 1 else "101동"
    save = "--save" in sys.argv
    run = "--run" in sys.argv
    
    build_path = OUT / f"build_{dong}.json"
    if not build_path.exists():
        print(f"Build data not found: {build_path}")
        print("Run `python tools/boq_build_master.py {dong}` first")
        sys.exit(1)
    
    data = json.loads(build_path.read_text(encoding="utf-8"))
    script = generate_model(dong, data)
    
    if save or run:
        script_path = OUT / f"{dong}_freecad_build.py"
        script_path.write_text(script, encoding="utf-8")
        print(f"Script saved: {script_path}")
        if run:
            os.system(f'freecadcmd "{script_path}"')
    else:
        print(script[:500])
        print(f"\n... ({len(script)} chars total)")
        print(f"\nTo save: python tools/boq_freecad_run.py {dong} --save")
        print(f"To run:  python tools/boq_freecad_run.py {dong} --run")
