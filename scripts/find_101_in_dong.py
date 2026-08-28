
import sys
import os
import ezdxf

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.dxf_parser.safe_reader import safe_readfile

def find_101_dong():
    dong_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    print(f"Searching for '101' in {os.path.basename(dong_path)}...")
    doc = safe_readfile(dong_path)
    msp = doc.modelspace()
    
    hits = []
    for e in msp.query('TEXT MTEXT'):
        txt = e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text()
        if '101' in txt:
            pos = e.dxf.insert
            hits.append((txt, pos.x, pos.y))
            
    print(f"Found {len(hits)} hits:")
    for txt, x, y in sorted(hits, key=lambda h: h[1])[:20]:
        print(f"  '{txt}' at ({x:.0f}, {y:.0f})")

if __name__ == "__main__":
    find_101_dong()
