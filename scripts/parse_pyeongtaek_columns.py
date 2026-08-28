import ezdxf
import os
import sys
import re
import json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.dxf_parser.entity_scanner import iter_all

dxf_path = r"D:/06.3지국 전용방/02. 평택 고덕/dxf_out/02_구조/S31-001~009 기둥일람표.dxf"

def main():
    print(f"[{os.path.basename(dxf_path)}] 기둥일람표 정밀 그리드 파싱 시작...")
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

    # 1. 기둥 마크 찾기 (C1, C2 등)
    col_pattern = re.compile(r'^(C\d+)$', re.IGNORECASE)
    cols = [t for t in texts if col_pattern.match(t['text'])]

    print(f"검출된 기둥 마크 개수: {len(cols)}")
    
    col_groups = {}
    for c in cols:
        name = c['text'].upper()
        if name not in col_groups:
            col_groups[name] = []
        col_groups[name].append(c)

    column_specs = {}

    for name, list_c in sorted(col_groups.items(), key=lambda x: x[0]):
        print(f"\n--- 기둥 {name} ---")
        column_specs[name] = []
        
        for idx, c in enumerate(list_c):
            cx, cy = c['x'], c['y']
            
            # 이 기둥 주변(가로 ±6000, 세로 ±6000)의 모든 텍스트 수집
            near = []
            for t in texts:
                dx = t['x'] - cx
                dy = t['y'] - cy
                if abs(dx) < 6000 and abs(dy) < 6000:
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
            
            # '크기' 키워드가 들어간 크기 행(들)과 층을 나타내는 텍스트들 수집
            size_rows = []
            floor_texts = []
            
            for y_val, r_texts in rows_by_y.items():
                r_txts = [t['text'] for t in r_texts]
                # 크기 행 판별
                if any('크' in txt and '기' in txt for txt in r_txts) or any('기둥크기' in txt for txt in r_txts):
                    size_rows.append(r_texts)
                # 층 텍스트 수집 (예: '10층', '지하1~지상1층', '2~3층', '8~9층')
                for t in r_texts:
                    t_val = t['text'].strip()
                    # HD나 @나 fck 등 불필요한 단어가 없는 순수 층이름 패턴
                    if ('층' in t_val or '지하' in t_val or '지상' in t_val) and not any(k in t_val for k in ['강도', '띠철근', '주근', 'fck', '별', '부호', '비고', '형식']):
                        floor_texts.append(t)

            # 매칭 진행
            for f_node in floor_texts:
                fl_name = f_node['text'].strip()
                fx = f_node['x']
                
                # fx 부근(가로 ±2000)의 크기 텍스트 수집
                for size_row in size_rows:
                    f_sizes = []
                    for s_node in size_row:
                        if abs(s_node['x'] - fx) < 2000:
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
                                    'floor': fl_name,
                                    'width': width,
                                    'height': height,
                                    'section': f"{width}x{height}"
                                }
                                # 중복 방지하며 추가
                                if spec not in column_specs[name]:
                                    column_specs[name].append(spec)
                                    print(f"  [매칭] {fl_name:15s} => {width}x{height}")

    # 결과 저장
    out_path = os.path.join("output", "pyeongtaek_column_specs.json")
    os.makedirs("output", exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(column_specs, f, ensure_ascii=False, indent=2)
        
    print(f"\n[성공] 평택 고덕 기둥 규격 {len(column_specs)}종 최종 파싱 완료 -> {out_path}")

if __name__ == "__main__":
    main()
