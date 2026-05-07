"""
agent_horizontal_scanner.py — [Agent 3] 수평부재(보, 슬라브) 위상 추출 봇
========================================================================
DXF에서 보(Beam)와 슬라브(Slab)를 표현하는 선과 폴리곤을 스캔하여
위상 데이터를 추출한다.
"""
import sys, os, time, json
import ezdxf

def extract_horizontal_members(dxf_path):
    print(f"[Agent 3] 수평부재 추출 시작: {os.path.basename(dxf_path)}")
    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
    except:
        doc = ezdxf.readfile(dxf_path, encoding='utf-8')
    msp = doc.modelspace()
    
    beams = []
    slabs = []
    
    for e in msp:
        layer = e.dxf.layer.upper()
        etype = e.dxftype()
        
        # 보(BEAM) 식별
        if 'BEM' in layer or 'BEAM' in layer:
            if etype == 'LINE':
                # 보 중심선 또는 외곽선 (시작점, 끝점)
                beams.append({
                    'type': 'line',
                    'layer': layer,
                    'p1': (e.dxf.start.x, e.dxf.start.y),
                    'p2': (e.dxf.end.x, e.dxf.end.y)
                })
            elif etype == 'LWPOLYLINE':
                pts = [(p[0], p[1]) for p in e.get_points()]
                beams.append({
                    'type': 'polyline',
                    'layer': layer,
                    'pts': pts,
                    'closed': e.is_closed
                })
                
        # 슬라브(SLAB) 식별
        elif 'SLB' in layer or 'SLAB' in layer:
            if etype == 'LWPOLYLINE':
                pts = [(p[0], p[1]) for p in e.get_points()]
                # 면적이 어느 정도 되는 것들만 슬라브 외곽선으로 간주 (최소 1m x 1m 이상)
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                w, d = max(xs) - min(xs), max(ys) - min(ys)
                if w > 1000 and d > 1000:
                    slabs.append({
                        'layer': layer,
                        'pts': pts,
                        'closed': e.is_closed,
                        'bbox': (min(xs), min(ys), max(xs), max(ys))
                    })
    
    print(f" -> 추출된 보(Beam) 조각: {len(beams)}개")
    print(f" -> 추출된 슬라브(Slab) 외곽선: {len(slabs)}개")
    
    # 결과를 JSON으로 저장 (Top-Down Builder가 읽을 수 있도록)
    out_file = os.path.join('output', f'horizontal_topology_{os.path.basename(dxf_path)}.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({'beams': beams, 'slabs': slabs}, f, ensure_ascii=False, indent=2)
        
    print(f"[완료] 저장됨: {out_file}")
    return out_file

if __name__ == '__main__':
    t0 = time.time()
    target_dxf = r"E:\Git\dxf_out\02_구조\260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    extract_horizontal_members(target_dxf)
    
    target_dxf_dong = r"E:\Git\dxf_out\02_구조\S30-001~010-101동 구조평면도.dxf"
    extract_horizontal_members(target_dxf_dong)
    print(f"총 소요시간: {time.time()-t0:.1f}초")
