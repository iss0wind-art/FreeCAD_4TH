"""
core/pipeline/track1_processor.py — Track 1: Direct Ingestion Processor
========================================================================
기존 members_accumulated.json 데이터를 기반으로 즉시 솔리드화 및 BOQ 산출.
"""
import json
import math
import os
from typing import List, Dict, Any
from core.pipeline.member_data import Member
from core.pipeline.boq_solid_builder import build_member_solid, export_to_step, export_boq

def run_track1(input_path: str, out_prefix: str):
    print(f'[TRACK 1] Loading assets: {input_path}')
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    raw_members = data.get('members', [])
    processed_members: List[Member] = []
    shapes = []
    
    # 층고 데이터 (임시)
    FLOOR_HEIGHTS = {
        'B2F': 4400,
        'B1F': 4400,
        '1F': 4000
    }
    
    # 오프셋 미적용 보정 (F-2 관련)
    # 2,189건에 대한 정확한 필터링 기준이 필요하나, 여기선 특정 조건(예: source='DONG') 예시 적용
    DONG_OFFSET_X = -126000.0
    
    for rm in raw_members:
        m_type = rm['type']
        m_floor = rm['floor']
        z_bot = rm.get('z_bot', 0)
        z_top = rm.get('z_top', 0)
        
        # 1. Member 객체로 변환
        m = Member(
            id=rm['id'],
            member_type=m_type,
            spec=rm.get('spec', rm.get('layer', 'N/A')),
            floor=m_floor,
            x=rm['x'],
            y=rm['y'],
            z=z_bot,
            layer=rm.get('layer'),
            metadata=rm
        )
        
        # 2. XRef 오프셋 보정 (F-2) - 임시 로직
        # "미적용 2,189건"을 정확히 특정할 수 없으므로, 로깅 후 추후 정교화
        if rm.get('source') == 'DONG' and 'offset_applied' not in rm:
            # m.x += DONG_OFFSET_X
            pass
            
        # 3. 부재별 속성 보강
        if m_type == 'WALL':
            # 벽체 두께 보강 (기본 200mm)
            m.width = rm.get('thickness_mm', rm.get('width_mm', 200))
            m.height = abs(z_top - z_bot) or 4000
            m.length = rm.get('length_mm', 1000)
            m.rotation = rm.get('angle_deg', 0)
            
            # 중심선 및 두께 기반 4개 꼭짓점 생성
            half_l = m.length / 2
            half_w = m.width / 2
            rad = math.radians(m.rotation)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            
            # 로컬 좌표계 (±L/2, ±W/2) -> 회전 -> 이동
            def rotate_translate(lx, ly):
                rx = lx * cos_a - ly * sin_a
                ry = lx * sin_a + ly * cos_a
                return (m.x + rx, m.y + ry)
            
            m.coords = [
                rotate_translate(-half_l, -half_w),
                rotate_translate(half_l, -half_w),
                rotate_translate(half_l, half_w),
                rotate_translate(-half_l, half_w)
            ]
            
        elif m_type == 'BEAM':
            m.width = rm.get('width_mm', 400)
            m.height = abs(z_top - z_bot) or 800
            m.length = rm.get('length_mm', 1000)
            m.rotation = rm.get('angle_deg', 0)
            
            length = m.length
            rad = math.radians(m.rotation)
            dx = (length / 2) * math.cos(rad)
            dy = (length / 2) * math.sin(rad)
            m.coords = [
                (m.x - dx, m.y - dy),
                (m.x + dx, m.y + dy)
            ]
            
        elif m_type == 'COLUMN':
            m.width = rm.get('width_mm', 600)
            m.depth = rm.get('depth_mm', 600)
            m.height = abs(z_top - z_bot) or 4000
            m.rotation = rm.get('angle_deg', 0)
            
        elif m_type == 'SLAB':
            # 1-B: PKG SLAB 격자 패널 생성 로직 (추후 고도화)
            m.height = 200 # 기본 두께
            if 'vertices' in rm:
                m.coords = rm['vertices']
            else:
                # 사각형 가정
                w = rm.get('width_mm', 1000)
                l = rm.get('length_mm', 1000)
                m.coords = [
                    (m.x - w/2, m.y - l/2),
                    (m.x + w/2, m.y - l/2),
                    (m.x + w/2, m.y + l/2),
                    (m.x - w/2, m.y + l/2)
                ]

        # 4. 솔리드 생성
        try:
            solid = build_member_solid(m)
            if solid:
                shapes.append((m.id, solid))
                # BOQ 수치 업데이트
                m.volume = solid.Volume / 1e9 # mm3 -> m3
                m.area = m.volume / (m.height / 1000) if m.height else 0
                processed_members.append(m)
            else:
                print(f'  [SKIP] Failed to build solid for {m.id} (Returned None)')
        except Exception as e:
            print(f'  [ERROR] Failed to build solid for {m.id}: {e}')

    # 5. 결과 내보내기
    export_to_step(shapes, out_prefix + '.step')
    export_boq(processed_members, out_prefix + '_boq')
    
    print(f'[TRACK 1] Completed. Members: {len(processed_members)}, Solids: {len(shapes)}')

if __name__ == '__main__':
    # FreeCAD 외부 실행 시에는 별도 래퍼 필요
    import sys
    run_track1('output/members_accumulated.json', 'output/final_track1')
