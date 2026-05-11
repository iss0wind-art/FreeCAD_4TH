
import sys
import os
import ezdxf

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.dxf_parser.safe_reader import safe_readfile

def find_101():
    pkg_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    print(f"Searching for '101' in {os.path.basename(pkg_path)}...")
    doc = safe_readfile(pkg_path)
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
    find_101()
