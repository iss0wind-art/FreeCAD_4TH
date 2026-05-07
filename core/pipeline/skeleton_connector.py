"""
core/pipeline/skeleton_connector.py — Track 2: Skeleton Line Connector
======================================================================
끊어진 골조선을 연결하여 부재 추출 정밀도를 높임 (Step 4).
방향차 < 5도, 간격 < 800mm 기준.
"""
import math
import ezdxf
from typing import List, Tuple

class SkeletonLine:
    def __init__(self, p1: Tuple[float, float], p2: Tuple[float, float], layer: str):
        self.p1 = p1
        self.p2 = p2
        self.layer = layer
        self.dx = p2[0] - p1[0]
        self.dy = p2[1] - p1[1]
        self.length = math.hypot(self.dx, self.dy)
        self.angle = math.atan2(self.dy, self.dx) % math.pi # 0 to pi

def connect_lines(lines: List[SkeletonLine], gap_tol: float = 800.0, angle_tol_deg: float = 5.0) -> List[SkeletonLine]:
    angle_tol = math.radians(angle_tol_deg)
    connected = list(lines)
    new_lines = []
    
    # 공간 분할 인덱스 생성
    grid_size = gap_tol * 2
    grid = {}
    
    def get_grid_cells(p):
        gx, gy = int(p[0] / grid_size), int(p[1] / grid_size)
        return [(gx + dx, gy + dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1]]

    for i, l in enumerate(lines):
        for cell in get_grid_cells(l.p1) + get_grid_cells(l.p2):
            grid.setdefault(cell, []).append(i)

    used_pairs = set()
    
    for i in range(len(lines)):
        l1 = lines[i]
        # l1의 끝점 주변 셀에 있는 라인들만 검사
        nearby_indices = set()
        for cell in get_grid_cells(l1.p1) + get_grid_cells(l1.p2):
            nearby_indices.update(grid.get(cell, []))
            
        for j in nearby_indices:
            if i >= j: continue
            if (i, j) in used_pairs: continue
            l2 = lines[j]
            
            # 1. 각도 차이 확인
            ang_diff = abs(l1.angle - l2.angle)
            if ang_diff > math.pi / 2: ang_diff = math.pi - ang_diff
            
            if ang_diff < angle_tol:
                # 2. 끝점 간 거리 확인
                dists = [
                    (math.hypot(l1.p2[0]-l2.p1[0], l1.p2[1]-l2.p1[1]), l1.p2, l2.p1),
                    (math.hypot(l1.p2[0]-l2.p2[0], l1.p2[1]-l2.p2[1]), l1.p2, l2.p2),
                    (math.hypot(l1.p1[0]-l2.p1[0], l1.p1[1]-l2.p1[1]), l1.p1, l2.p1),
                    (math.hypot(l1.p1[0]-l2.p2[0], l1.p1[1]-l2.p2[1]), l1.p1, l2.p2),
                ]
                min_dist, p_start, p_end = min(dists, key=lambda x: x[0])
                
                if min_dist < gap_tol and min_dist > 1.0:
                    new_lines.append(SkeletonLine(p_start, p_end, l1.layer))
                    used_pairs.add((i, j))
    
    return connected + new_lines

def process_dxf_skeleton(in_path: str, out_path: str):
    print(f'[SKELETON] Loading: {in_path}')
    doc = ezdxf.readfile(in_path)
    msp = doc.modelspace()
    
    lines = []
    for e in msp.query('LINE'):
        lines.append(SkeletonLine(
            (e.dxf.start.x, e.dxf.start.y),
            (e.dxf.end.x, e.dxf.end.y),
            e.dxf.layer
        ))
    
    print(f'  Loaded {len(lines)} lines.')
    connected_all = connect_lines(lines)
    print(f'  After connection: {len(connected_all)} lines (+{len(connected_all)-len(lines)})')
    
    # 새로운 DXF 저장
    new_doc = ezdxf.new()
    new_msp = new_doc.modelspace()
    for l in connected_all:
        new_msp.add_line(l.p1, l.p2, dxfattribs={'layer': l.layer})
        
    new_doc.saveas(out_path)
    print(f'[SKELETON] Saved: {out_path}')

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        process_dxf_skeleton(sys.argv[1], sys.argv[2])
    else:
        # 테스트용
        process_dxf_skeleton('output/skeleton_pkg_b1f.dxf', 'output/skeleton_pkg_b1f_step4.dxf')
