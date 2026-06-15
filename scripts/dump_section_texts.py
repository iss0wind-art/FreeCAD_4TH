import ezdxf
from core.dxf_parser.safe_reader import safe_readfile

def dump_texts(filepath):
    print(f"[{filepath}] 전체 텍스트 덤프...")
    doc = safe_readfile(filepath)
    
    texts = []
    # 텍스트, MTEXT, 속성(ATTRIB) 전부 탐색
    for e in doc.modelspace():
        if e.dxftype() in ('TEXT', 'MTEXT'):
            txt = getattr(e.dxf, 'text', getattr(e, 'text', '')).strip()
            if txt:
                texts.append((e.dxf.insert.y, txt))
        elif e.dxftype() == 'INSERT':
            # Block attributes
            for attrib in e.attribs:
                txt = attrib.dxf.text.strip()
                if txt:
                    texts.append((e.dxf.insert.y, txt))
                    
    texts.sort(key=lambda item: item[0], reverse=True)
    
    # 텍스트들을 50개만 샘플로 출력 (SL, 층, 높이와 관련된 텍스트 위주로 필터링)
    keywords = ['SL', 'FL', 'EL', '층', 'THK', '2900', '3000', '3300', '4200', '4500']
    filtered = [txt for y, txt in texts if any(k in txt for k in keywords)]
    
    unique_filtered = list(dict.fromkeys(filtered)) # 중복 제거 보존
    
    print("\n[관련 텍스트 샘플]")
    for t in unique_filtered[:50]:
        print(f"  {t}")

if __name__ == "__main__":
    section_dxf = r"D:\06.3지국 전용방\01. 설계도면\dxf_out\01_건축\A40-010~240 동단면도.dxf"
    dump_texts(section_dxf)
