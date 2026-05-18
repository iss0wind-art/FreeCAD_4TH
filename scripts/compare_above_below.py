
import sys
import os
import math
from collections import Counter

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.safe_reader import safe_readfile

def get_member_stats(file_path):
    print(f"  Extracting {os.path.basename(file_path)}...")
    doc = safe_readfile(file_path)
    extractor = StructuralExtractor()
    data = extractor.extract(doc)
    
    stats = {
        'cols': len(data.columns),
        'cols_labeled': len([c for c in data.columns if c.symbol != "NOCOL"]),
        'beams': len(data.beams),
        'beams_labeled': len([b for b in data.beams if b.symbol != "NOBEAM"]),
        'beam_len': sum(b.length for b in data.beams) / 1000.0,
        'slabs': len(data.slab_outlines),
        'slabs_labeled': len([s for s in data.slab_outlines if s.symbol != "NOSLAB"]),
        'slab_area': sum(s.area_m2 for s in data.slab_outlines),
        'walls': len(data.shear_walls),
        'wall_len': sum(math.hypot(w.centerline_p2[0]-w.centerline_p1[0], w.centerline_p2[1]-w.centerline_p1[1]) for w in data.shear_walls) / 1000.0
    }
    return stats

def compare_above_below():
    # 지상 대표: 101동
    above_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    # 지하 대표: 지하주차장
    below_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    
    print("--- Structural Member Analysis: Aboveground vs Underground ---")
    
    above_stats = get_member_stats(above_path)
    below_stats = get_member_stats(below_path)
    
    report = f"""
| 부재 분류 | 지상 (Aboveground - 101동) | 지하 (Underground - 주차장) | 합계 (Total) |
| :--- | :---: | :---: | :---: |
| **기둥 (Columns)** | {above_stats['cols']}개 ({above_stats['cols_labeled']} 매칭) | {below_stats['cols']}개 ({below_stats['cols_labeled']} 매칭) | {above_stats['cols'] + below_stats['cols']}개 |
| **보 (Beams)** | {above_stats['beams']}개 ({above_stats['beam_len']:.0f}m) | {below_stats['beams']}개 ({below_stats['beam_len']:.0f}m) | {above_stats['beams'] + below_stats['beams']}개 |
| **벽체 (Walls)** | {above_stats['walls']}개 ({above_stats['wall_len']:.0f}m) | {below_stats['walls']}개 ({below_stats['wall_len']:.0f}m) | {above_stats['walls'] + below_stats['walls']}개 |
| **슬래브 (Slabs)** | {above_stats['slabs']}개 ({above_stats['slab_area']:.0f}㎡) | {below_stats['slabs']}개 ({below_stats['slab_area']:.0f}㎡) | {above_stats['slabs'] + below_stats['slabs']}개 |
"""
    print(report)

if __name__ == "__main__":
    compare_above_below()
