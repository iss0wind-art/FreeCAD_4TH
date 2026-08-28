import os, sys, ezdxf
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"

SHEETS = {
    'B2': {'sw': (247250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0},
    'B1': {'sw': (877250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0},
}

def iter_all(c, d=0, m=8):
    if d > m:
        return
    for e in c:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), d + 1, m)
            except Exception:
                pass
        else:
            yield e

def analyze_sheet_structural_layers():
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    
    print("Caching all entities from INSERT blocks...")
    all_entities = list(iter_all(msp))
    print(f"Total flattened entities: {len(all_entities)}")
    
    keywords = ['BEAM', 'GIRDER', 'COL', 'SLAB', 'WALL', 'PC']
    
    for name, sheet in SHEETS.items():
        sw = sheet['sw']; w = sheet['w']; h = sheet['h']
        ix0, iy0 = sw[0] + w * 0.02, sw[1] + h * 0.02
        ix1, iy1 = sw[0] + w * 0.98, sw[1] + h * 0.98
        
        sheet_layers = Counter()
        for e in all_entities:
            try:
                ly = e.dxf.layer
            except Exception:
                continue
            et = e.dxftype()
            if et == 'LINE':
                try:
                    p = e.dxf.start
                    if ix0 <= p.x <= ix1 and iy0 <= p.y <= iy1:
                        sheet_layers[ly] += 1
                except Exception:
                    pass
            elif et == 'LWPOLYLINE':
                try:
                    pts = list(e.get_points())
                    if pts:
                        p0 = pts[0]
                        if ix0 <= p0[0] <= ix1 and iy0 <= p0[1] <= iy1:
                            sheet_layers[ly] += 1
                except Exception:
                    pass
                    
        print(f"\n================ Sheet: {name} (Structural / PC Layers) ================")
        print(f"{'Layer Name':<50} | {'Count':<8}")
        print("-" * 61)
        for ly, cnt in sorted(sheet_layers.items(), key=lambda x: -x[1]):
            ly_upper = ly.upper()
            if any(k in ly_upper for k in keywords):
                print(f"{ly:<50} | {cnt:<8}")

if __name__ == '__main__':
    analyze_sheet_structural_layers()
