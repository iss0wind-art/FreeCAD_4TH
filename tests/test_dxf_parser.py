"""
test_dxf_parser.py — dxf_parser 패키지 단위 검증
================================================
실제 도면 없이 실행 가능한 단위 테스트.
모의(Mock) DXF 구조로 핵심 로직 검증.

실행: python tests/test_dxf_parser.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ─────────────────────────────────────────────────────────────
# 테스트 프레임워크 (의존성 없이)
# ─────────────────────────────────────────────────────────────

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
# 1. coord_unifier — DrawingTransform
# ─────────────────────────────────────────────────────────────

def test_drawing_transform():
    print('\n[coord_unifier] DrawingTransform 검증')
    from core.dxf_parser.coord_unifier import DrawingTransform

    tr = DrawingTransform(drawing_id='test', tx=1000.0, ty=2000.0)
    x, y = tr.apply(500.0, 300.0)
    check('apply tx+ty', abs(x - 1500) < 0.1 and abs(y - 2300) < 0.1,
          f'got ({x},{y})')

    pts = [(0, 0), (100, 100), (-100, 50)]
    unified = tr.apply_pts(pts)
    check('apply_pts 3점', len(unified) == 3)
    check('apply_pts [0] 정확', abs(unified[0][0] - 1000) < 0.1)

    # 회전 테스트 (90도)
    import math
    tr90 = DrawingTransform(drawing_id='rot', tx=0, ty=0, rotation_deg=90.0)
    x2, y2 = tr90.apply(1.0, 0.0)
    check('90도 회전 x→y', abs(x2) < 0.01 and abs(y2 - 1.0) < 0.01,
          f'got ({x2:.3f},{y2:.3f})')


# ─────────────────────────────────────────────────────────────
# 2. level_parser — _normalize_floor_label, LevelSet
# ─────────────────────────────────────────────────────────────

def test_level_parser():
    print('\n[level_parser] 표고·단차 파싱 검증')
    from core.dxf_parser.level_parser import _normalize_floor_label, LevelSet

    check('지하 2층→B2F', _normalize_floor_label('지하 2층') == 'B2F')
    check('지하 1층→B1F', _normalize_floor_label('지하 1층') == 'B1F')
    check('B2F 통과', _normalize_floor_label('B2F') == 'B2F')
    check('빈값→빈값', _normalize_floor_label('') == '')

    # LevelSet 층고 계산
    ls = LevelSet(floor_sl={'B2F': -9050.0, 'B1F': -5600.0, '1F': 370.0})
    h1 = ls.floor_height('B2F', 'B1F')
    check('층고 B2F→B1F = 3450', h1 is not None and abs(h1 - 3450) < 1,
          f'got {h1}')
    h2 = ls.floor_height('B1F', '1F')
    check('층고 B1F→1F = 5970', h2 is not None and abs(h2 - 5970) < 1,
          f'got {h2}')
    check('sl(B2F) = -9050', abs(ls.sl('B2F') - (-9050)) < 0.1)
    check('sl(없는층) = None', ls.sl('B3F') is None)


# ─────────────────────────────────────────────────────────────
# 3. full_extractor — _parse_section, _shoelace_area
# ─────────────────────────────────────────────────────────────

def test_full_extractor():
    print('\n[full_extractor] 추출기 로직 검증')
    from core.dxf_parser.full_extractor import _parse_section, _shoelace_area, _in_clip

    # 블록명 파싱
    w, h = _parse_section('C400X800', 1.0, 1.0)
    check('C400X800 파싱', abs(w - 400) < 0.1 and abs(h - 800) < 0.1,
          f'got ({w},{h})')

    w2, h2 = _parse_section('B2-B1 C2', 1.0, 1.0)
    check('B2-B1 C2 기본값', w2 == 500.0, f'got ({w2},{h2})')

    w3, h3 = _parse_section('C500', 1.0, 1.0)
    check('C500 정방형', abs(w3 - 500) < 0.1 and abs(h3 - 500) < 0.1,
          f'got ({w3},{h3})')

    w4, h4 = _parse_section('TC600X900', 1.0, 1.0)
    check('TC600X900', abs(w4 - 600) < 0.1 and abs(h4 - 900) < 0.1,
          f'got ({w4},{h4})')

    # 폴리라인 면적
    sq = [(0,0), (10,0), (10,10), (0,10)]
    area = _shoelace_area(sq)
    check('정사각형 면적 100', abs(area - 100) < 0.01, f'got {area}')

    tri = [(0,0), (1,0), (0,1)]
    area2 = _shoelace_area(tri)
    check('삼각형 면적 0.5', abs(area2 - 0.5) < 0.01, f'got {area2}')

    # 클립 검사
    check('클립 내부 True', _in_clip(5, 5, (0, 0, 10, 10)))
    check('클립 외부 False', not _in_clip(15, 5, (0, 0, 10, 10)))
    check('clip=None → True', _in_clip(999, 999, None))


# ─────────────────────────────────────────────────────────────
# 4. step_zone — StepZone, StepZoneMap
# ─────────────────────────────────────────────────────────────

def test_step_zone():
    print('\n[step_zone] 단차 구역 검증')
    from core.dxf_parser.step_zone import StepZone, StepZoneMap

    base_sl = {'B2F': -9050.0, 'B1F': -5600.0}

    zone = StepZone(x=100, y=200, floor_label='B2F', delta_mm=1600)
    abs_sl = zone.absolute_sl(base_sl)
    check('B2F +1600 절대SL = -7450', abs_sl is not None and abs(abs_sl - (-7450)) < 0.1,
          f'got {abs_sl}')

    zone_neg = StepZone(x=0, y=0, floor_label='B2F', delta_mm=-1800)
    abs_sl2 = zone_neg.absolute_sl(base_sl)
    check('B2F -1800 절대SL = -10850', abs_sl2 is not None and abs(abs_sl2 - (-10850)) < 0.1,
          f'got {abs_sl2}')

    zone_map = StepZoneMap(
        zones=[StepZone(x=500, y=500, floor_label='B2F', delta_mm=1600, radius_mm=1000)],
        base_sl=base_sl,
    )
    # 단차 구역 안
    sl_inside = zone_map.slab_z(500, 500, 'B2F')
    check('단차 구역 내 SL = -7450', abs(sl_inside - (-7450)) < 0.1,
          f'got {sl_inside}')
    # 단차 구역 밖
    sl_outside = zone_map.slab_z(5000, 5000, 'B2F')
    check('단차 구역 외 SL = -9050 (기준)', abs(sl_outside - (-9050)) < 0.1,
          f'got {sl_outside}')
    # 다른 층 — 단차 영향 없음
    sl_b1f = zone_map.slab_z(500, 500, 'B1F')
    check('B1F는 단차 영향 없음 = -5600', abs(sl_b1f - (-5600)) < 0.1,
          f'got {sl_b1f}')


# ─────────────────────────────────────────────────────────────
# 5. ev_detector — _cluster_center
# ─────────────────────────────────────────────────────────────

def test_ev_detector():
    print('\n[ev_detector] 클러스터 중심 검증')
    from core.dxf_parser.ev_detector import _cluster_center

    # 같은 위치 3개 점
    candidates = [(100.0, 200.0, 0.9), (101.0, 199.0, 0.8), (99.0, 201.0, 0.7)]
    cx, cy, conf = _cluster_center(candidates, radius=50.0)
    check('클러스터 중심 X ≈ 100', abs(cx - 100) < 2, f'got cx={cx:.1f}')
    check('클러스터 중심 Y ≈ 200', abs(cy - 200) < 2, f'got cy={cy:.1f}')
    check('신뢰도 > 0', conf > 0)

    # 단일 점
    single = [(50.0, 75.0, 1.0)]
    cx2, cy2, _ = _cluster_center(single, radius=100.0)
    check('단일점 통과', abs(cx2 - 50) < 0.1 and abs(cy2 - 75) < 0.1)


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 60)
    print('dxf_parser 단위 검증')
    print('=' * 60)

    test_drawing_transform()
    test_level_parser()
    test_full_extractor()
    test_step_zone()
    test_ev_detector()

    print(f'\n{"="*60}')
    print(f'결과: {_passed} 통과 / {_failed} 실패 / {_passed+_failed} 전체')
    if _failed == 0:
        print('전체 PASS')
    else:
        print(f'주의: {_failed}건 실패')
        sys.exit(1)
