import ezdxf
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S31-001~009 기둥일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 기둥일람표 텍스트 스캔 시작...")
    if not os.path.exists(dxf_path):
        print(f"오류: 파일 없음: {dxf_path}")
        return

    doc = ezdxf.readfile(dxf_path, encoding='cp949', errors='replace')
    msp = doc.modelspace()

    # 모든 텍스트 수집
    texts = []
    for e in iter_all(msp):
        if e.dxftype() in ('TEXT', 'MTEXT'):
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if txt:
                pos = getattr(e.dxf, 'insert', None)
                if pos:
                    texts.append((txt, round(pos.x), round(pos.y), e.dxf.layer))

    print(f"총 {len(texts)}개의 텍스트 엔티티 검출.")
    
    # 기둥 번호(예: C1, C2)나 치수 형식(예: 600*600, 600x600, 600, 800)이 포함된 것 필터링
    import re
    col_pattern = re.compile(r'\b(C\d+)\b', re.IGNORECASE)
    size_pattern = re.compile(r'\b(\d{3,4})\s*[xX*]\s*(\d{3,4})\b')
    
    matched_cols = []
    matched_sizes = []
    
    for txt, x, y, layer in texts:
        if col_pattern.search(txt):
            matched_cols.append((txt, x, y, layer))
        if size_pattern.search(txt) or re.search(r'^\d{3,4}$', txt):
            matched_sizes.append((txt, x, y, layer))

    print(f"\n[기둥 패턴 매칭 텍스트 샘플 ({len(matched_cols)}개)]")
    for txt, x, y, layer in sorted(matched_cols, key=lambda p: (p[2], p[1]))[:30]:
        print(f"  텍스트: {txt:15s} | 좌표: ({x:8d}, {y:8d}) | 레이어: {layer}")

    print(f"\n[치수 패턴 매칭 텍스트 샘플 ({len(matched_sizes)}개)]")
    for txt, x, y, layer in sorted(matched_sizes, key=lambda p: (p[2], p[1]))[:30]:
        print(f"  텍스트: {txt:15s} | 좌표: ({x:8d}, {y:8d}) | 레이어: {layer}")

if __name__ == "__main__":
    main()
