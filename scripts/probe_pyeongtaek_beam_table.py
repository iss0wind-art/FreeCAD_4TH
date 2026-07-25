import ezdxf
import os
import sys
import re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S35-001~019 보 일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 보 일람표 텍스트 스캔 시작...")
    if not os.path.exists(dxf_path):
        return

    doc = ezdxf.readfile(dxf_path, encoding='utf-8', errors='replace')
    msp = doc.modelspace()

    texts = []
    for e in iter_all(msp):
        if e.dxftype() in ('TEXT', 'MTEXT'):
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if txt:
                pos = getattr(e.dxf, 'insert', None)
                if pos:
                    texts.append((txt, round(pos.x), round(pos.y), e.dxf.layer))

    print(f"총 {len(texts)}개의 텍스트 엔티티 검출.")
    
    # 보 패턴 매칭 (G1, B1, CG1, RG1 등)
    beam_pattern = re.compile(r'\b([EP]?[GB]G?\d+[A-Z]?)\b', re.IGNORECASE)
    # 크기 패턴 (500x700, 500*700, 500/700 등)
    size_pattern = re.compile(r'\b(\d{3,4})\s*[xX*/]\s*(\d{3,4})\b')
    
    matched_beams = []
    matched_sizes = []
    
    for txt, x, y, layer in texts:
        if beam_pattern.search(txt) and not any(k in txt for k in ['강도', '철근', 'fck', '띠']):
            matched_beams.append((txt, x, y, layer))
        if size_pattern.search(txt):
            matched_sizes.append((txt, x, y, layer))

    print(f"\n[보 기호 패턴 매칭 텍스트 샘플 ({len(matched_beams)}개)]")
    for txt, x, y, layer in sorted(matched_beams, key=lambda p: (p[2], p[1]))[:30]:
        print(f"  텍스트: {txt:15s} | 좌표: ({x:8d}, {y:8d}) | 레이어: {layer}")

    print(f"\n[단면 치수 패턴 매칭 텍스트 샘플 ({len(matched_sizes)}개)]")
    for txt, x, y, layer in sorted(matched_sizes, key=lambda p: (p[2], p[1]))[:30]:
        print(f"  텍스트: {txt:15s} | 좌표: ({x:8d}, {y:8d}) | 레이어: {layer}")

if __name__ == "__main__":
    main()
