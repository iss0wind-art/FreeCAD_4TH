"""
agent_schedule_parser_v2.py — [Agent 6] 심층 블록 폭파 스펙 파서
===================================================================
도면의 단순 텍스트뿐만 아니라, 테이블(일람표)을 구성하는 INSERT 블록과
내부 속성(Attribute)까지 재귀적으로 폭파하여 텍스트를 추출한다.
"""
import sys, os, time, re
import ezdxf
from collections import Counter

def extract_deep_texts(dxf_path):
    print(f" -> 딥 스캔 중(블록 폭파): {os.path.basename(dxf_path)}")
    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
    except:
        doc = ezdxf.readfile(dxf_path, encoding='utf-8')
    msp = doc.modelspace()
    
    texts = []
    def add_text(t):
        if t and t.strip():
            # MTEXT의 특수문자 제거
            clean = re.sub(r'\\[A-Za-z0-9~]+;?', '', t)
            clean = clean.replace('\\P', ' ').strip()
            texts.append(clean)

    for e in msp:
        if e.dxftype() in ('TEXT', 'MTEXT'):
            add_text(e.dxf.text if e.dxftype() == 'TEXT' else e.text)
        elif e.dxftype() == 'INSERT':
            # 1. 속성(Attribute) 추출
            if e.has_attrib:
                for attrib in e.attribs:
                    add_text(attrib.dxf.text)
            # 2. 블록 원본(Definition) 내부 텍스트 추출
            try:
                block = doc.blocks[e.dxf.name]
                for be in block:
                    if be.dxftype() in ('TEXT', 'MTEXT'):
                        add_text(be.dxf.text if be.dxftype() == 'TEXT' else be.text)
            except:
                pass
    return texts

def parse_s10_levels(texts):
    print(" -> [S10] 층고(SL) 데이터 분석 중...")
    floor_sl = {}
    
    # 예: B2F, B1F, 1F 와 -9050, -5600, 370 매칭
    pat_floor = re.compile(r'B?[1-9]F|지붕층', re.IGNORECASE)
    # GL. -9.05, SL: -5600 등
    pat_val = re.compile(r'(?:SL|GL|지상|지하)[^\d+-]*([+-]?\d{1,4}(?:\.\d{1,3})?)')
    
    buffer = ""
    for t in texts:
        buffer += " " + t
        
    # 대량의 텍스트 풀에서 B1F와 숫자 간의 근접도를 찾음 (휴리스틱)
    # 가장 확실한 층고 표기 찾기
    found_vals = pat_val.findall(buffer)
    valid_sl = []
    for v in found_vals:
        try:
            val = float(v)
            if abs(val) < 100: val *= 1000 # m -> mm 변환
            if -20000 < val < 20000 and val % 10 == 0:
                valid_sl.append(int(val))
        except: pass
        
    if valid_sl:
        print(f"    * 유력한 레벨(SL) 후보군: {Counter(valid_sl).most_common(5)}")
        
    return valid_sl

def parse_s40_slabs(texts):
    print(" -> [S40] 슬라브 두께 데이터 분석 중...")
    thk_vals = []
    # 두께 150, THK 200, THK=250 등
    pat_thk = re.compile(r'(?:THK|T|두께)\s*[:=]?\s*(\d{3})', re.IGNORECASE)
    
    for t in texts:
        match = pat_thk.search(t)
        if match:
            thk_vals.append(int(match.group(1)))
            
    # 숫자 단독으로 표기된 경우 (150, 200, 250 등)
    pat_num = re.compile(r'^([1-3]\d{2})$')
    for t in texts:
        if pat_num.match(t):
            thk_vals.append(int(t))
            
    if thk_vals:
        print(f"    * 슬라브 두께 분포: {Counter(thk_vals).most_common(5)}")
    return thk_vals

def main():
    print("=== [Agent 6 V2] 딥 스캔: 블록 폭파 및 텍스트 채굴 ===")
    t0 = time.time()
    dir_path = r"E:\Git\dxf_out\02_구조"
    
    s10_path = os.path.join(dir_path, "S10-001~033 구조일반사항.dxf")
    s40_slab = os.path.join(dir_path, "S40-121~124 지하주차장 슬래브 리스트.dxf")
    
    t1 = extract_deep_texts(s10_path)
    parse_s10_levels(t1)
    
    t2 = extract_deep_texts(s40_slab)
    parse_s40_slabs(t2)
    
    print(f"\n[완료] 파싱 소요시간: {time.time()-t0:.2f}초")

if __name__ == '__main__':
    main()
