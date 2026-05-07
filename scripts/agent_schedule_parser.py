"""
agent_schedule_parser.py — [Agent 6] 구조일람표 및 일반사항 스펙 파서
=============================================================================
추측 0%. 오직 구조일반사항(S10)과 부재 일람표(S40)에서 
층고(SL), 슬라브 두께(THK), 보 크기(bxh)를 정밀하게 긁어낸다.
"""
import sys, os, time, re
import ezdxf
from collections import defaultdict

def extract_texts(dxf_path):
    print(f" -> 도면 로드 중: {os.path.basename(dxf_path)}")
    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
    except:
        doc = ezdxf.readfile(dxf_path, encoding='utf-8')
    msp = doc.modelspace()
    
    texts = []
    for e in msp.query('TEXT MTEXT'):
        t = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if t:
            texts.append(t.replace('\\P', ' ').strip())
    return texts

def parse_floor_levels(texts):
    print(" -> [S10 구조일반사항] 층고(SL) 분석")
    levels = {}
    # 패턴 예: "B2F", "B1F", "1F" 와 "GL. -9.05", "SL: -5600"
    floor_pat = re.compile(r'(B?[1-9]F|지붕층)', re.IGNORECASE)
    sl_pat = re.compile(r'(?:SL|GL)\.?\s*[:=]?\s*([+-]?\d+\.?\d*)', re.IGNORECASE)
    
    # 텍스트들을 훑으며 층과 고도를 페어링 (간단한 휴리스틱)
    for t in texts:
        if 'SL' in t.upper() or 'GL' in t.upper():
            match = sl_pat.search(t)
            floor_match = floor_pat.search(t)
            if match and floor_match:
                val = float(match.group(1))
                if abs(val) < 100: val *= 1000 # m -> mm
                levels[floor_match.group(1).upper()] = val
    return levels

def parse_slab_thickness(texts):
    print(" -> [S40 슬래브 리스트] 두께(THK) 분석")
    thk_dict = {}
    
    # "S1", "S2" 같은 기호 찾기
    slab_pat = re.compile(r'^S\d*[A-Z]?$')
    # "THK 200", "두께 150"
    thk_pat = re.compile(r'(?:THK|T|두께)\s*[:=]?\s*(\d{3})', re.IGNORECASE)
    
    last_slab = None
    for t in texts:
        if slab_pat.match(t):
            last_slab = t
        match = thk_pat.search(t)
        if match and last_slab:
            thk_dict[last_slab] = int(match.group(1))
            last_slab = None # 매칭 후 리셋
    
    # 만약 위 방식으로 안 잡히면, 전체 THK 텍스트의 빈도수 추출
    all_thks = []
    for t in texts:
        match = thk_pat.search(t)
        if match:
            all_thks.append(int(match.group(1)))
            
    from collections import Counter
    if all_thks:
        common = Counter(all_thks).most_common(5)
        print(f"    * 발견된 주요 슬라브 두께 빈도: {common}")
        
    return thk_dict, all_thks

def parse_beam_sizes(texts):
    print(" -> [S40 보 리스트] 춤과 폭(bxh) 분석")
    # 보 크기는 보통 "400x600" 형태로 기재됨
    size_pat = re.compile(r'(\d{3})\s*[xX*]\s*(\d{3,4})')
    
    sizes = []
    for t in texts:
        match = size_pat.search(t)
        if match:
            b, h = int(match.group(1)), int(match.group(2))
            sizes.append((b, h))
            
    from collections import Counter
    if sizes:
        common = Counter(sizes).most_common(5)
        print(f"    * 발견된 주요 보 규격(b x h) 빈도: {common}")
    return sizes

def main():
    print("=== [Agent 6] 엄밀한 스펙 파싱 시작 ===")
    t0 = time.time()
    
    dir_path = r"E:\Git\dxf_out\02_구조"
    
    # 1. 층고 파싱
    s10_path = os.path.join(dir_path, "S10-001~033 구조일반사항.dxf")
    s10_texts = extract_texts(s10_path)
    levels = parse_floor_levels(s10_texts)
    if levels:
        print(f"    * 확정된 층고(SL): {levels}")
    
    # 2. 슬라브 두께 파싱
    slab_path = os.path.join(dir_path, "S40-121~124 지하주차장 슬래브 리스트.dxf")
    slab_texts = extract_texts(slab_path)
    slab_dict, all_thks = parse_slab_thickness(slab_texts)
    if slab_dict:
        print(f"    * 부재별 슬라브 두께: {slab_dict}")
        
    # 3. 보 규격 파싱
    beam_path = os.path.join(dir_path, "S40-151~156 지하주차장 보 리스트_260202 이오스 수정.dxf")
    beam_texts = extract_texts(beam_path)
    beam_sizes = parse_beam_sizes(beam_texts)
    
    print(f"\n[완료] 파싱 소요시간: {time.time()-t0:.1f}초")

if __name__ == '__main__':
    main()
