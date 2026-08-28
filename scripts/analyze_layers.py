import ezdxf
from core.dxf_parser.safe_reader import safe_readfile
from core.dxf_parser.structural_filter import is_structural, classify_layers

def analyze_dxf(filepath):
    print(f"[{filepath}] 레이어 정밀 분석 시작...")
    doc = safe_readfile(filepath)
    
    cats = classify_layers(doc)
    
    print("\n[골조 레이어로 분류된 것들 (structural)]")
    for layer, cnt in sorted(cats['structural'].items(), key=lambda x: -x[1]):
        print(f"  {layer}: {cnt}개")
        
    print("\n[비골조 레이어로 차단된 것들 (non_structural)]")
    for layer, cnt in sorted(cats['non_structural'].items(), key=lambda x: -x[1])[:20]:
        print(f"  {layer}: {cnt}개")
        
    print("\n[알 수 없는 레이어 (unknown)]")
    for layer, cnt in sorted(cats['unknown'].items(), key=lambda x: -x[1])[:20]:
        print(f"  {layer}: {cnt}개")

if __name__ == "__main__":
    dxf_file = r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-001~010-101동 구조평면도.dxf"
    analyze_dxf(dxf_file)
