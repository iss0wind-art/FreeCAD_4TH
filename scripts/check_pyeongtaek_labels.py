import ezdxf
import re
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r"D:/Git/FreeCAD_4TH")

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S21-001~012 구조평면도.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 라벨 추출 테스트 시작...")
    if not os.path.exists(dxf_path):
        print(f"오류: 파일 없음: {dxf_path}")
        return

    doc = ezdxf.readfile(dxf_path, encoding='cp949', errors='replace')
    msp = doc.modelspace()

    labels = []
    for e in iter_all(msp):
        if e.dxftype() in ('TEXT', 'MTEXT'):
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            # 기둥(C), 보(G, B, RG, CG), 슬래브(S), 옹벽(W) 등의 패턴 매칭
            if re.search(r'\b([GBCW][GBCW]?\d+|S\d+)\b', txt) or re.search(r'([GBCW][GBCW]?\d+|S\d+)', txt):
                pos = getattr(e.dxf, 'insert', None)
                if pos:
                    labels.append((txt, round(pos.x), round(pos.y), e.dxf.layer))

    print(f"총 {len(labels)}개의 매칭 라벨을 찾았습니다.")
    print("\n[샘플 라벨 30개]")
    for txt, x, y, layer in labels[:30]:
        print(f"  텍스트: {txt:15s} | 좌표: ({x:8d}, {y:8d}) | 레이어: {layer}")

if __name__ == "__main__":
    main()
