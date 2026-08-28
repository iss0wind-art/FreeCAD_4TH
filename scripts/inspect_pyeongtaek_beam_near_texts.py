import ezdxf
import os
import sys
import re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S35-001~019 보 일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 보 주변 텍스트 분석 시작...")
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
                    texts.append((txt, pos.x, pos.y, e.dxf.layer))

    # B0 근처 (X: 9692, Y: 10904) 정찰
    cx, cy = 9692, 10904
    print(f"\n=== 보 B0 부근 텍스트 (X={cx}, Y={cy}) ===")
    near_texts = []
    for txt, x, y, layer in texts:
        dx = abs(x - cx)
        dy = y - cy
        if dx < 10000 and -10000 < dy < 10000:
            near_texts.append((txt, dx, dy, x, y, layer))
            
    for txt, dx, dy, rx, ry, layer in sorted(near_texts, key=lambda p: (-p[4], p[3])):
        marker = "★" if rx == cx and ry == cy else "  "
        print(f"  {marker} {txt:25s} | 상대 dy: {dy:6.0f} (dx: {dx:5.0f}) | 절대좌표: ({rx:8.0f}, {ry:8.0f}) | 레이어: {layer}")

if __name__ == "__main__":
    main()
