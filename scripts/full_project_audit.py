"""
full_project_audit.py — 프로젝트 전체 구조체(보/기둥/슬래브) 파싱율 전수 감사
========================================================================
101동 전체 시트를 순회하며 보, 기둥, 슬래브의 실제 매칭 성공률을 집계.
"""
import os
import sys
from core.dxf_parser.pipeline import parse_structural_frame

def run_audit():
    dxf_path = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
    
    sheets = {
        "B2F (S30-001)": (100000, 2340000, 180000, 2400000),
        "B1F (S30-002)": (100000, 2240000, 180000, 2300000),
        "PH  (S30-010)": (900000, 2050000, 1000000, 2150000)
    }
    
    print("="*70)
    print("      [FULL STRUCTURAL AUDIT REPORT - 101 DONG]")
    print("="*70)
    
    total_stats = {'beams': [0,0], 'cols': [0,0], 'slabs': [0,0]}
    
    for name, clip in sheets.items():
        print(f"\n[Auditing {name}]...")
        try:
            frame = parse_structural_frame(dxf_path, clip=clip, encoding='cp949', extract_grid=True)
            
            # 1. Beams
            b_total = len(frame.beams)
            b_matched = len([b for b in frame.beams if b.symbol != "NOBEAM" and b.width > 0])
            total_stats['beams'][0] += b_total
            total_stats['beams'][1] += b_matched
            
            # 2. Columns
            c_total = len(frame.columns)
            c_matched = len([c for c in frame.columns if c.symbol != "NOCOL"])
            total_stats['cols'][0] += c_total
            total_stats['cols'][1] += c_matched
            
            # 3. Slabs
            s_total = len(frame.slab_outlines)
            s_matched = len([s for s in frame.slab_outlines if s.symbol != "NOSLAB"])
            total_stats['slabs'][0] += s_total
            total_stats['slabs'][1] += s_matched
            
            print(f"  - Beams: {b_matched}/{b_total} ({ (b_matched/b_total*100) if b_total>0 else 0:.1f}%)")
            print(f"  - Columns: {c_matched}/{c_total} ({ (c_matched/c_total*100) if c_total>0 else 0:.1f}%)")
            print(f"  - Slabs: {s_matched}/{s_total} ({ (s_matched/s_total*100) if s_total>0 else 0:.1f}%)")
            
        except Exception as e:
            print(f"  [ERROR] {name} 감사 실패: {e}")
            
    print("\n"+"="*70)
    print("  [FINAL STRUCTURAL INTEGRITY]")
    for key, (tot, mat) in total_stats.items():
        rate = (mat/tot*100) if tot > 0 else 0
        print(f"  - {key.upper():<6}: {mat:>4} / {tot:>4} ({rate:>5.1f}%)")
    
    grand_total = sum(v[0] for v in total_stats.values())
    grand_matched = sum(v[1] for v in total_stats.values())
    overall = (grand_matched/grand_total*100) if grand_total > 0 else 0
    print("-"*70)
    print(f"  [OVERALL SCORE] 실질 구조체 정합도: {overall:.1f}%")
    print("="*70)

if __name__ == "__main__":
    sys.path.append(os.getcwd())
    run_audit()
