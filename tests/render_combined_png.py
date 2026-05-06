"""
통합 STEP을 PNG로 자동 캡처 — FreeCAD GUI 매크로
====================================================

FreeCAD GUI 모드에서만 saveImage 작동. freecadcmd는 GUI 없어 불가.
실행: FreeCAD.exe (GUI) 자동 실행 후 본 매크로 호출.

실행 방법:
  "C:/Program Files/FreeCAD 1.1/bin/FreeCAD.exe" tests/render_combined_png.py
"""
import os, sys, time

# FreeCAD에서 sys.path에 작업 디렉터리 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import FreeCAD
import FreeCADGui
import Part

STEP = r"D:/Git/FreeCAD_4TH/output/poc_101_combined.step"
OUT_DIR = r"D:/Git/FreeCAD_4TH/output"

# 새 문서
doc = FreeCAD.newDocument('combined_render')

# STEP 로드
shape = Part.read(STEP)
Part.show(shape)
doc.recompute()

# GUI 뷰 설정
gui_doc = FreeCADGui.ActiveDocument
view = gui_doc.ActiveView

# 4 시점 캡처
views = [
    ('iso', 'viewIsometric'),
    ('top', 'viewTop'),
    ('front', 'viewFront'),
    ('right', 'viewRight'),
]

for name, method in views:
    getattr(view, method)()
    view.fitAll()
    time.sleep(0.3)
    out_png = os.path.join(OUT_DIR, f'poc_101_combined_{name}.png')
    view.saveImage(out_png, 1920, 1080, 'White')
    print(f'[PNG] {out_png}')

print('[종결] 4 시점 PNG 캡처 완료')

# 매크로 자동 종료
import sys
sys.exit(0)
