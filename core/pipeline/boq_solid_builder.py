"""
core/pipeline/boq_solid_builder.py — Unified Solid Builder and Exporter
=======================================================================
FreeCAD API를 사용하여 부재(Member) 객체를 3D 솔리드로 변환하고,
STEP 파일 및 BOQ(JSON, CSV) 산출물을 생성하는 통합 모듈.
"""
import os
import json
import csv
import math
from typing import List, Tuple, Dict, Any, Optional
from core.pipeline.member_data import Member

# FreeCAD 환경 확인 (외부 실행 시 ImportError 방지)
try:
    import FreeCAD
    import Part
except ImportError:
    FreeCAD = None
    Part = None

def make_box_solid(width: float, depth: float, height: float, x: float, y: float, z: float, rotation: float = 0.0):
    """직육면체 솔리드 생성 (기둥 등)."""
    if not Part: return None
    
    # 로컬 좌표계 기준 생성
    box = Part.makeBox(width, depth, height)
    
    # 회전 적용 (중심 기준 회전 필요 시 오프셋 조절)
    if rotation != 0:
        box.rotate(FreeCAD.Vector(width/2, depth/2, 0), FreeCAD.Vector(0, 0, 1), rotation)
    
    # 배치
    box.translate(FreeCAD.Vector(x - width/2, y - depth/2, z))
    return box

def make_beam_solid(p1: Tuple[float, float], p2: Tuple[float, float], thickness: float, height: float, z_base: float):
    """중심선 기반 보(Beam) 솔리드 생성."""
    if not Part: return None
    
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 1.0: return None
    
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux  # 법선 벡터
    half_t = thickness / 2
    
    corners = [
        FreeCAD.Vector(p1[0] + nx * half_t, p1[1] + ny * half_t, z_base),
        FreeCAD.Vector(p1[0] - nx * half_t, p1[1] - ny * half_t, z_base),
        FreeCAD.Vector(p2[0] - nx * half_t, p2[1] - ny * half_t, z_base),
        FreeCAD.Vector(p2[0] + nx * half_t, p2[1] + ny * half_t, z_base),
    ]
    
    edges = [Part.makeLine(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    wire = Part.Wire(edges)
    face = Part.Face(wire)
    solid = face.extrude(FreeCAD.Vector(0, 0, height))
    return solid

def make_prism_solid(vertices: List[Tuple[float, float]], height: float, z_base: float):
    """다각형 평면 기반 프리즘 솔리드 생성 (벽체, 슬래브 등)."""
    if not Part or not vertices or len(vertices) < 3: return None
    
    pts = [FreeCAD.Vector(v[0], v[1], z_base) for v in vertices]
    edges = [Part.makeLine(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    wire = Part.Wire(edges)
    
    # 닫히지 않은 경우 자동 폐합
    if not wire.isClosed():
        edges.append(Part.makeLine(pts[-1], pts[0]))
        wire = Part.Wire(edges)
        
    try:
        face = Part.Face(wire)
        solid = face.extrude(FreeCAD.Vector(0, 0, height))
        return solid
    except Exception:
        return None

def build_member_solid(m: Member) -> Optional[Any]:
    """Member 객체 정보를 바탕으로 적절한 솔리드 생성."""
    if m.member_type == 'COLUMN':
        # 기둥은 width, depth(height 인자 오용 가능성 주의) 사용
        w = m.width or 600
        d = m.depth or m.height or 600 # depth 정보가 없을 시 height를 깊이로 사용
        h = 4000 # 기본 층고 (추후 Member 정보에서 가져와야 함)
        return make_box_solid(w, d, h, m.x, m.y, m.z, m.rotation)
    
    elif m.member_type == 'BEAM':
        if len(m.coords) >= 2:
            p1, p2 = m.coords[0], m.coords[1]
            t = m.width or 400
            h = m.height or 800
            return make_beam_solid(p1, p2, t, h, m.z)
    
    elif m.member_type in ('WALL', 'SLAB'):
        if m.coords:
            h = m.height or 200
            return make_prism_solid(m.coords, h, m.z)
            
    return None

def export_to_step(shapes: List[Tuple[str, Any]], out_path: str):
    """솔리드 목록을 STEP 파일로 내보냄."""
    if not Part or not shapes: return
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    compound = Part.makeCompound([s for name, s in shapes])
    compound.exportStep(out_path)
    print(f'[BUILDER] STEP Exported: {out_path}')

def export_boq(members: List[Member], out_base_path: str):
    """BOQ 데이터를 JSON 및 CSV로 내보냄."""
    os.makedirs(os.path.dirname(out_base_path), exist_ok=True)
    
    # JSON Export
    json_path = out_base_path + '.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump([m.to_dict() for m in members], f, ensure_ascii=False, indent=2)
    
    # CSV Export
    csv_path = out_base_path + '.csv'
    if members:
        keys = members[0].to_dict().keys()
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for m in members:
                writer.writerow(m.to_dict())
                
    print(f'[BUILDER] BOQ Exported: {json_path}, {csv_path}')
