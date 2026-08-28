import re
from core.dxf_parser.safe_reader import safe_readfile

def extract_levels_from_dxf(filepath):
    print(f"[{filepath}] 표고/층고 텍스트 스캔 시작...")
    doc = safe_readfile(filepath)
    
    # 층 표기 (예: 1F, B1F, 지붕층, SL, FL 등)
    target_pattern = re.compile(r'(B?\d+F|SL|FL|EL|지하|지상|층고|PH|옥상|지붕|기준)', re.IGNORECASE)
    
    found_texts = []
    
    for e in doc.modelspace():
        if e.dxftype() in ('TEXT', 'MTEXT'):
            txt = getattr(e.dxf, 'text', getattr(e, 'text', '')).strip()
            if target_pattern.search(txt) and len(txt) < 30:
                found_texts.append((e.dxf.insert.x, e.dxf.insert.y, txt))
                
    # Y 좌표를 기준으로 내림차순 정렬 (일반적으로 상층이 Y값이 높음)
    found_texts.sort(key=lambda item: item[1], reverse=True)
    
    # 상위 100개만 출력해본다 (분석용)
    print(f"--- 총 {len(found_texts)} 개 텍스트 발견 ---")
    
    # 중복 텍스트 묶기 (같은 라인 Y좌표에 있는 텍스트들)
    # y좌표가 비슷한(오차 100) 텍스트끼리 묶기
    y_groups = {}
    for x, y, txt in found_texts:
        y_key = round(y / 100) * 100
        if y_key not in y_groups:
            y_groups[y_key] = []
        y_groups[y_key].append(txt)
        
    for y, texts in list(y_groups.items())[:50]:
        unique_texts = list(set(texts))
        print(f"Y={y}: {unique_texts}")

if __name__ == "__main__":
    col_list_dxf = r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-471~491 101~112동 기둥리스트.dxf"
    extract_levels_from_dxf(col_list_dxf)
