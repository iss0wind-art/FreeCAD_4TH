"""
BOQ FreeCAD 3D Build v1.0
=========================
Pipeline output → FreeCAD 3D model

Usage: FreeCAD Python console or:
    freecadcmd tools/boq_freecad_build.py 101동
    
Generates: output/101동_build.py (FreeCAD script)
"""

import json, sys, os
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "output"


def generate_freecad_script(dong_name: str) -> str:
    """Generate a FreeCAD Python script from build data."""
    build_path = OUTPUT / f"build_{dong_name}.json"
    if not build_path.exists():
        return f"# Build data not found: {build_path}"
    
    data = json.loads(build_path.read_text(encoding="utf-8"))
    
    lines = [
        f'"""FreeCAD 3D Build — {dong_name} (auto-generated)"""',
        "import FreeCAD, Part, Draft",
        "from FreeCAD import Base, Vector",
        "",
        f'doc = FreeCAD.newDocument("{dong_name}")',
        f'print("Building {dong_name}...")',
        "",
        "# ── FLOOR LEVELS ──",
    ]
    
    levels = data.get("levels", {})
    for floor, sl in sorted(levels.items(), key=lambda x: str(x[1])):
        lines.append(f"# {floor}: SL = {sl}mm")
    
    lines.append("")
    lines.append("# ── COLUMNS ──")
    cols = data.get("columns", [])
    lines.append(f"print(f'Columns: {len(cols)}')")
    for i, col in enumerate(cols[:500]):
        cx, cy = col.get("cx", 0), col.get("cy", 0)
        w, h = col.get("w", 500), col.get("h", 500)
        lines.append(f"""
box = Part.makeBox({w}, {h}, 2830, Vector({cx-w/2}, {cy-h/2}, -9050))
box_obj = doc.addObject("Part::Feature", "Col_{i}")
box_obj.Shape = box""")
    
    lines.append("")
    lines.append("# ── BEAMS ──")
    beams = data.get("beams", [])
    lines.append(f"print(f'Beams: {len(beams)}')")
    for i, beam in enumerate(beams[:500]):
        x0, y0 = beam.get("x0", 0), beam.get("y0", 0)
        x1, y1 = beam.get("x1", 0), beam.get("y1", 0)
        w = beam.get("width", 500)
        h = beam.get("height", 600)
        lines.append(f"""
p1 = Vector({x0}, {y0}, -5600)
p2 = Vector({x1}, {y1}, -5600)
length = p1.distanceToPoint(p2)
beam = Part.makeBox({w}, {h}, length, Vector({x0-w/2}, {y0-h/2}, -5600))
beam_obj = doc.addObject("Part::Feature", "Beam_{i}")
beam_obj.Shape = beam""")
    
    lines.append("")
    lines.append("# ── SLAB OUTLINES ──")
    slabs = data.get("slabs", [])
    lines.append(f"print(f'Slabs: {len(slabs)}')")
    for i, slab in enumerate(slabs):
        pts = slab.get("pts", [])
        if len(pts) < 3:
            continue
        thk = 210  # default
        pts_str = ", ".join(f"Vector({p[0]}, {p[1]}, -5600)" for p in pts)
        lines.append(f"""
wire = Part.makePolygon([{pts_str}])
face = Part.Face(wire)
slab = face.extrude(Vector(0, 0, {thk}))
slab_obj = doc.addObject("Part::Feature", "Slab_{i}")
slab_obj.Shape = slab""")
    
    lines.append("")
    lines.append("# ── WALLS ──")
    walls = data.get("walls", [])
    lines.append(f"print(f'Walls: {len(walls)}')")
    for i, wall in enumerate(walls[:500]):
        p1 = wall.get("p1", [0, 0])
        p2 = wall.get("p2", [0, 0])
        thk = wall.get("thickness", 200)
        length = wall.get("length", 3000)
        lines.append(f"""
wall = Part.makeBox({thk}, {length}, 2830, Vector({p1[0]}, {p1[1]}, -9050))
wall_obj = doc.addObject("Part::Feature", "Wall_{i}")
wall_obj.Shape = wall""")
    
    lines.append("")
    lines.append("doc.recompute()")
    lines.append(f'print(f"Done: {dong_name}")')
    
    return "\n".join(lines)


def generate_build_script(dong_name: str):
    script = generate_freecad_script(dong_name)
    out_path = OUTPUT / f"{dong_name}_freecad_build.py"
    out_path.write_text(script, encoding="utf-8")
    print(f"Generated: {out_path}")
    print(f"  Run: freecadcmd {out_path}")


if __name__ == "__main__":
    dong = sys.argv[1] if len(sys.argv) > 1 else "101동"
    generate_build_script(dong)
