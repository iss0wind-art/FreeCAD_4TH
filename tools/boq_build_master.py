"""
BOQ Build Master v1.0
=====================
통합 파이프라인: DXF → 구조파싱 → FreeCAD 3D → BOQ

사용법:
    python tools/boq_build_master.py 101동
    python tools/boq_build_master.py all
    python tools/boq_build_master.py 101동 --report-only
"""

import sys, json, time, os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

INPUT = ROOT / "input_drawings"
OUTPUT = ROOT / "output"

# ──────────────────────────────────────
# 1. LEVEL SYSTEM (my module)
# ──────────────────────────────────────
from tools.boq_level_extractor import BuildingLevelSystem, FloorLevelParser, SlabDataParser

# ──────────────────────────────────────
# 2. DXF PIPELINE (existing core)
# ──────────────────────────────────────
from core.dxf_parser.pipeline import parse_structural_frame, FrameData
from core.dxf_parser.coord_unifier import CoordUnifier
from core.dxf_parser.level_parser import parse_dxf as parse_level_dxf


@dataclass
class BuildResult:
    dong: str = ""
    levels: dict = field(default_factory=dict)
    beams: List[dict] = field(default_factory=list)
    columns: List[dict] = field(default_factory=list)
    walls: List[dict] = field(default_factory=list)
    slabs: List[dict] = field(default_factory=list)
    slab_types: dict = field(default_factory=dict)
    level_changes: List[dict] = field(default_factory=list)
    pit_openings: int = 0
    grid: dict = field(default_factory=dict)
    frame_json: str = ""
    elapsed_sec: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    def summary(self) -> str:
        lines = [f"\n{'='*60}", f"  [{self.dong}] BUILD MASTER REPORT", f"{'='*60}"]
        lines.append(f"  Elapsed: {self.elapsed_sec:.1f}s")
        lines.append(f"  Levels: {len(self.levels)} floors")
        lines.append(f"  Beams: {len(self.beams)}")
        lines.append(f"  Columns: {len(self.columns)}")
        lines.append(f"  Walls: {len(self.walls)}")
        lines.append(f"  Slab outlines: {len(self.slabs)}")
        lines.append(f"  Slab types: {len(self.slab_types)}")
        lines.append(f"  Step changes: {len(self.level_changes)}")
        lines.append(f"  PIT openings: {self.pit_openings}")
        if self.errors:
            lines.append(f"  ERRORS: {len(self.errors)}")
            for e in self.errors[:5]:
                lines.append(f"    - {e}")
        return "\n".join(lines)


def build_dong(dong_name: str) -> BuildResult:
    """Build complete model for one apartment building."""
    t0 = time.time()
    result = BuildResult(dong=dong_name)
    
    dong_num = dong_name.replace("동", "")
    
    # ── A. DXF path mapping ──
    s30_map = {
        "101동": "S30-001~010-101동 구조평면도.dxf",
        "102동": "S30-021~029-102동 구조평면도.dxf",
        "103동": "S30-041~050-103동 구조평면도.dxf",
        "104동": "S30-061~070-104동 구조평면도.dxf",
        "105동": "S30-081~089-105동 구조평면도.dxf",
        "106동": "S30-101~110-106동 구조평면도.dxf",
        "107동": "S30-121~128-107동 구조평면도.dxf",
        "108동": "S30-131~140-108동 구조평면도.dxf",
        "109동": "S30-151~161-109동 구조평면도.dxf",
        "110동": "S30-171~180-110동 구조평면도.dxf",
        "111동": "S30-191~202-111동 구조평면도.dxf",
        "112동": "S30-211~219-112동 구조평면도.dxf",
        "113동": "S30-231~237-113동 구조평면도.dxf",
        "114동": "S30-241~248-114동 구조평면도.dxf",
        "115동": "S30-251~259-115동 구조평면도.dxf",
        "116동": "S30-271~279-116동 구조평면도.dxf",
    }
    
    struct_dxf = s30_map.get(dong_name, f"S30-001~010-{dong_name} 구조평면도.dxf")
    struct_path = INPUT / struct_dxf
    
    # ── B. Floor Levels ──
    try:
        bls = BuildingLevelSystem(dong_name)
        bls.floor_levels.extract_from_dxf()
        bls.floor_levels.compute_heights()
        bls.floor_levels.compute_absolute_sl()
        result.levels = bls.floor_levels.absolute_sl.copy()
        
        # Slab thickness from structural plan
        if struct_path.exists():
            sdp = SlabDataParser()
            sdp.extract_slab_thickness(str(struct_path))
            result.slab_types = sdp.slab_types.copy()
        
        # Level changes from floor plan (A40 covers 101~108 or 109~116)
        dong_i = int(dong_num)
        if dong_i <= 108:
            plan_dxf = "A40-003~237 101동~108동 평면도.dxf"
        else:
            plan_dxf = "A40-003~237 109동~116동 평면도.dxf"
        sdp2 = SlabDataParser()
        sdp2.extract_level_changes(plan_dxf)
        result.level_changes = sdp2.level_changes
        result.pit_openings = len(sdp2.pit_openings)
    except Exception as e:
        result.errors.append(f"Levels: {e}")
    
    # ── C. Structural Frame ──
    try:
        if struct_path.exists():
            frame = parse_structural_frame(str(struct_path))
            result.frame_json = frame.to_json()
            frame_data = json.loads(result.frame_json)
            result.beams = frame_data.get("beams", [])
            result.columns = frame_data.get("columns", [])
            result.slabs = frame_data.get("slab_outlines", [])
            result.walls = frame_data.get("shear_walls", [])
            if frame_data.get("grid"):
                result.grid = frame_data["grid"]
    except Exception as e:
        result.errors.append(f"Frame: {e}")
    
    # ── D. Coordinate Unification (PKG ↔ DONG) ──
    try:
        # Load known transform from coord_config
        txf = {"tx": -447970, "ty": 3621813}
        
        # Try to use CoordUnifier for active alignment
        try:
            from core.dxf_parser.coord_unifier import CoordUnifier
            unifier = CoordUnifier()
            unifier.add("dong", str(struct_path), dong=dong_num)
            
            # Find building location in parking plan
            parking_dxf = str(INPUT / "260119_부산에코델타 공동주택 24BL 지하주차장 구조평면도23.dxf")
            if Path(parking_dxf).exists():
                unifier.add("parking", parking_dxf, dong_clip=(10000, -2000000, 900000, -500000))
                transforms = unifier.unify(reference="dong")
                if "parking" in transforms:
                    t = transforms["parking"]
                    txf = {"tx": t.tx, "ty": t.ty}
        except:
            pass
        
        result.coord_transform = txf
    except Exception as e:
        result.errors.append(f"Coord: {e}")
    
    result.elapsed_sec = time.time() - t0
    return result


