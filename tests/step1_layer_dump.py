"""
step1_layer_dump.py -- Step 1: 양 DXF 레이어 전수 조사
=======================================================
골조선 분리 전문가 임무의 첫 단계.
모든 레이어명을 덤프하고 구조 관련 여부를 분류한다.
"""
from __future__ import annotations

import sys
import json
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')

import ezdxf

DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DXF_PKG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'


def dump_layers(dxf_path: str, label: str):
    """DXF 레이어 전수 조사 — 엔티티 타입별 카운트 포함."""
    print(f'\n{"="*60}')
    print(f'[{label}] 레이어 덤프')
    print(f'파일: {dxf_path}')
    print('='*60)

    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
    except Exception as e:
        print(f'FAIL: {e}')
        return {}

    msp = doc.modelspace()

    # 레이어별 엔티티 타입 카운트
    layer_stats: dict = defaultdict(lambda: defaultdict(int))

    for e in msp:  # 직접 순회 (INSERT 내부 제외, 레이어명만 볼 것)
        layer = '0'
        try:
            layer = e.dxf.layer or '0'
        except Exception:
            pass
        etype = e.dxftype()
        layer_stats[layer][etype] += 1

    # INSERT 내부 레이어도 수집 (1단계만)
    for e in msp:
        if e.dxftype() == 'INSERT':
            try:
                for sub in e.virtual_entities():
                    layer = '0'
                    try:
                        layer = sub.dxf.layer or '0'
                    except Exception:
                        pass
                    etype = sub.dxftype()
                    layer_stats[layer][etype] += 1
            except Exception:
                pass

    # 총 엔티티 수 기준 정렬
    sorted_layers = sorted(
        layer_stats.items(),
        key=lambda x: -sum(x[1].values())
    )

    print(f'\n레이어 총 {len(sorted_layers)}개\n')
    print(f'{"레이어명":<45} {"총수":>6}  {"주요타입"}')
    print('-'*80)

    result = {}
    for layer_name, type_counts in sorted_layers:
        total = sum(type_counts.values())
        top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:3]
        top_str = ', '.join(f'{t}:{c}' for t, c in top_types)
        print(f'{layer_name:<45} {total:>6}  {top_str}')
        result[layer_name] = dict(type_counts)

    return result


def classify_layers(layer_dict: dict, label: str):
    """레이어를 KEEP/SKIP으로 분류하고 출력."""
    import re

    # 구조 관련 키워드
    KEEP_KEYWORDS = [
        'S-', 'S_',                    # 구조 접두사
        'COLUMN', 'COL',               # 기둥
        'BEAM', 'GIRDER',              # 보, 거더
        'WALL', 'SHEAR',               # 벽, 전단벽
        'SLAB', 'FND', 'BASE',         # 슬라브, 기초
        'PC-', 'PC_',                  # PC 부재
        'STRUCT', 'STR',               # 구조 일반
        '00_',                         # PKG 구조 레이어 패턴
        'A-WALL-RC',                   # RC 구조벽
    ]

    SKIP_KEYWORDS = [
        'HATCH', 'ANNO', 'TEXT', 'DIM', 'DIMENSION',
        'FUR', 'STAIR', 'DOOR', 'WINDOW', 'EQUIP',
        'DEFPOINTS', 'VIEWPORT',
        'TITLE', 'BORDER', 'FRAME',
        'MARK', 'NOTE', 'TAG',
        'GRID', 'AXIS',  # 격자선 (중심선이 아닌 주석용)
    ]

    # 선형 엔티티 타입 (골조선 가능)
    LINE_TYPES = {'LINE', 'LWPOLYLINE', 'ARC', 'CIRCLE', 'POLYLINE', 'SPLINE'}

    keep = []
    skip = []
    uncertain = []

    for layer_name, type_counts in layer_dict.items():
        total = sum(type_counts.values())
        has_lines = any(t in LINE_TYPES for t in type_counts)
        name_upper = layer_name.upper()

        is_keep = any(kw.upper() in name_upper for kw in KEEP_KEYWORDS)
        is_skip = any(kw.upper() in name_upper for kw in SKIP_KEYWORDS)

        # 엔티티 타입이 선형인지도 체크
        if is_keep and not is_skip and has_lines:
            keep.append((layer_name, total, type_counts))
        elif is_skip or not has_lines:
            skip.append((layer_name, total, type_counts))
        else:
            uncertain.append((layer_name, total, type_counts))

    print(f'\n\n[{label}] 레이어 분류 결과')
    print(f'  KEEP (골조선 포함 예상): {len(keep)}개')
    print(f'  SKIP (잡선 예상):        {len(skip)}개')
    print(f'  UNCERTAIN (판단 불가):   {len(uncertain)}개')

    print(f'\n--- KEEP 레이어 ({len(keep)}개) ---')
    for name, total, tc in sorted(keep, key=lambda x: -x[1]):
        top = sorted(tc.items(), key=lambda x: -x[1])[:3]
        top_str = ', '.join(f'{t}:{c}' for t, c in top)
        print(f'  [KEEP] {name:<45} {total:>6}  {top_str}')

    print(f'\n--- UNCERTAIN 레이어 ({len(uncertain)}개) ---')
    for name, total, tc in sorted(uncertain, key=lambda x: -x[1])[:30]:
        top = sorted(tc.items(), key=lambda x: -x[1])[:3]
        top_str = ', '.join(f'{t}:{c}' for t, c in top)
        print(f'  [???] {name:<45} {total:>6}  {top_str}')

    print(f'\n--- SKIP 레이어 (상위 20개) ---')
    for name, total, tc in sorted(skip, key=lambda x: -x[1])[:20]:
        top = sorted(tc.items(), key=lambda x: -x[1])[:3]
        top_str = ', '.join(f'{t}:{c}' for t, c in top)
        print(f'  [SKIP] {name:<45} {total:>6}  {top_str}')

    return {
        'keep': [n for n, _, _ in keep],
        'uncertain': [n for n, _, _ in uncertain],
        'skip': [n for n, _, _ in skip],
    }


if __name__ == '__main__':
    dong_layers = dump_layers(DXF_DONG, '101동 구조평면도')
    pkg_layers  = dump_layers(DXF_PKG,  '지하주차장 구조평면도')

    dong_classified = classify_layers(dong_layers, '101동')
    pkg_classified  = classify_layers(pkg_layers,  '지하주차장')

    # JSON 저장
    import os
    os.makedirs('output', exist_ok=True)
    summary = {
        'dong': {
            'layer_stats': dong_layers,
            'classified': dong_classified,
        },
        'pkg': {
            'layer_stats': pkg_layers,
            'classified': pkg_classified,
        },
    }
    with open('output/skeleton_layer_audit.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print('\n\n-> output/skeleton_layer_audit.json 저장 완료')
