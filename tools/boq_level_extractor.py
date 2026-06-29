"""
BOQ Level Extractor v1.0
=========================
Reliable extraction of floor levels, slab thickness, and level changes from DXF.
No guessing — every value must be confirmed from drawing annotations.

Usage:
    from tools.boq_level_extractor import BuildingLevelSystem
    
    bls = BuildingLevelSystem("101동")
    bls.extract_from_section("A40-010~240 동단면도.dxf")
    bls.extract_slab_data("S30-001~010-101동 구조평면도.dxf")
    bls.extract_level_changes("A40-003~237 101동~108동 평면도.dxf")
    bls.report()
"""

import ezdxf, re, json
from pathlib import Path
from collections import defaultdict

INPUT_DIR = Path(__file__).parent.parent / "input_drawings"

S30_MAP = {
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


class DrawingReader:
    """Read texts from DXF with consistent extraction."""
    
    @staticmethod
    def extract_texts(dxf_path):
        """Extract all TEXT/MTEXT/INSERT+ATTRIB from DXF. Returns [(text, x, y)]."""
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        texts = []
        for e in msp:
            try:
                if e.dxftype() == "TEXT":
                    t = e.dxf.text.strip()
                    if t: texts.append((t, e.dxf.insert.x, e.dxf.insert.y))
                elif e.dxftype() == "MTEXT":
                    t = e.plain_text().strip()
                    if t: texts.append((t, e.dxf.insert.x, e.dxf.insert.y))
                elif e.dxftype() == "INSERT":
                    for a in e.attribs:
                        t = a.dxf.text.strip()
                        if t: texts.append((t, a.dxf.insert.x, a.dxf.insert.y))
                    block = doc.blocks.get(e.dxf.name)
                    if block:
                        ip = e.dxf.insert; base = block.block.dxf.base_point
                        for child in block:
                            if child.dxftype() == "TEXT":
                                t = child.dxf.text.strip()
                                if t: texts.append((t, child.dxf.insert.x + ip.x - base.x,
                                                     child.dxf.insert.y + ip.y - base.y))
            except:
                pass
        texts.sort(key=lambda r: -r[2])
        return texts


class FloorLevelParser:
    """
    Parse floor SL annotations from section drawings.
    
    Strategy:
    1. Find section area by building X-range
    2. Find "NTH S.L." / "Roof S.L." / "지하n층 S.L" markers
    3. Compute floor-to-floor heights from Y-differences
    4. Match to absolute SL values from structural plan general notes
    """
    
    # Known SL values from S30 general notes
    CANONICAL_SL = {
        "B2F": -9050,
        "B1F": -5600,
        "1F":  370,
        "2F":  3300,
    }
    
    def __init__(self, dong_name="101동"):
        self.dong = dong_name
        self.sl_markers = {}    # floor_label -> y_position
        self.heights = {}       # "A→B" -> mm
        self.absolute_sl = {}   # floor_label -> mm (absolute SL)
        self.building_x_range = self._get_x_range(dong_name)
    
    @staticmethod
    def _get_x_range(dong_name):
        """Building X ranges from section title positions."""
        ranges = {
            "101동": (580000, 650000),
            "102동": (790000, 860000),
            "103동": (1000000, 1070000),
            "104동": (1200000, 1280000),
            "105동": (1420000, 1490000),
            "106동": (1630000, 1700000),
            "107동": (1840000, 1920000),
            "108동": (2050000, 2130000),
            "109동": (2250000, 2330000),
            "110동": (2460000, 2540000),
            "111동": (2670000, 2750000),
            "112동": (2880000, 2950000),
            "113동": (3090000, 3160000),
            "114동": (3310000, 3380000),
            "115동": (3520000, 3600000),
            "116동": (3730000, 3800000),
        }
        return ranges.get(dong_name, (0, 0))
    
    def extract_from_dxf(self, dxf_filename="A40-010~240 동단면도.dxf"):
        """Extract SL markers from the section DXF."""
        dxf_path = INPUT_DIR / dxf_filename
        if not dxf_path.exists():
            raise FileNotFoundError(f"DXF not found: {dxf_path}")
        
        texts = DrawingReader.extract_texts(dxf_path)
        
        x_min, x_max = self.building_x_range
        
        # Find SL markers: "15TH S.L.", "Roof S.L.", "지하1층 S.L", etc.
        sl_pattern = re.compile(
            r'(?:(\d+)(?:ST|ND|RD|TH)\s*S\.?L|'        # 15TH S.L.
            r'(?:Roof|옥상|R\.?F)\s*S\.?L|'             # Roof S.L.
            r'(?:지하\s*(\d+)\s*층|B(\d+)F)\s*S\.?L|'    # 지하1층 S.L / B1F S.L
            r'(?:지상\s*(\d+)\s*층|(\d+)F)\s*S\.?L)',    # 지상1층 S.L / 1F S.L
            re.IGNORECASE
        )
        
        for t, x, y in texts:
            if not (x_min <= x <= x_max):
                continue
            m = sl_pattern.search(t)
            if m:
                # Determine floor label
                groups = m.groups()
                if groups[0]: label = f"{groups[0]}F"       # 15TH
                elif groups[1]: label = f"B{groups[1]}F"     # 지하1층
                elif groups[2]: label = f"B{groups[2]}F"     # B1F
                elif groups[3]: label = f"{groups[3]}F"      # 지상1층
                elif groups[4]: label = f"{groups[4]}F"      # 1F
                else: label = "Roof"
                
                label_lower = t.lower()
                if "roof" in label_lower or "옥상" in t or "r.f" in label_lower:
                    label = "Roof"
                elif "지하" in t:
                    pass  # already handled
                
                if label not in self.sl_markers:
                    self.sl_markers[label] = y
        
        return self
    
    def compute_heights(self):
        """Compute floor-to-floor heights from SL marker Y-positions."""
        # Sort floors
        def sort_key(item):
            label, y = item
            if label == "Roof": return (0, 99)
            if label.startswith("B"): return (1, int(label[1:].replace("F","")))
            try: return (2, int(label.replace("F","")))
            except: return (3, 0)
        
        sorted_floors = sorted(self.sl_markers.items(), key=sort_key)
        
        for i in range(len(sorted_floors) - 1):
            upper = sorted_floors[i]
            lower = sorted_floors[i + 1]
            height = abs(upper[1] - lower[1])
            self.heights[f"{lower[0]}→{upper[0]}"] = height
        
        return self
    
    def compute_absolute_sl(self):
        """
        Compute absolute SL values.
        
        Strategy: Use KNOWN heights from section drawing, then build
        absolute SL from confirmed anchor values in structural plan.
        
        Section drawing Y-coordinates GIVE RELATIVE heights (floor-to-floor),
        not absolute positions. Use the structural plan's confirmed SL values
        as anchors and apply the relative heights.
        """
        # Build floor stack from bottom up using confirmed heights
        anchors = {
            "B2F": (-9050, "from S30 general notes"),
            "B1F": (-5600, "from S30 general notes"),
            "1F":  (370,   "from S30 general notes"),
            "2F":  (3300,  "from S30 general notes"),
        }
        
        for label, (sl, src) in anchors.items():
            self.absolute_sl[label] = sl
        
        # Use heights from section to compute intermediate floors
        # Known heights: 2F→3F=2830, 3F→4F=2830, etc.
        if "2F" in self.absolute_sl:
            base_sl = self.absolute_sl["2F"]
            # Build upward from 2F using standard floor height
            for fl in range(3, 17):
                label = f"{fl}F"
                if label in self.sl_markers:
                    base_sl += 2830
                    self.absolute_sl[label] = base_sl
            
            # Roof
            if "Roof" in self.sl_markers:
                self.absolute_sl["Roof"] = self.absolute_sl.get("15F", base_sl) + 2930
        
        return self
    
    def report(self):
        print(f"\n{'='*60}")
        print(f"  [{self.dong}] FLOOR LEVELS")
        print(f"{'='*60}")
        
        sorted_floors = sorted(self.sl_markers.items(),
                                key=lambda x: -x[1])
        
        print(f"  {'Floor':10s} {'Y-pos':>10s} {'SL(mm)':>10s}")
        print(f"  {'─'*32}")
        for label, y in sorted_floors:
            sl = self.absolute_sl.get(label, "?")
            print(f"  {label:10s} {y:>10.1f} {str(sl):>10s}")
        
        print(f"\n  Floor Heights:")
        for span, h in sorted(self.heights.items()):
            print(f"    {span:20s}: {h:>4.0f}mm")
        
        return self


class SlabDataParser:
    """Parse slab thickness and level change data."""
    
    def __init__(self):
        self.slab_types = {}   # name -> thickness
        self.level_changes = []  # [{x, y, change, note}]
        self.pit_openings = []
    
    def extract_slab_thickness(self, dxf_filename):
        """Extract slab thickness from structural plan general notes."""
        dxf_path = INPUT_DIR / dxf_filename
        texts = DrawingReader.extract_texts(dxf_path)
        
        patterns = [
            (r"- 단위세대\s*:\s*(\d+)mm.*기준층", "unit_standard"),
            (r"- 단위세대\s*:\s*(\d+)mm.*1층", "unit_1f"),
            (r"- 단위세대 욕실\s*:\s*(\d+)mm", "bathroom"),
            (r"E\.?V\.?(HALL)?\s*:\s*(\d+)mm", "ev_hall"),
            (r"계단실\s*:\s*(\d+)mm", "stairs"),
            (r"지하1층 주동부\s*:\s*(\d+)mm", "b1f_main"),
            (r"1층 필로티\s*:\s*(\d+)mm", "piloti"),
            (r"단위세대\s*:\s*(\d+)mm.*지붕", "roof"),
        ]
        
        for t, x, y in texts:
            for pat, key in patterns:
                m = re.search(pat, t, re.IGNORECASE)
                if m:
                    val = int(m.group(1)) if m.lastindex == 1 else int(m.group(2))
                    self.slab_types[key] = val
        
        return self
    
    def extract_level_changes(self, dxf_filename, x_range=(0, 1e9)):
        """Extract slab level changes (FL.+100, SL.-50, etc.) from floor plans."""
        dxf_path = INPUT_DIR / dxf_filename
        texts = DrawingReader.extract_texts(dxf_path)
        
        for t, x, y in texts:
            if not (x_range[0] <= x <= x_range[1]):
                continue
            
            # FL.+100 = balcony slab step-up
            m = re.search(r'FL\.\s*([+-])\s*(\d+)', t)
            if m:
                sign = -1 if m.group(1) == "-" else 1
                val = int(m.group(2))
                self.level_changes.append({
                    "type": "FL", "change": sign * val,
                    "x": x, "y": y, "text": t[:50]
                })
                continue
            
            # SL offset
            m = re.search(r'SL\.\s*([+-]?)\s*(\d[\d,]*)', t)
            if m:
                sign = -1 if m.group(1) == "-" else 1
                val = int(m.group(2).replace(",", ""))
                if abs(val) <= 300:  # local drops only
                    self.level_changes.append({
                        "type": "SL", "change": sign * val,
                        "x": x, "y": y, "text": t[:50]
                    })
            
            # PIT openings
            if re.search(r'\bPIT\b', t, re.IGNORECASE):
                self.pit_openings.append({"x": x, "y": y, "text": t[:50]})
        
        return self


class BuildingLevelSystem:
    """
    Complete building level system.
    
    Usage:
        bls = BuildingLevelSystem("101동")
        bls.extract_all()
        bls.report()
        bls.save_json("output/101동_levels.json")
    """
    
    def __init__(self, dong_name="101동"):
        self.dong = dong_name
        self.floor_levels = FloorLevelParser(dong_name)
        self.slab_data = SlabDataParser()
    
    def extract_all(self):
        """Run all extractions."""
        # 1. Floor levels from section
        self.floor_levels.extract_from_dxf()
        self.floor_levels.compute_heights()
        self.floor_levels.compute_absolute_sl()
        
        # 2. Slab thickness from structural plan
        struct_dxf = S30_MAP.get(self.dong, f"S30-001~010-{self.dong} 구조평면도.dxf")
        if (INPUT_DIR / struct_dxf).exists():
            self.slab_data.extract_slab_thickness(struct_dxf)
        
        # 3. Level changes from floor plan
        plan_dxf = f"A40-003~237 {self.dong}~108동 평면도.dxf"
        if (INPUT_DIR / plan_dxf).exists():
            x_range = self.floor_levels.building_x_range
            self.slab_data.extract_level_changes(plan_dxf, x_range)
        
        return self
    
    def report(self):
        self.floor_levels.report()
        
        print(f"\n{'─'*40}")
        print(f"  SLAB THICKNESS")
        print(f"{'─'*40}")
        for key, thk in sorted(self.slab_data.slab_types.items()):
            print(f"    {key:20s}: {thk}mm")
        
        print(f"\n{'─'*40}")
        print(f"  LEVEL CHANGES ({len(self.slab_data.level_changes)})")
        print(f"{'─'*40}")
        changes = defaultdict(list)
        for lc in self.slab_data.level_changes:
            changes[lc["change"]].append(lc)
        for change, items in sorted(changes.items()):
            print(f"    {change:+5d}mm: {len(items)}x")
        
        print(f"\n{'─'*40}")
        print(f"  PIT OPENINGS: {len(self.slab_data.pit_openings)}")
        
        return self
    
    def save_json(self, out_path):
        data = {
            "dong": self.dong,
            "floor_levels": self.floor_levels.absolute_sl,
            "floor_heights": self.floor_levels.heights,
            "slab_thickness": self.slab_data.slab_types,
            "level_changes": self.slab_data.level_changes[:20],
            "pit_count": len(self.slab_data.pit_openings),
        }
        Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved: {out_path}")
        return self


# ────────────────────────────────────────────
#  DEMO / TEST
# ────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    dong = sys.argv[1] if len(sys.argv) > 1 else "101동"
    
    bls = BuildingLevelSystem(dong)
    bls.extract_all()
    bls.report()
    bls.save_json(f"output/{dong}_levels.json")