def save_json(result: BuildResult, path: str):
    data = asdict(result)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def report_all(all_results: Dict[str, BuildResult]):
    print(f"\n{'='*60}")
    print(f"  FINAL REPORT — {len(all_results)} buildings")
    print(f"{'='*60}")
    
    totals = {"beams": 0, "columns": 0, "walls": 0, "slabs": 0, "errors": 0}
    
    for dong_name in sorted(all_results.keys()):
        r = all_results[dong_name]
        print(f"\n  {dong_name}:")
        print(f"    Levels: {len(r.levels)} floors")
        print(f"    Beams: {len(r.beams)} | Columns: {len(r.columns)} | Walls: {len(r.walls)} | Slabs: {len(r.slabs)}")
        print(f"    Step changes: {len(r.level_changes)} | PIT: {r.pit_openings}")
        if r.errors:
            print(f"    ⚠ Errors: {r.errors}")
        totals["beams"] += len(r.beams)
        totals["columns"] += len(r.columns)
        totals["walls"] += len(r.walls)
        totals["slabs"] += len(r.slabs)
        totals["errors"] += len(r.errors)
    
    print(f"\n  {'─'*40}")
    print(f"  GRAND TOTAL")
    print(f"  Beams: {totals['beams']}")
    print(f"  Columns: {totals['columns']}")
    print(f"  Walls: {totals['walls']}")
    print(f"  Slab outlines: {totals['slabs']}")
    print(f"  Errors: {totals['errors']}")
    print(f"{'='*60}")


# ──────────────────────────────────────
# MAIN
# ──────────────────────────────────────
if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    
    if args[0] == "all":
        dongs = [f"{i}동" for i in range(101, 117)]
    else:
        dongs = [a for a in args if a.replace("동", "").isdigit() or a.endswith("동")]
        if not dongs:
            dongs = [args[0]]
    
    all_results = {}
    for dong in dongs:
        print(f"\n  Building {dong}...")
        result = build_dong(dong)
        all_results[dong] = result
        print(result.summary())
        
        out_path = OUTPUT / f"build_{dong}.json"
        save_json(result, str(out_path))
        print(f"    Saved: {out_path}")
        
        # knot-vault 자동 동기화
        try:
            from tools.knot_vault_sync import sync_all
            sync_all([dong])
        except Exception as kv_e:
            print(f"    [knot-vault] sync skipped: {kv_e}")
    
    report_all(all_results)
    
    # Save master report
    master = {
        dong: {
            "beams": len(r.beams),
            "columns": len(r.columns),
            "walls": len(r.walls),
            "slabs": len(r.slabs),
            "levels": len(r.levels),
            "step_changes": len(r.level_changes),
            "errors": len(r.errors),
            "elapsed": round(r.elapsed_sec, 1),
        }
        for dong, r in all_results.items()
    }
    (OUTPUT / "build_master_report.json").write_text(
        json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Master report: output/build_master_report.json")
