
import sys
import os
import math
from collections import Counter

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.safe_reader import safe_readfile

def check_status():
    dong_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    print(f"--- Member Parsing Status Check: {os.path.basename(dong_path)} ---")
    
    doc = safe_readfile(dong_path)
    extractor = StructuralExtractor()
    data = extractor.extract(doc)
    
    # 1. 기둥 (Columns)
    cols = data.columns
    col_symbols = [c.symbol for c in cols]
    col_symbol_stats = Counter(col_symbols)
    labeled_cols = [c for c in cols if c.symbol != "NOCOL"]
    print(f"\n[1] Columns: Total {len(cols)}")
    print(f"    - Labeled: {len(labeled_cols)} ({len(labeled_cols)/len(cols)*100:.1f}%)")
    print(f"    - Top Symbols: {dict(col_symbol_stats.most_common(5))}")
    
    # 2. 보 (Beams)
    beams = data.beams
    beam_symbols = [b.symbol for b in beams]
    beam_symbol_stats = Counter(beam_symbols)
    labeled_beams = [b for b in beams if b.symbol != "NOBEAM"]
    total_beam_length = sum(b.length for b in beams) / 1000.0 # m
    print(f"\n[2] Beams: Total {len(beams)}")
    print(f"    - Labeled: {len(labeled_beams)} ({len(labeled_beams)/len(beams)*100:.1f}%)")
    print(f"    - Total Length: {total_beam_length:.1f} m")
    print(f"    - Top Symbols: {dict(beam_symbol_stats.most_common(5))}")
    
    # 3. 슬래브 (Slabs)
    slabs = data.slab_outlines
    slab_symbols = [s.symbol for s in slabs]
    slab_symbol_stats = Counter(slab_symbols)
    labeled_slabs = [s for s in slabs if s.symbol != "NOSLAB"]
    total_slab_area = sum(s.area_m2 for s in slabs)
    print(f"\n[3] Slabs: Total {len(slabs)}")
    print(f"    - Labeled: {len(labeled_slabs)} ({len(labeled_slabs)/len(slabs)*100:.1f}%)")
    print(f"    - Total Area: {total_slab_area:.1f} m2")
    print(f"    - Top Symbols: {dict(slab_symbol_stats.most_common(5))}")
    
    # 4. 전단벽 (Shear Walls)
    walls = data.shear_walls
    total_wall_length = sum(math.hypot(w.centerline_p2[0]-w.centerline_p1[0], w.centerline_p2[1]-w.centerline_p1[1]) for w in walls) / 1000.0 # m
    print(f"\n[4] Shear Walls: Total {len(walls)}")
    print(f"    - Total Length: {total_wall_length:.1f} m")

if __name__ == "__main__":
    check_status()
