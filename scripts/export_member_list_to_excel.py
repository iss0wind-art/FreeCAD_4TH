
import sys
import os
import math
import pandas as pd
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.safe_reader import safe_readfile

def export_to_excel():
    above_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    below_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    
    output_dir = "C:/Users/USER/.gemini/antigravity/artifacts"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"BOQ_Member_List_{datetime.now().strftime('%y%m%d_%H%M')}.xlsx")
    
    print(f"Exporting members to {output_path}...")
    
    extractor = StructuralExtractor()
    
    # 1. 지상 데이터 추출
    print("  Processing Aboveground (101-Dong)...")
    res_above = extractor.extract(safe_readfile(above_path))
    
    # 2. 지하 데이터 추출
    print("  Processing Underground (Parking Lot)...")
    res_below = extractor.extract(safe_readfile(below_path))
    
    # --- 데이터 준비 ---
    
    # Columns
    cols_data = []
    for c in res_above.columns:
        cols_data.append({'구분': '지상(101동)', 'ID': id(c), '심볼': c.symbol, 'CX': c.cx, 'CY': c.cy, 'W': c.w, 'H': c.h, '레이어': c.layer})
    for c in res_below.columns:
        cols_data.append({'구분': '지하(주차장)', 'ID': id(c), '심볼': c.symbol, 'CX': c.cx, 'CY': c.cy, 'W': c.w, 'H': c.h, '레이어': c.layer})
        
    # Beams
    beams_data = []
    for b in res_above.beams:
        beams_data.append({'구분': '지상(101동)', '심볼': b.symbol, 'W': b.width, 'H': b.height, 'L': b.length, 'X0': b.x0, 'Y0': b.y0, 'X1': b.x1, 'Y1': b.y1})
    for b in res_below.beams:
        beams_data.append({'구분': '지하(주차장)', '심볼': b.symbol, 'W': b.width, 'H': b.height, 'L': b.length, 'X0': b.x0, 'Y0': b.y0, 'X1': b.x1, 'Y1': b.y1})
        
    # Walls
    walls_data = []
    for w in res_above.shear_walls:
        l = math.hypot(w.centerline_p2[0]-w.centerline_p1[0], w.centerline_p2[1]-w.centerline_p1[1])
        walls_data.append({'구분': '지상(101동)', '두께': w.thickness, '길이': l, 'X0': w.centerline_p1[0], 'Y0': w.centerline_p1[1], 'X1': w.centerline_p2[0], 'Y1': w.centerline_p2[1]})
    for w in res_below.shear_walls:
        l = math.hypot(w.centerline_p2[0]-w.centerline_p1[0], w.centerline_p2[1]-w.centerline_p1[1])
        walls_data.append({'구분': '지하(주차장)', '두께': w.thickness, '길이': l, 'X0': w.centerline_p1[0], 'Y0': w.centerline_p1[1], 'X1': w.centerline_p2[0], 'Y1': w.centerline_p2[1]})

    # Slabs
    slabs_data = []
    for s in res_above.slab_outlines:
        slabs_data.append({'구분': '지상(101동)', '심볼': s.symbol, '면적(m2)': s.area_m2, '레이어': s.layer})
    for s in res_below.slab_outlines:
        slabs_data.append({'구분': '지하(주차장)', '심볼': s.symbol, '면적(m2)': s.area_m2, '레이어': s.layer})

    # --- 엑셀 저장 ---
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(cols_data).to_excel(writer, sheet_name='기둥_Columns', index=False)
        pd.DataFrame(beams_data).to_excel(writer, sheet_name='보_Beams', index=False)
        pd.DataFrame(walls_data).to_excel(writer, sheet_name='벽체_Walls', index=False)
        pd.DataFrame(slabs_data).to_excel(writer, sheet_name='슬래브_Slabs', index=False)
        
    print(f"Excel file created successfully: {output_path}")
    return output_path

if __name__ == "__main__":
    export_to_excel()
