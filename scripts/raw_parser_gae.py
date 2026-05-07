"""
raw_parser_gae.py — 개팀장 전용 원초적 파서 (제로베이스)
=============================================================
과거 쓰레기 데이터는 버린다. 
도면에서 순수하게 선, 텍스트, 폴리곤만 뜯어내서 진짜 좌표를 찾아낸다.
"""
import sys
import os
import ezdxf
import time

def analyze_dxf(dxf_path):
    print(f'[개팀장 파서] 도면 분석 시작: {os.path.basename(dxf_path)}')
    t0 = time.time()
    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
    except Exception as e:
        print(f"Failed to read with cp949: {e}, trying utf-8")
        doc = ezdxf.readfile(dxf_path, encoding='utf-8')
    
    msp = doc.modelspace()
    
    # 1. 레이어별 엔티티 수집
    layer_stats = {}
    total_entities = 0
    
    # 간단한 형태의 BBox 계산용
    xs, ys = [], []
    
    for e in msp:
        total_entities += 1
        layer = e.dxf.layer
        etype = e.dxftype()
        
        if layer not in layer_stats:
            layer_stats[layer] = {'count': 0, 'types': set()}
        
        layer_stats[layer]['count'] += 1
        layer_stats[layer]['types'].add(etype)
        
        if etype in ('LINE', 'LWPOLYLINE', 'TEXT', 'MTEXT', 'INSERT'):
            if hasattr(e.dxf, 'insert'):
                xs.append(e.dxf.insert.x)
                ys.append(e.dxf.insert.y)
            elif etype == 'LINE':
                xs.append(e.dxf.start.x)
                ys.append(e.dxf.start.y)
            elif etype == 'LWPOLYLINE':
                for point in e.get_points():
                    xs.append(point[0])
                    ys.append(point[1])
                    
    print(f'  -> 총 엔티티 수: {total_entities}')
    if xs and ys:
        print(f'  -> 도면 바운딩 박스: X({min(xs):.0f} ~ {max(xs):.0f}), Y({min(ys):.0f} ~ {max(ys):.0f})')
        print(f'  -> 크기: {max(xs)-min(xs):.0f} x {max(ys)-min(ys):.0f} mm')
        
    print('\n[주요 구조 레이어 TOP 20]')
    structural_keywords = ['COL', 'WAL', 'BEM', 'SLB', '기둥', '벽', '보', '슬라브']
    
    # 구조 레이어 필터링
    str_layers = {}
    for l, stats in layer_stats.items():
        is_struct = any(k in l.upper() for k in structural_keywords)
        if is_struct or stats['count'] > 1000:
            str_layers[l] = stats
            
    sorted_layers = sorted(str_layers.items(), key=lambda x: x[1]['count'], reverse=True)
    for l, stats in sorted_layers[:20]:
        print(f"  {l:30s} | {stats['count']:6d} 개 | {list(stats['types'])}")
        
    print(f'[완료] 소요시간: {time.time() - t0:.2f}초\n')

if __name__ == '__main__':
    target_dxf = r"E:\Git\dxf_out\02_구조\260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    analyze_dxf(target_dxf)
    
    target_dxf2 = r"E:\Git\dxf_out\02_구조\S30-001~010-101동 구조평면도.dxf"
    analyze_dxf(target_dxf2)
