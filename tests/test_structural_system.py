"""
test_structural_system.py — 골조 시스템 단위 검증
====================================================
structural_filter, structural_extractor, pipeline 검증.
실제 도면 없이 실행 가능 (Mock DXF 모의 객체 사용).

실행: python tests/test_structural_system.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_passed = _failed = 0


def check(name: str, cond: bool, msg: str = ''):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f'  [PASS] {name}')
    else:
        _failed += 1
        print(f'  [FAIL] {name}' + (f' — {msg}' if msg else ''))


# ─────────────────────────────────────────────────────────────
# 1. structural_filter
# ─────────────────────────────────────────────────────────────

def test_structural_filter():
    print('\n[structural_filter] 레이어 필터 검증')
    from core.dxf_parser.structural_filter import is_structural, is_structural_block

    # 골조 레이어
    check('S-GIRDER', is_structural('S-GIRDER'))
    check('00_COLUMN', is_structural('00_COLUMN'))
    check('00_SHEAR WALL', is_structural('00_SHEAR WALL'))
    check('A-WALL-RC', is_structural('A-WALL-RC'))
    check('S-PC-SLAB', is_structural('S-PC-SLAB'))

    # 비골조 레이어
    check('A-WALL-BRICK 제외', not is_structural('A-WALL-BRICK'))
    check('A-FUR-1 제외', not is_structural('A-FUR-1'))
    check('A-DOOR-ELE 제외', not is_structural('A-DOOR-ELE'))
    check('Defpoints 제외', not is_structural('Defpoints'))
    check('0-Pile 제외', not is_structural('0-Pile'))

    # 골조 블록명
    check('C400X800 블록', is_structural_block('C400X800'))
    check('B2-B1 C2 블록', is_structural_block('B2-B1 C2'))
    check('B2-B1 PC2(S)(T) 블록', is_structural_block('B2-B1 PC2(S)(T)'))
    check('B2-B1 EC1 블록', is_structural_block('B2-B1 EC1'))
    check('FSD-600 비골조', not is_structural_block('FSD-600'))
    check('A-FUR 비골조', not is_structural_block('A-FUR'))


# ─────────────────────────────────────────────────────────────
# 2. structural_extractor — _parse_section 등 직접 테스트
# ─────────────────────────────────────────────────────────────

def test_structural_extractor():
    print('\n[structural_extractor] 추출기 로직 검증')
    from core.dxf_parser.structural_extractor import StructuralExtractor, StructuralData

    # StructuralData 생성
    data = StructuralData()
    check('초기 상태 빈 목록', len(data.columns) == 0)
    check('stats 딕셔너리', isinstance(data.stats(), dict))
    check('summary 문자열', isinstance(data.summary(), str))

    # StructuralExtractor 생성
    ext = StructuralExtractor(min_col_size=100, max_col_size=3000)
    check('min_col 설정', ext.min_col == 100)
    check('max_col 설정', ext.max_col == 3000)

    # 빔 레이어 패턴
    from core.dxf_parser.structural_extractor import _BEAM_LAYER, _SHEAR_LAYER, _COL_LAYER
    check('S-GIRDER 보 레이어', bool(_BEAM_LAYER.search('S-GIRDER')))
    check('00_SHEAR 전단벽 레이어', bool(_SHEAR_LAYER.search('00_SHEAR WALL')))
    check('A-WALL-RC 전단벽 레이어', bool(_SHEAR_LAYER.search('A-WALL-RC')))
    check('00_COLUMN 기둥 레이어', bool(_COL_LAYER.search('00_COLUMN')))

    # 보 레이어가 전단벽 레이어에 매칭 안 됨
    check('S-GIRDER != 전단벽', not bool(_SHEAR_LAYER.search('S-GIRDER')))


# ─────────────────────────────────────────────────────────────
# 3. BeamLine 속성
# ─────────────────────────────────────────────────────────────

def test_beam_line():
    print('\n[BeamLine] 보 속성 검증')
    from core.dxf_parser.structural_extractor import BeamLine

    bm = BeamLine(x0=0, y0=0, x1=5000, y1=0, layer='S-GIRDER')
    check('length 5000mm', abs(bm.length - 5000) < 0.1)
    check('기본 폭 400mm', bm.width == 400.0)
    check('기본 높이 900mm', bm.height == 900.0)

    bm_diag = BeamLine(x0=0, y0=0, x1=3000, y1=4000)
    check('대각선 length 5000mm', abs(bm_diag.length - 5000) < 0.1)


# ─────────────────────────────────────────────────────────────
# 4. FrameData
# ─────────────────────────────────────────────────────────────

def test_frame_data():
    print('\n[FrameData] 파이프라인 출력 검증')
    from core.dxf_parser.pipeline import FrameData
    from core.dxf_parser.structural_extractor import ColumnPrim, BeamLine

    frame = FrameData(
        source_dxf='test.dxf',
        columns=[ColumnPrim(cx=100, cy=200, w=400, h=800, source='HATCH')],
        beams=[BeamLine(x0=0, y0=0, x1=5000, y1=0)],
    )
    check('columns 1개', len(frame.columns) == 1)
    check('beams 1개', len(frame.beams) == 1)
    check('summary 반환', 'FrameData' in frame.summary())

    # JSON 직렬화
    import json
    js = frame.to_json()
    d = json.loads(js)
    check('JSON columns 1개', len(d['columns']) == 1)
    check('JSON beams 1개', len(d['beams']) == 1)
    check('JSON col cx=100', d['columns'][0]['cx'] == 100)
    check('JSON col w=400', d['columns'][0]['w'] == 400)
    check('JSON beam length=5000', d['beams'][0]['length'] == 5000)


# ─────────────────────────────────────────────────────────────
# 5. StructuralGrid
# ─────────────────────────────────────────────────────────────

def test_structural_grid():
    print('\n[StructuralGrid] 격자 속성 검증')
    from core.dxf_parser.grid_extractor import StructuralGrid, GridLine

    grid = StructuralGrid()
    grid.x_lines = [
        GridLine('X1', 'X', 100000.0, (100000, 200000)),
        GridLine('X2', 'X', 108500.0, (108500, 200000)),
        GridLine('X3', 'X', 115000.0, (115000, 200000)),
    ]
    grid.y_lines = [
        GridLine('Y1', 'Y', 300000.0, (50000, 300000)),
        GridLine('Y2', 'Y', 313000.0, (50000, 313000)),
    ]

    check('x_coords 3개', len(grid.x_coords) == 3)
    check('y_coords 2개', len(grid.y_coords) == 2)
    check('intersections 6개', len(grid.intersections) == 6)
    check('spans_x 2개', len(grid.spans_x) == 2)
    check('spans_x[0] = 8500mm', abs(grid.spans_x[0] - 8500) < 1)
    check('spans_y[0] = 13000mm', abs(grid.spans_y[0] - 13000) < 1)
    check('summary 반환', '격자' in grid.summary())


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 60)
    print('골조 시스템 단위 검증')
    print('=' * 60)

    test_structural_filter()
    test_structural_extractor()
    test_beam_line()
    test_frame_data()
    test_structural_grid()

    print(f'\n{"="*60}')
    print(f'결과: {_passed} 통과 / {_failed} 실패 / {_passed+_failed} 전체')
    if _failed == 0:
        print('전체 PASS')
    else:
        print(f'주의: {_failed}건 실패')
        sys.exit(1)
