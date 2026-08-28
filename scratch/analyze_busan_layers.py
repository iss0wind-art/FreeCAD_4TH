import os, sys, ezdxf
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.pc_layer_adapter import classify_layer, PCKind

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"

def main():
    if not os.path.exists(DXF):
        print(f"File not found: {DXF}")
        return
    print(f"Reading {DXF}...")
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    
    # Count entities per layer
    layer_counts = Counter()
    for e in msp:
        try:
            layer_counts[e.dxf.layer] += 1
        except Exception:
            pass
            
    print("\n--- Layer Analysis (Top 50 by Entity Count) ---")
    print(f"{'Layer Name':<40} | {'Count':<8} | {'PC Kind':<12}")
    print("-" * 66)
    
    for layer, count in layer_counts.most_common(50):
        kind, pat = classify_layer(layer)
        print(f"{layer:<40} | {count:<8} | {kind.value:<12}")
        
    print("\n--- All PC Layers ---")
    for layer, count in sorted(layer_counts.items()):
        kind, pat = classify_layer(layer)
        if kind != PCKind.NON_PC:
            print(f"{layer:<40} | {count:<8} | {kind.value:<12} (matched: {pat})")

if __name__ == '__main__':
    main()
