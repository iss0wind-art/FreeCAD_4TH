import ezdxf
import os
import sys
import re
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S35-001~019 보 일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 고유 텍스트 조사 시작...")
    if not os.path.exists(dxf_path):
        return

    doc = ezdxf.readfile(dxf_path, encoding='utf-8', errors='replace')
    msp = doc.modelspace()

    texts = []
    for e in iter_all(msp):
        if e.dxftype() in ('TEXT', 'MTEXT'):
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if txt:
                texts.append(txt)

    print(f"전체 텍스트 엔티티 개수: {len(texts)}")
    
    # 300~1200 사이의 숫자를 포함하는 고유 텍스트와 빈도수 분석
    num_pattern = re.compile(r'\b(300|400|500|600|700|800|900|1000|1100|1200)\b')
    
    matched_texts = [t for t in texts if num_pattern.search(t)]
    unique_cnt = Counter(matched_texts)
    
    print(f"\n[치수 유력 숫자 포함 텍스트 (총 {len(matched_texts)}개, 고유 {len(unique_cnt)}종)]")
    for txt, count in unique_cnt.most_common(50):
        print(f"  텍스트: {txt:30s} | 빈도: {count}회")

if __name__ == "__main__":
    main()
