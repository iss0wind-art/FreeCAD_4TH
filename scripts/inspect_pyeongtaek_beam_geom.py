import ezdxf
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S35-001~019 보 일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 1G4 주변 TEXT만 추출 시작...")
    if not os.path.exists(dxf_path):
        return

    doc = ezdxf.readfile(dxf_path, encoding='utf-8', errors='replace')
    msp = doc.modelspace()

    # 1G4 (X=24799.6, Y=10903.8) 주변 텍스트 수집 (가로 ±6000, 세로 ±12000로 세로 범위 확대)
    cx, cy = 24799.6, 10903.8
    near_texts = []
    
    for e in iter_all(msp):
        etype = e.dxftype()
        if etype in ('TEXT', 'MTEXT'):
            pos = getattr(e.dxf, 'insert', None)
            if pos:
                dx = abs(pos.x - cx)
                dy = abs(pos.y - cy)
                if dx < 6000 and dy < 12000:
                    txt = (e.dxf.text if etype == 'TEXT' else e.text).strip()
                    near_texts.append((txt, pos.x, pos.y, e.dxf.layer))

    print(f"부근 TEXT 엔티티 개수: {len(near_texts)}")
    
    # Y좌표 내림차순(위에서 아래)으로 출력
    for i, (txt, x, y, layer) in enumerate(sorted(near_texts, key=lambda p: -p[2]), 1):
        print(f"  {i:3d}: {txt:30s} | 좌표: ({x:8.1f}, {y:8.1f}) | 레이어: {layer}")

if __name__ == "__main__":
    main()
