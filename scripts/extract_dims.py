import math
from core.dxf_parser.safe_reader import safe_readfile

def extract_dimensions(filepath):
    print(f"[{filepath}] DIMENSION 엔티티 스캔...")
    doc = safe_readfile(filepath)
    
    dims = []
    
    for e in doc.modelspace():
        if e.dxftype() == 'DIMENSION':
            # ezdxf에서 dimension 텍스트를 가져오려면 e.dxf.text(사용자 지정 텍스트) 
            # 또는 측정값 (e.get_measurement())을 확인해야 함.
            text = e.dxf.text if e.dxf.hasattr('text') and e.dxf.text not in ('', '<>') else None
            try:
                measurement = e.get_measurement()
            except:
                measurement = None
                
            val = text if text else str(round(measurement)) if measurement else "N/A"
            
            # 수직(Vertical) 치수인지 확인 (angle이나 x/y 좌표 비교)
            # ezdxf의 dimension은 종류가 다양하므로 일단 값만 전부 뽑아서 빈도를 본다.
            if val != "N/A" and val.isdigit():
                dims.append(int(val))
                
    # 빈도수 분석
    from collections import Counter
    cnt = Counter(dims)
    print("\n[가장 많이 사용된 치수 Top 20]")
    for val, count in cnt.most_common(20):
        print(f"  {val} mm : {count} 회")

if __name__ == "__main__":
    col_list_dxf = r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-471~491 101~112동 기둥리스트.dxf"
    extract_dimensions(col_list_dxf)
