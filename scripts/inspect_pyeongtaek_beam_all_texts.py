import ezdxf
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S35-001~019 보 일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 전체 텍스트 덤프 시작...")
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

    print(f"총 {len(texts)}개의 텍스트 엔티티 검출.")
    
    # 텍스트들을 X좌표 순, Y좌표 내림차순으로 정렬해서 상위 200개 출력
    sorted_texts = sorted(texts, key=lambda p: (p[1], -p[2]))
    
    print("\n[상위 200개 텍스트 리스트]")
    for i, (txt, x, y, layer) in enumerate(sorted_texts[:200], 1):
        print(f"  {i:3d}: {txt:30s} | 좌표: ({x:8.1f}, {y:8.1f}) | 레이어: {layer}")

if __name__ == "__main__":
    main()
