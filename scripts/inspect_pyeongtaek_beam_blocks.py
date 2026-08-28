import ezdxf
import os
import sys
import re
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.safe_reader import safe_readfile

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S35-001~019 보 일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 블록 정의 내부 고유 텍스트 조사 시작...")
    if not os.path.exists(dxf_path):
        return

    doc = safe_readfile(dxf_path)
    
    texts = []
    # 모든 Block 내부 탐색
    for block in doc.blocks:
        # 익명 블록(*U 등)이나 테이블 관련 블록 정의 내부의 TEXT/MTEXT 수집
        for e in block.query('TEXT MTEXT'):
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if txt:
                texts.append(txt)

    print(f"블록 정의 내 전체 텍스트 개수: {len(texts)}")
    
    num_pattern = re.compile(r'\b(300|400|500|600|700|800|900|1000|1100|1200)\b')
    matched_texts = [t for t in texts if num_pattern.search(t)]
    unique_cnt = Counter(matched_texts)
    
    print(f"\n[블록 내부 치수 유력 숫자 포함 텍스트 (총 {len(matched_texts)}개, 고유 {len(unique_cnt)}종)]")
    for txt, count in unique_cnt.most_common(50):
        print(f"  텍스트: {txt:30s} | 빈도: {count}회")

if __name__ == "__main__":
    main()
