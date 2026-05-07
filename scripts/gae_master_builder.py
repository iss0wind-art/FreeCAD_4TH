"""
gae_master_builder.py — 개팀장 마스터 빌더 (산출식 근거 포함 버전)
===================================================================
역산(Top-Down)을 수행한 후, 단순 총합이 아닌 각 부재별로
정확한 [산출식]을 포함하여 CSV 물량산출서를 생성한다.
"""
import sys, os, time, csv
import ezdxf

FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"
sys.path.insert(0, FREECAD_BIN)
import FreeCAD
import Part

def get_columns(dxf_path, offset_x=0, offset_y=0, prefix="PKG"):
    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
    except:
        doc = ezdxf.readfile(dxf_path, encoding='utf-8')
        
    cols = []
    idx = 1
    for e in doc.modelspace().query('LWPOLYLINE'):
        if 'COL' in e.dxf.layer.upper() and 'NAME' not in e.dxf.layer.upper() and e.is_closed:
            pts = [(p[0], p[1]) for p in e.get_points()]
            if len(pts) >= 4:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                w, d = max(xs) - min(xs), max(ys) - min(ys)
                if 100 < w < 3000 and 100 < d < 3000:
                    cx = min(xs) + w/2 + offset_x
                    cy = min(ys) + d/2 + offset_y
                    cols.append((f"{prefix}-C{idx:03d}", cx, cy, w, d))
                    idx += 1
    return cols

def main():
    print("[1] 데이터 파싱 및 좌표 정렬")
    pkg_dxf = r"E:\Git\dxf_out\02_구조\260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    dong_dxf = r"E:\Git\dxf_out\02_구조\S30-001~010-101동 구조평면도.dxf"
    
    DONG_TX, DONG_TY = 247229, -1390677
    
    pkg_cols = get_columns(pkg_dxf, 0, 0, "PKG")
    dong_cols = get_columns(dong_dxf, DONG_TX, DONG_TY, "101D")
    all_cols = pkg_cols + dong_cols
    
    print("[2] Top-Down 3D 역산 모델링 가동 (Boolean Cut)")
    SL_TOP, SL_BOT, SLAB_T = 3000, 0, 200
    
    xs, ys = [c[1] for c in all_cols], [c[2] for c in all_cols]
    if not xs: return
    
    slab = Part.makeBox(max(xs)-min(xs)+2000, max(ys)-min(ys)+2000, SLAB_T)
    slab.translate(FreeCAD.Vector(min(xs)-1000, min(ys)-1000, SL_TOP - SLAB_T))
    
    solids = []
    boq_records = []
    
    for name, cx, cy, w, d in all_cols:
        col = Part.makeBox(w, d, SL_TOP - SL_BOT)
        col.translate(FreeCAD.Vector(cx - w/2, cy - d/2, SL_BOT))
        
        # 슬라브 자르기
        cut_col = col.cut(slab)
        solids.append(cut_col)
        
        # 역산된 실제 높이 (BoundingBox ZLength)
        # 만약 보(Beam)와 겹쳤다면 높이가 다를 것임
        h_cut = cut_col.BoundBox.ZLength
        
        # 정미 체적 / 면적
        vol_m3 = cut_col.Volume / 1e9
        
        formwork_m2 = 0.0
        for face in cut_col.Faces:
            if abs(face.normalAt(0,0).z) < 0.01:
                formwork_m2 += face.Area / 1e6
                
        # 산출식 (명확한 수식)
        w_m, d_m, h_m = w/1000, d/1000, h_cut/1000
        vol_formula = f"{w_m:.3f} * {d_m:.3f} * {h_m:.3f}"
        form_formula = f"({w_m:.3f} + {d_m:.3f}) * 2 * {h_m:.3f}"
        
        boq_records.append({
            '부재ID': name,
            '좌표X': f"{cx:.0f}",
            '좌표Y': f"{cy:.0f}",
            '가로(W)': f"{w_m:.3f}",
            '세로(D)': f"{d_m:.3f}",
            '역산높이(H)': f"{h_m:.3f}",
            '콘크리트(m3)': f"{vol_m3:.3f}",
            '콘크리트_산출식': vol_formula,
            '거푸집(m2)': f"{formwork_m2:.3f}",
            '거푸집_산출식': form_formula
        })
        
    print("[3] 산출식 근거 포함 BOQ(CSV) 생성")
    csv_path = r"output\boq_formulas_gae.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=boq_records[0].keys())
        writer.writeheader()
        writer.writerows(boq_records)
        
    out_step = r"output\master_topdown_aligned.step"
    Part.makeCompound(solids + [slab]).exportStep(out_step)
    print(f"[완료] STEP: {out_step}")
    print(f"[완료] 산출내역: {csv_path}")

if __name__ == '__main__':
    main()
