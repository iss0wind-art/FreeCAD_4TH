"""
agent_level_parser.py — [Agent 5] 레벨/층고 및 슬라브 두께 정밀 텍스트 파서
=============================================================================
추측 금지. 도면에 적혀 있는 TEXT/MTEXT 엔티티를 긁어서
정확한 바닥 고도(SL)와 슬라브 두께(THK)를 수학적으로 확정한다.
"""
import sys, os, time, re
import ezdxf

def parse_levels(dxf_path):
    print(f"[Agent 5] 레벨(SL) 및 두께 파싱 시작: {os.path.basename(dxf_path)}")
    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
    except:
        doc = ezdxf.readfile(dxf_path, encoding='utf-8')
    msp = doc.modelspace()
    
    sl_texts = []
    thk_texts = []
    
    # 정규식 패턴 (SL: -5.60, SL -5600, THK=200, T=150 등)
    sl_pattern = re.compile(r'SL\s*[:=]?\s*([+-]?\d+\.?\d*)', re.IGNORECASE)
    thk_pattern = re.compile(r'(?:THK|T)\s*[:=]?\s*(\d+)', re.IGNORECASE)
    
    for e in msp.query('TEXT MTEXT'):
        text = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        if not text: continue
        
        # 줄바꿈 및 특수문자 제거
        text = text.replace('\\P', ' ').strip()
        
        sl_match = sl_pattern.search(text)
        if sl_match:
            val = float(sl_match.group(1))
            # m 단위로 적혀있으면 mm로 변환 (예: -5.60 -> -5600)
            if abs(val) < 100: val *= 1000
            sl_texts.append(val)
            
        thk_match = thk_pattern.search(text)
        if thk_match:
            thk_texts.append(float(thk_match.group(1)))
            
    print(f" -> 발견된 SL 텍스트 수: {len(sl_texts)}건")
    if sl_texts:
        # 가장 빈도수가 높은 SL 값 채택 (대표 층고)
        from collections import Counter
        sl_most_common = Counter(sl_texts).most_common(3)
        print(f" -> 주요 SL 분포: {sl_most_common}")
        
    print(f" -> 발견된 슬라브 두께(THK) 텍스트 수: {len(thk_texts)}건")
    if thk_texts:
        thk_most_common = Counter(thk_texts).most_common(3)
        print(f" -> 주요 슬라브 두께 분포: {thk_most_common}")
        
    return sl_texts, thk_texts

if __name__ == '__main__':
    pkg_dxf = r"E:\Git\dxf_out\02_구조\260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    parse_levels(pkg_dxf)
