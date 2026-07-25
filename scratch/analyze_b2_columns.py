import os, sys, ezdxf
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"

SHEETS = {
    'B2': {'sw': (247250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0},
    'B1': {'sw': (877250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0},
}

def analyze_b2_columns():
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    
    # B2 영역 필터링
    sheet = SHEETS['B2']
    sw = sheet['sw']; w = sheet['w']; h = sheet['h']
    ix0, iy0 = sw[0] + w * 0.02, sw[1] + h * 0.02
    ix1, iy1 = sw[0] + w * 0.98, sw[1] + h * 0.98
    
    top_types = Counter()
    
    for e in msp:
        try:
            ly = e.dxf.layer
        except:
            continue
        
        px, py = 0, 0
        if e.dxftype() == 'INSERT':
            p = e.dxf.insert
            px, py = p.x, p.y
        elif e.dxftype() == 'LINE':
            p = e.dxf.start
            px, py = p.x, p.y
        elif e.dxftype() == 'LWPOLYLINE':
            pts = list(e.get_points())
            if pts:
                px, py = pts[0][0], pts[0][1]
            else:
                continue
        else:
            continue
            
        if not (ix0 <= px <= ix1 and iy0 <= py <= iy1):
            continue
            
        if ly == '00_COLUMN':
            top_types[e.dxftype()] += 1
                
    print("=== B2 00_COLUMN Top-Level Entities ===")
    for t, cnt in top_types.items():
        print(f"  Type {t}: {cnt}개")
        
if __name__ == '__main__':
    analyze_b2_columns()
