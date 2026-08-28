import os, sys, ezdxf
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"

SHEETS = {
    'B1': {'sw': (877250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0},
}

def main():
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    
    sheet = SHEETS['B1']
    sw = sheet['sw']; w = sheet['w']; h = sheet['h']
    ix0, iy0 = sw[0] + w * 0.02, sw[1] + h * 0.02
    ix1, iy1 = sw[0] + w * 0.98, sw[1] + h * 0.98
    
    # B1 영역 내 00_COLUMN 레이어의 LINE 수집
    lines = []
    for e in msp:
        try:
            if e.dxf.layer != '00_COLUMN':
                continue
        except:
            continue
            
        if e.dxftype() == 'LINE':
            p1 = e.dxf.start
            p2 = e.dxf.end
            if ix0 <= p1.x <= ix1 and iy0 <= p1.y <= iy1:
                lines.append((p1.x, p1.y, p2.x, p2.y))
                
    print(f"Collected {len(lines)} LINEs in B1 '00_COLUMN'")
    
    # 1. 그래프 빌드 (끝점 매칭용 5mm 오차 허용)
    def snap(val):
        return round(val / 5.0) * 5.0  # 5mm 그리드 스냅
        
    adj = defaultdict(set)
    edges = set()
    
    for x1, y1, x2, y2 in lines:
        u = (snap(x1), snap(y1))
        v = (snap(x2), snap(y2))
        if u == v:
            continue
        # 정렬된 튜플로 에지 유일화
        edge = tuple(sorted([u, v]))
        if edge not in edges:
            edges.add(edge)
            adj[u].add(v)
            adj[v].add(u)
            
    # 2. 연결 컴포넌트(Connected Components) 찾기
    visited = set()
    components = []
    
    for node in adj.keys():
        if node in visited:
            continue
        comp = []
        queue = [node]
        visited.add(node)
        while queue:
            curr = queue.pop(0)
            comp.append(curr)
            for nxt in adj[curr]:
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        components.append(comp)
        
    print(f"Found {len(components)} connected components")
    
    # 3. 4개의 노드로 이루어지고, 모든 노드의 degree가 2인 컴포넌트(사각형 루프) 필터링
    rects = []
    for comp in components:
        if len(comp) == 4:
            # 모든 노드가 degree 2인지 검사
            deg_ok = True
            for node in comp:
                # 이 컴포넌트 내에서의 degree
                comp_deg = len(adj[node].intersection(comp))
                if comp_deg != 2:
                    deg_ok = False
                    break
            if deg_ok:
                xs = [p[0] for p in comp]
                ys = [p[1] for p in comp]
                xmin, xmax = min(xs), max(xs)
                ymin, ymax = min(ys), max(ys)
                bw = xmax - xmin
                bh = ymax - ymin
                if 400 <= bw <= 3000 and 400 <= bh <= 3000:
                    rects.append({'cx': (xmin+xmax)/2, 'cy': (ymin+ymax)/2, 'w': bw, 'h': bh})
                    
    print(f"Reconstructed {len(rects)} rectangular columns from LINEs!")
    if rects:
        print("Sample reconstructed rect:", rects[0])

if __name__ == '__main__':
    main()
