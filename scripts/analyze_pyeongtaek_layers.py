import ezdxf
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.safe_reader import safe_readfile
from core.dxf_parser.structural_filter import classify_layers

def analyze_dxf(filepath):
    print(f"[{os.path.basename(filepath)}] 레이어 분석 시작...")
    if not os.path.exists(filepath):
        print(f"오류: 파일이 존재하지 않습니다: {filepath}")
        return
    doc = safe_readfile(filepath)
    cats = classify_layers(doc)
    
    print("\n[골조 레이어 (structural)]")
    for layer, cnt in sorted(cats['structural'].items(), key=lambda x: -x[1])[:20]:
        print(f"  {layer}: {cnt}개")
        
    print("\n[비골조/차단 레이어 (non_structural)]")
    for layer, cnt in sorted(cats['non_structural'].items(), key=lambda x: -x[1])[:20]:
        print(f"  {layer}: {cnt}개")
        
    print("\n[분류되지 않은 레이어 (unknown)]")
    for layer, cnt in sorted(cats['unknown'].items(), key=lambda x: -x[1])[:20]:
        print(f"  {layer}: {cnt}개")

if __name__ == "__main__":
    dxf_file = r"D:\06.3지국 전용방\02. 평택 고덕\dxf_out\02_구조\S21-001~012 구조평면도.dxf"
    analyze_dxf(dxf_file)
