"""
Minimal FreeCAD test: 101동 core + slab
"""
import FreeCAD, Part
from FreeCAD import Vector

doc = FreeCAD.newDocument("101동_test")

# ── 1. SLAB (B1F) ──
slab_pts = [
    Vector(69013, 2241258, -5600),
    Vector(229013, 2241258, -5600),
    Vector(229013, 2401258, -5600),
    Vector(69013, 2401258, -5600),
]
wire = Part.makePolygon(slab_pts + [slab_pts[0]])
face = Part.Face(wire)
slab = face.extrude(Vector(0, 0, 210))
slab_obj = doc.addObject("Part::Feature", "Slab_B1F")
slab_obj.Shape = slab

# ── 2. FEW COLUMNS ──
cols_data = [
    (100000, 2300000, 600, 600, "RC"),
    (120000, 2300000, 600, 600, "RC"),
    (140000, 2300000, 600, 600, "RC"),
    (100000, 2320000, 600, 600, "RC"),
    (120000, 2320000, 600, 600, "RC"),
]
rc_group = doc.addObject("App::DocumentObjectGroup", "Columns_RC")
for i, (cx, cy, w, h, mtype) in enumerate(cols_data):
    col = Part.makeBox(w, h, 2830, Vector(cx-w/2, cy-h/2, -5600))
    obj = doc.addObject("Part::Feature", f"Col_{i}_{mtype}")
    obj.Shape = col
    rc_group.addObject(obj)

# ── 3. FEW BEAMS ──
beams_data = [
    (100000, 2300000, 140000, 2300000, 500, 900, "RC"),
    (140000, 2300000, 140000, 2320000, 500, 900, "RC"),
    (100000, 2320000, 140000, 2320000, 500, 900, "RC"),
]
beam_rc_g = doc.addObject("App::DocumentObjectGroup", "Beams_RC")
for i, (x0, y0, x1, y1, w, h, mtype) in enumerate(beams_data):
    p1, p2 = Vector(x0, y0, -5600), Vector(x1, y1, -5600)
    d = p2.sub(p1)
    beam = Part.makeBox(w, h, int(d.Length), Vector(x0-w/2, y0, -5600))
    obj = doc.addObject("Part::Feature", f"Beam_{i}_{mtype}")
    obj.Shape = beam
    beam_rc_g.addObject(obj)

doc.recompute()
print("101동_minimal model ready")
print(f"Objects: {len(doc.Objects)}")

import os
doc.saveAs(os.path.join(os.path.dirname(__file__), "101동_minimal.fcstd"))
print("Saved: output/101동_minimal.fcstd")
