import sys
import os
import math
from collections import Counter
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.v2.inspect.meta_pipeline import inspect
from core.v2.extract.extract_pipeline import extract_all_members

def check_v2_status():
    dong_path = Path("D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf")
    print(f"--- V2 Engine Parsing Status Check: {dong_path.name} ---")
    
    # 1. 메타 데이터 및 레이어 분석 (inspect)
    meta = inspect(dong_path)
    
    # 2. V2 파이프라인 추출 실행
    # 일람표가 있다면 파싱해서 넣어야 하지만 일단 없이 추출
    data = extract_all_members(meta)
    
    # 1. 기둥 (Columns)
    cols = data.columns
    col_layers = Counter([c[0].layer for c in cols])
    print(f"\n[1] Columns (V2): Total {len(cols)}")
    print(f"    - Top Layers: {dict(col_layers.most_common(5))}")
    
    # 2. 보 (Beams)
    beams = data.beams
    beam_layers = Counter([b[0].layer for b in beams])
    total_beam_length = sum(b[0].length_mm for b in beams) / 1000.0 # m
    print(f"\n[2] Beams (V2): Total {len(beams)}")
    print(f"    - Total Length: {total_beam_length:.1f} m")
    print(f"    - Top Layers: {dict(beam_layers.most_common(5))}")
    
    # 3. 슬래브 (Slabs)
    slabs = data.slabs
    total_slab_area = sum(s[0].area_m2 for s in slabs)
    print(f"\n[3] Slabs (V2): Total {len(slabs)}")
    print(f"    - Total Area: {total_slab_area:.1f} m2")
    
    # 4. 전단벽 (Shear Walls)
    walls = data.walls
    total_wall_length = sum(w[0].length_mm for w in walls) / 1000.0 # m
    print(f"\n[4] Shear Walls (V2): Total {len(walls)}")
    print(f"    - Total Length: {total_wall_length:.1f} m")

if __name__ == "__main__":
    check_v2_status()
