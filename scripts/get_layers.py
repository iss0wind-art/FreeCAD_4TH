
import ezdxf
dxf_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
doc = ezdxf.readfile(dxf_path, encoding='cp949')
layers = sorted(list(set(e.dxf.layer for e in doc.modelspace())))
with open("d:/Git/FreeCAD_4TH/layers.txt", "w", encoding='utf-8', errors='replace') as f:
    for L in layers:
        f.write(L + "\n")
print(f"Written {len(layers)} layers.")
