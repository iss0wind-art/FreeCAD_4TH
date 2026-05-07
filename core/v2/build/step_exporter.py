"""
step_exporter.py — STEP 출력 (v4 P5)
======================================
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Union


def export_step(
    shapes_with_names: List[Tuple[object, str]],
    out_path: Union[str, Path],
) -> Path:
    """솔리드 리스트 → STEP."""
    try:
        import FreeCAD
        import Part
    except ImportError:
        raise RuntimeError("FreeCAD 환경 필요")

    out = Path(out_path)
    doc = FreeCAD.newDocument("V2BuildExport")
    for shape, name in shapes_with_names:
        if shape is None:
            continue
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
    doc.recompute()
    Part.export([o for o in doc.Objects], str(out))
    FreeCAD.closeDocument(doc.Name)
    return out
