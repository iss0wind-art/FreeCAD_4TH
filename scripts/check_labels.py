
import ezdxf
import re

dxf_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
doc = ezdxf.readfile(dxf_path, encoding='cp949')
msp = doc.modelspace()

import sys
sys.path.insert(0, "D:/Git/FreeCAD_4TH")
from core.dxf_parser.entity_scanner import iter_all

print(f"Recursively searching all entities...")

labels = []
for e in iter_all(msp):
    if e.dxftype() in ('TEXT', 'MTEXT'):
        txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
        if re.search(r'([GBC][GBCB]?\d+|S\d+)', txt):
            pos = e.dxf.insert
            labels.append((txt, round(pos.x), round(pos.y)))

print(f"Found {len(labels)} potential labels.")
print("Samples (text, x, y):", labels[:20])
