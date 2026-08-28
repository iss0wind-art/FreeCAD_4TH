import ezdxf
from core.dxf_parser.safe_reader import safe_readfile

def search_text_in_blocks(filepath):
    print(f"[{filepath}] 블록 내부 텍스트 딥 스캔...")
    doc = safe_readfile(filepath)
    
    texts = []
    
    # 1. Modelspace 탐색
    for e in doc.modelspace().query('TEXT MTEXT'):
        texts.append(e.dxf.text if e.dxftype() == 'TEXT' else e.text)
        
    # 2. 모든 Block 내부 탐색
    for block in doc.blocks:
        for e in block.query('TEXT MTEXT'):
            texts.append(e.dxf.text if e.dxftype() == 'TEXT' else e.text)
            
    # 3. Attributes 탐색
    for e in doc.modelspace().query('INSERT'):
        for attrib in e.attribs:
            texts.append(attrib.dxf.text)
            
    # 필터링 (숫자가 포함된 층고/레벨 관련 텍스트)
    import re
    # 층고(2000~6000)처럼 보이는 숫자 단독 표기나 SL, FL 등
    pattern = re.compile(r'(SL|FL|EL|THK|층고|CH|^\d{4}$)', re.IGNORECASE)
    
    found = []
    for t in texts:
        if type(t) is str:
            t_clean = t.strip()
            if pattern.search(t_clean) and len(t_clean) < 15:
                found.append(t_clean)
                
    from collections import Counter
    cnt = Counter(found)
    print("\n[발견된 주요 텍스트 (빈도순)]")
    for txt, count in cnt.most_common(50):
        print(f"  {txt} : {count}회")

if __name__ == "__main__":
    section_dxf = r"D:\06.3지국 전용방\01. 설계도면\dxf_out\01_건축\A40-010~240 동단면도.dxf"
    search_text_in_blocks(section_dxf)
