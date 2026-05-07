"""
raw_to_3d_gae.py — 개팀장의 백지상태 3D 빌더 (에이전트 1~11 협력)
========================================================================
모든 과거 자료 무시. 순수 DXF 파싱 -> 좌표 추출 -> 즉시 FreeCAD 솔리드화
"""
import sys, os, time, math
import ezdxf

# FreeCAD Path 설정
FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"
sys.path.insert(0, FREECAD_BIN)

try:
    import FreeCAD
    import Part
except ImportError:
    print("Run this script using FreeCAD's python.exe")
    sys.exit(1)

def is_column_layer(layer):
    l = layer.upper()
    return 'COL' in l and 'NAME' not in l and 'DIM' not in l and 'TEXT' not in l

def is_wall_layer(layer):
    l = layer.upper()
    return 'WAL' in l and 'NAME' not in l and 'DIM' not in l and 'TEXT' not in l

def make_box(x, y, w, d, h):
    box = Part.makeBox(w, d, h)
    box.translate(FreeCAD.Vector(x - w/2, y - d/2, 0))
    return box

def make_wall(p1, p2, thickness, height):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 10: return None
    
    # 2D 방향 벡터
    ux = dx / length
    uy = dy / length
    # 직교 벡터
    nx = -uy * (thickness / 2)
    ny = ux * (thickness / 2)
    
    pts = [
        FreeCAD.Vector(p1[0] + nx, p1[1] + ny, 0),
        FreeCAD.Vector(p2[0] + nx, p2[1] + ny, 0),
        FreeCAD.Vector(p2[0] - nx, p2[1] - ny, 0),
        FreeCAD.Vector(p1[0] - nx, p1[1] - ny, 0),
        FreeCAD.Vector(p1[0] + nx, p1[1] + ny, 0)
    ]
    try:
        wire = Part.makePolygon(pts)
        face = Part.Face(wire)
        solid = face.extrude(FreeCAD.Vector(0, 0, height))
        return solid
    except Exception as e:
        return None

def process_dxf_to_solids(dxf_path, offset_x=0, offset_y=0):
    print(f'[Agent] 파싱 시작: {os.path.basename(dxf_path)}')
    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
    except:
        doc = ezdxf.readfile(dxf_path, encoding='utf-8')
        
    msp = doc.modelspace()
    solids = []
    
    col_count = 0
    wall_count = 0
    
    # 기둥 파싱 (폐합 폴리라인)
    for e in msp.query('LWPOLYLINE'):
        layer = e.dxf.layer
        if is_column_layer(layer) and e.is_closed:
            pts = [(p[0], p[1]) for p in e.get_points()]
            if len(pts) >= 4:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                w = max(xs) - min(xs)
                d = max(ys) - min(ys)
                # 너무 큰 폴리라인은 기둥이 아님
                if w < 5000 and d < 5000:
                    cx = min(xs) + w/2 + offset_x
                    cy = min(ys) + d/2 + offset_y
                    box = make_box(cx, cy, w, d, 4000) # 기본 층고 4m
                    solids.append(box)
                    col_count += 1

    # 벽체 파싱 (선)
    for e in msp.query('LINE'):
        layer = e.dxf.layer
        if is_wall_layer(layer):
            p1 = (e.dxf.start.x + offset_x, e.dxf.start.y + offset_y)
            p2 = (e.dxf.end.x + offset_x, e.dxf.end.y + offset_y)
            wall = make_wall(p1, p2, 200, 4000) # 기본 두께 200, 층고 4m
            if wall:
                solids.append(wall)
                wall_count += 1
                
    print(f'  -> 추출 완료: 기둥 {col_count}개, 벽체 {wall_count}개')
    return solids

def main():
    t0 = time.time()
    
    pkg_dxf = r"E:\Git\dxf_out\02_구조\260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    dong_dxf = r"E:\Git\dxf_out\02_구조\S30-001~010-101동 구조평면도.dxf"
    
    # 새 문서
    doc = FreeCAD.newDocument("GAE_RAW_BUILD")
    
    # 주차장 파싱 (원점 기준)
    pkg_solids = process_dxf_to_solids(pkg_dxf, 0, 0)
    
    # 아파트 동 파싱 (주차장과 너무 멀리 떨어져 있으면 겹치지 않게 오프셋 강제 부여 - 임시)
    # 실제로는 좌표 매핑이 필요하지만, 여기선 DXF 원시 좌표를 씁니다.
    dong_solids = process_dxf_to_solids(dong_dxf, 0, 0)
    
    all_solids = pkg_solids + dong_solids
    print(f'\n[Agent] 총 {len(all_solids)}개의 3D 솔리드 결합 중...')
    
    # 너무 많으면 Part.show가 느리므로 compound로 묶기
    compound = Part.makeCompound(all_solids)
    Part.show(compound)
    
    out_step = os.path.join("output", "gae_raw_track1.step")
    compound.exportStep(out_step)
    
    print(f'[완료] 저장됨: {out_step} (총 소요시간: {time.time()-t0:.1f}초)')

if __name__ == '__main__':
    main()
