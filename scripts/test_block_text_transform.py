import ezdxf
import os
import sys
import math
import re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.safe_reader import safe_readfile

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S35-001~019 보 일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 블록 속성 수동 변환 테스트 개시...")
    if not os.path.exists(dxf_path):
        return

    doc = safe_readfile(dxf_path)
    msp = doc.modelspace()

    # 1. 모든 블록 정의 내부의 TEXT/MTEXT 수집
    block_texts = {}
    for block in doc.blocks:
        bname = block.name
        block_texts[bname] = []
        for e in block.query('TEXT MTEXT'):
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if txt:
                pos = getattr(e.dxf, 'insert', None)
                if pos:
                    block_texts[bname].append((txt, pos.x, pos.y, e.dxf.layer))

    # 2. 모델스페이스의 INSERT를 순회하며 가상 텍스트 생성
    resolved_texts = []
    
    # 모델스페이스 자체의 직접 TEXT/MTEXT도 일단 수집
    for e in msp.query('TEXT MTEXT'):
        txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
        if txt:
            pos = getattr(e.dxf, 'insert', None)
            if pos:
                resolved_texts.append((txt, pos.x, pos.y, e.dxf.layer))

    # INSERT 전개
    insert_count = 0
    resolved_from_inserts = 0
    
    for e in msp.query('INSERT'):
        insert_count += 1
        bname = e.dxf.name
        
        # INSERT 자체 속성(ATTRIB)도 수집
        for attrib in e.attribs:
            txt = attrib.dxf.text.strip()
            if txt:
                pos = attrib.dxf.insert
                resolved_texts.append((txt, pos.x, pos.y, attrib.dxf.layer))
                resolved_from_inserts += 1

        # 블록 정의 내 텍스트들을 2D 변환 행렬 적용하여 복원
        if bname in block_texts and block_texts[bname]:
            ix, iy = e.dxf.insert.x, e.dxf.insert.y
            sx = e.dxf.scale.x if hasattr(e.dxf, 'scale') else 1.0
            sy = e.dxf.scale.y if hasattr(e.dxf, 'scale') else 1.0
            rot = e.dxf.rotation if hasattr(e.dxf, 'rotation') else 0.0
            rad = math.radians(rot)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)
            
            for txt, lx, ly, layer in block_texts[bname]:
                # 2D 변환 행렬 적용
                gx = ix + (lx * sx * cos_r - ly * sy * sin_r)
                gy = iy + (lx * sx * sin_r + ly * sy * cos_r)
                
                # 포맷팅 제어 문자 제거 (\A1; 등)
                clean_txt = re.sub(r'\\A\d+;', '', txt).strip()
                clean_txt = re.sub(r'\\[a-zA-Z]\d+;', '', clean_txt).strip()
                
                resolved_texts.append((clean_txt, gx, gy, layer))
                resolved_from_inserts += 1

    print(f"모델스페이스 내 INSERT 개수: {insert_count}")
    print(f"INSERT 전개로 복원된 텍스트 개수: {resolved_from_inserts}")
    print(f"최종 병합된 텍스트 총 개수: {len(resolved_texts)}")
    
    # 1G4 (X=24799.6, Y=10903.8) 주변 복원된 텍스트 확인
    cx, cy = 24799.6, 10903.8
    near = []
    for txt, x, y, layer in resolved_texts:
        dx = abs(x - cx)
        dy = abs(y - cy)
        if dx < 4000 and dy < 8000:
            near.append((txt, dx, dy, x, y, layer))
            
    print(f"\n[복원된 1G4 주변 텍스트 분포 (상위 50개)]")
    for txt, dx, dy, rx, ry, layer in sorted(near, key=lambda p: (-p[4], p[3]))[:50]:
        print(f"  텍스트: {txt:25s} | 상대 dy: {dy:6.0f} (dx: {dx:5.0f}) | 절대좌표: ({rx:8.0f}, {ry:8.0f}) | 레이어: {layer}")

if __name__ == "__main__":
    main()
