import os
src = 'd:/Git/FreeCAD_4TH/scratch/recover_extractor.py'
dst = 'd:/Git/FreeCAD_4TH/core/dxf_parser/structural_extractor.py'
with open(src, 'r', encoding='utf-8') as f:
    content = f.read()
with open(dst, 'w', encoding='utf-8') as f:
    f.write(content)
print("Recovery successful")
