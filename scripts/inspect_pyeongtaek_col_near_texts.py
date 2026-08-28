import ezdxf
import os
import sys
import re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S31-001~009 기둥일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 기둥 주변 텍스트 분석 시작...")
    if not os.path.exists(dxf_path):
        return

    doc = ezdxf.readfile(dxf_path, encoding='cp949', errors='replace')
    msp = doc.modelspace()

    texts = []
    for e in iter_all(msp):
        if e.dxftype() in ('TEXT', 'MTEXT'):
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if txt:
                pos = getattr(e.dxf, 'insert', None)
                if pos:
                    texts.append((txt, pos.x, pos.y, e.dxf.layer))

    # C1, C2 등 기둥 기호 찾기
    col_pattern = re.compile(r'^(C\d+)$', re.IGNORECASE)
    cols = [t for t in texts if col_pattern.match(t[0])]
    
    print(f"찾은 기둥 기호: {[c[0] for c in cols]}")
    
    # 각 기둥 기호 주변 (X차이 3000 이하, Y차이 6000 이하)의 텍스트 나열
    for col_txt, cx, cy, clayer in sorted(cols, key=lambda x: x[0]):
        print(f"\n=== 기둥: {col_txt} 좌표 ({cx:.0f}, {cy:.0f}) 부근 텍스트 ===")
        near_texts = []
        for txt, x, y, layer in texts:
            dx = abs(x - cx)
            dy = y - cy  # 상대적인 위/아래 방향 확인을 위해 dy 보존
            if dx < 4000 and -6000 < dy < 6000:
                near_texts.append((txt, dx, dy, x, y, layer))
        
        # Y좌표 내림차순(위에서 아래로) 정렬
        for txt, dx, dy, rx, ry, layer in sorted(near_texts, key=lambda p: -p[4]):
            marker = "★" if rx == cx and ry == cy else "  "
            print(f"  {marker} {txt:15s} | 상대 dy: {dy:6.0f} (dx: {dx:5.0f}) | 절대좌표: ({rx:8.0f}, {ry:8.0f}) | 레이어: {layer}")

if __name__ == "__main__":
    main()
