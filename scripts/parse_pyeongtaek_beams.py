import ezdxf
import os
import sys
import re
import json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S35-001~019 보 일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 보 일람표 정밀 파싱 시작...")
    if not os.path.exists(dxf_path):
        return

    doc = ezdxf.readfile(dxf_path, encoding='utf-8', errors='replace')
    msp = doc.modelspace()

    # 모든 텍스트 수집
    texts = []
    for e in iter_all(msp):
        if e.dxftype() in ('TEXT', 'MTEXT'):
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if txt:
                pos = getattr(e.dxf, 'insert', None)
                if pos:
                    texts.append({
                        'text': txt,
                        'x': pos.x,
                        'y': pos.y,
                        'layer': e.dxf.layer
                    })

    # 1. 보 마크 찾기 (1G4, 1G4D, RaB1, B0 등)
    exclude_keywords = ['철근', '늑근', '강도', 'fck', '띠', '별', '부호', '비고', '형식', '상부', '하부', '중앙', '단부', '연속', 'END', 'ALL', 'CENTER', 'BOTH', '※', '이상', '의무', '적용', '표기']
    # 보 기호 패턴 (예: 1G4, 1G4D, RaB1, B0 등 매칭)
    beam_pattern = re.compile(r'\b(\d*[R|a|E|P|C|G|B|W]+[GB]G?\d+[A-Z0-9]*)\b', re.IGNORECASE)
    
    beams = []
    for t in texts:
        txt = t['text']
        if beam_pattern.search(txt) and not any(k in txt for k in exclude_keywords):
            # 순수 보 기호만 추출
            m = beam_pattern.search(txt)
            if m:
                clean_name = m.group(1).upper()
                t['text'] = clean_name
                beams.append(t)

    print(f"검출된 보 마크 개수: {len(beams)}")
    
    beam_groups = {}
    for b in beams:
        name = b['text'].upper()
        if name not in beam_groups:
            beam_groups[name] = []
        beam_groups[name].append(b)

    beam_specs = {}

    for name, list_b in sorted(beam_groups.items(), key=lambda x: x[0]):
        print(f"\n--- 보 {name} ---")
        beam_specs[name] = []
        
        for idx, b in enumerate(list_b):
            bx, by = b['x'], b['y']
            
            # 이 보 주변(가로 ±4000, 세로 ±8000)의 모든 텍스트 수집
            near = []
            for t in texts:
                dx = t['x'] - bx
                dy = t['y'] - by
                if abs(dx) < 4000 and abs(dy) < 8000:
                    near.append(t)
            
            # Y좌표 별로 그룹화하여 행(Row) 분석
            rows_by_y = {}
            for t in near:
                y_key = None
                for y_val in rows_by_y.keys():
                    if abs(t['y'] - y_val) < 100:
                        y_key = y_val
                        break
                if y_key is None:
                    y_key = t['y']
                    rows_by_y[y_key] = []
                rows_by_y[y_key].append(t)
            
            # '크기' 키워드가 들어간 행(들)과 해당 X좌표 부근의 치수들 수집
            size_rows = []
            for y_val, r_texts in rows_by_y.items():
                r_txts = [t['text'] for t in r_texts]
                if any('크' in txt and '기' in txt for txt in r_txts) or any('보크기' in txt for txt in r_txts) or any('형태' in txt or '형  태' in txt for txt in r_txts):
                    size_rows.append(r_texts)
            
            for size_row in size_rows:
                # bx 부근(가로 ±1500)의 크기 텍스트 수집
                f_sizes = []
                for s_node in size_row:
                    if abs(s_node['x'] - bx) < 1500:
                        f_sizes.append(s_node)
                
                if len(f_sizes) >= 2:
                    # 숫자만 추출
                    nums = []
                    for s in sorted(f_sizes, key=lambda s: s['x']):
                        num_val = re.sub(r'[^0-9]', '', s['text'])
                        if num_val:
                            nums.append(num_val)
                    
                    if len(nums) >= 2:
                        width = int(nums[0])
                        height = int(nums[1])
                        if width >= 200 and height >= 200:
                            spec = {
                                'width': width,
                                'height': height,
                                'section': f"{width}x{height}"
                            }
                            if spec not in beam_specs[name]:
                                beam_specs[name].append(spec)
                                print(f"  [매칭] 규격 => {width}x{height}")

    # 결과 저장
    out_path = os.path.join("output", "pyeongtaek_beam_specs.json")
    os.makedirs("output", exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(beam_specs, f, ensure_ascii=False, indent=2)
        
    print(f"\n[성공] 평택 고덕 보 규격 {len(beam_specs)}종 최종 파싱 완료 -> {out_path}")

if __name__ == "__main__":
    main()
