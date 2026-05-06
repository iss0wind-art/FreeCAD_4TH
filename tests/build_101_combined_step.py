"""
build_101_combined_step.py
==========================
101동 동체 + 주변 주차장 통합 STEP 빌드

방부장 친명 현실 테스트 두 번째 — 통합 임무

[배경]
A1 (101동 동체): tests/poc_101_b1_b2_dong_stack.py
  - STEP: output/poc_101_b1_b2_dong.step (2.9MB)
  - 좌표계: 도엽 SW 기준 정규화 (S30-001 sw=(116247, 2290548))
  - 기둥 cx 범위: 약 0~126000 (도엽 폭)
  - 419 솔리드

A2 (주변 주차장): tests/poc_101_around_parking.py
  - STEP: output/poc_101_around_parking.step (665KB)
  - 좌표계: 지하주차장 도엽 SW 기준 정규화
  - 기둥 cx 범위: 약 330000~392000 (mm, 도엽 SW로 정규화)
  - 99 솔리드

[좌표 정렬 전략]
A1 좌표계: 도엽 S30-001 SW=(116247, 2290548) 기준 정규화
  → 솔리드들의 cx 범위 ≈ 0 ~ 50000 (101동 footprint ~50m×47m)

A2 좌표계: 지하주차장 B2 도엽 SW=(247250, -1390677) 기준 정규화
  → 101동 텍스트 상대 좌표 = (384832, 93939)
  → 솔리드들의 cx 범위 ≈ 330000 ~ 392000 (클립 중심 384832 ± 55000)

A2를 A1 좌표계로 변환:
  - A2의 101동 중심 = 클립 중심 = (384832, 93939) [도엽 상대]
  - A1의 101동 중심 = A1 솔리드 BBox 중심 (cx, cy)
  - 변환: A2_x' = A2_x - 384832 + A1_cx
          A2_y' = A2_y - 93939  + A1_cy

[검증]
통합 BoundingBox가 약 110m × 107m (클립 영역 크기) 이하로 합리적이어야 한다.

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/build_101_combined_step.py
"""

import os, sys, json, math, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

A1_STEP = "output/poc_101_b1_b2_dong.step"
A1_JSON = "output/poc_101_b1_b2_dong.json"
A2_STEP = "output/poc_101_around_parking.step"
A2_JSON = "output/poc_101_around_parking.json"
OUT_STEP = "output/poc_101_combined.step"
OUT_JSON = "output/poc_101_combined.json"

# A2 101동 중심 (지하주차장 도엽 상대 좌표 기준)
# probe 결과 박제: B2 도엽 상대=(384832, 93939), B1 도엽 상대=(385019, 93870)
# 두 도엽 평균 사용 (B2·B1 평균)
A2_DONG_101_CX_RELATIVE = (384832.0 + 385019.0) / 2  # ≈ 384925.5
A2_DONG_101_CY_RELATIVE = (93939.0 + 93870.0) / 2    # ≈ 93904.5


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def compute_a1_center(a1_data):
    """A1 솔리드 메타에서 101동 동체 중심 cx, cy 추정."""
    all_cx = []
    all_cy = []
    for sheet in a1_data['sheets']:
        for col in sheet['columns']:
            all_cx.append(col['cx'])
            all_cy.append(col['cy'])
        for g in sheet['girders']:
            p1, p2 = g['p1'], g['p2']
            all_cx.append((p1[0] + p2[0]) / 2)
            all_cy.append((p1[1] + p2[1]) / 2)
    if not all_cx:
        return 0.0, 0.0
    cx = (min(all_cx) + max(all_cx)) / 2
    cy = (min(all_cy) + max(all_cy)) / 2
    return cx, cy


def main():
    print('=' * 65)
    print('build_101_combined_step.py')
    print('101동 동체 + 주변 주차장 통합 STEP 빌드')
    print('=' * 65)

    t0 = time.time()

    # ── JSON 로드 ──────────────────────────────────────────────
    print(f'\n[메타 로드]')
    a1_data = load_json(A1_JSON)
    a2_data = load_json(A2_JSON)
    print(f'  A1: {a1_data["totals"]["solids"]}솔리드 (기둥 {a1_data["totals"]["columns"]} + 거더 {a1_data["totals"]["girders"]})')
    print(f'  A2: {a2_data["totals"]["solids"]}솔리드 (기둥 {a2_data["totals"]["columns"]} + 거더 {a2_data["totals"]["girders"]})')

    # ── 좌표 정렬 계산 ─────────────────────────────────────────
    print(f'\n[좌표 정렬 계산]')

    # A1 솔리드 중심 (도엽 정규화 좌표)
    a1_cx, a1_cy = compute_a1_center(a1_data)
    print(f'  A1 솔리드 중심: ({a1_cx:.1f}, {a1_cy:.1f}) mm')

    # A2 101동 중심 (도엽 정규화 좌표)
    print(f'  A2 101동 텍스트 상대 좌표: ({A2_DONG_101_CX_RELATIVE:.1f}, {A2_DONG_101_CY_RELATIVE:.1f}) mm')

    # 변환 벡터: A2 솔리드를 A1 좌표계로 이동
    dx = a1_cx - A2_DONG_101_CX_RELATIVE
    dy = a1_cy - A2_DONG_101_CY_RELATIVE
    print(f'  평행 이동 벡터: dx={dx:.1f}, dy={dy:.1f} mm')
    print(f'  (A2 솔리드 각 점에 이 벡터를 더함)')

    # ── FreeCAD STEP 빌드 ──────────────────────────────────────
    print(f'\n[FreeCAD STEP 로드 및 변환]')
    import FreeCAD
    import Part

    # A1 로드 (좌표 그대로 사용)
    print(f'  A1 STEP 로드: {A1_STEP}')
    if not os.path.exists(A1_STEP):
        print(f'  [오류] A1 STEP 없음: {A1_STEP}')
        return
    a1_shape = Part.Shape()
    a1_shape.read(A1_STEP)
    print(f'  A1 STEP 로드 완료 — BoundBox: '
          f'X[{a1_shape.BoundBox.XMin:.0f} ~ {a1_shape.BoundBox.XMax:.0f}] '
          f'Y[{a1_shape.BoundBox.YMin:.0f} ~ {a1_shape.BoundBox.YMax:.0f}] '
          f'Z[{a1_shape.BoundBox.ZMin:.0f} ~ {a1_shape.BoundBox.ZMax:.0f}]')

    # A2 로드 + 평행 이동
    print(f'  A2 STEP 로드: {A2_STEP}')
    if not os.path.exists(A2_STEP):
        print(f'  [오류] A2 STEP 없음: {A2_STEP}')
        return
    a2_shape = Part.Shape()
    a2_shape.read(A2_STEP)
    print(f'  A2 STEP 로드 완료 — BoundBox: '
          f'X[{a2_shape.BoundBox.XMin:.0f} ~ {a2_shape.BoundBox.XMax:.0f}] '
          f'Y[{a2_shape.BoundBox.YMin:.0f} ~ {a2_shape.BoundBox.YMax:.0f}] '
          f'Z[{a2_shape.BoundBox.ZMin:.0f} ~ {a2_shape.BoundBox.ZMax:.0f}]')

    # A2 평행 이동 (좌표 정렬)
    print(f'  A2 평행 이동 적용: dx={dx:.1f} dy={dy:.1f}')
    move_vec = FreeCAD.Vector(dx, dy, 0)
    a2_moved = a2_shape.copy()
    a2_moved.translate(move_vec)
    print(f'  A2 이동 후 BoundBox: '
          f'X[{a2_moved.BoundBox.XMin:.0f} ~ {a2_moved.BoundBox.XMax:.0f}] '
          f'Y[{a2_moved.BoundBox.YMin:.0f} ~ {a2_moved.BoundBox.YMax:.0f}]')

    # 통합 Compound
    print(f'\n[통합 Compound 생성]')
    # A1과 A2(이동 후) 서브셰이프 결합
    a1_solids = a1_shape.Solids
    a2_solids = a2_moved.Solids
    total_solids = len(a1_solids) + len(a2_solids)
    print(f'  A1 솔리드: {len(a1_solids)}개')
    print(f'  A2 솔리드 (이동 후): {len(a2_solids)}개')
    print(f'  합계: {total_solids}개')

    all_solids = a1_solids + a2_solids
    compound = Part.makeCompound(all_solids)

    # 검증
    bb = compound.BoundBox
    w_m = (bb.XMax - bb.XMin) / 1000
    h_m = (bb.YMax - bb.YMin) / 1000
    print(f'\n[통합 BoundBox 검증]')
    print(f'  X: {bb.XMin:.0f} ~ {bb.XMax:.0f} mm  →  폭 {w_m:.1f}m')
    print(f'  Y: {bb.YMin:.0f} ~ {bb.YMax:.0f} mm  →  높이 {h_m:.1f}m')
    print(f'  Z: {bb.ZMin:.0f} ~ {bb.ZMax:.0f} mm')
    bbox_ok = w_m <= 200 and h_m <= 200  # 합리적 범위 200m 이내
    print(f'  합리성 검증: {"통과 (≤200m)" if bbox_ok else "경고 (>200m, 좌표 정렬 확인 필요)"}')

    # STEP 출력
    os.makedirs('output', exist_ok=True)
    compound.exportStep(OUT_STEP)
    print(f'\n[STEP 저장] {OUT_STEP}')

    # 총 부피 계산
    total_volume = sum(s.Volume for s in all_solids if s.isValid())
    total_volume_m3 = total_volume / 1e9

    # 무효 솔리드 확인
    invalid_count = sum(1 for s in all_solids if not s.isValid())

    print(f'\n[통합 메타 박제]')
    elapsed = round(time.time() - t0, 1)

    out = {
        'project': '부산 에코델타 24BL 101동 동체 + 주변 주차장 통합',
        'directive': '방부장 친명 현실 테스트 두 번째 — 통합 STEP',
        'sources': {
            'A1': {
                'label': '101동 동체 B1·B2',
                'step': A1_STEP,
                'solids': len(a1_solids),
                'columns': a1_data['totals']['columns'],
                'girders': a1_data['totals']['girders'],
                'volume_m3': a1_data['totals']['volume_m3'],
            },
            'A2': {
                'label': '101동 주변 지하주차장 B1·B2',
                'step': A2_STEP,
                'solids': len(a2_solids),
                'columns': a2_data['totals']['columns'],
                'girders': a2_data['totals']['girders'],
                'volume_m3': a2_data['totals']['volume_m3'],
            },
        },
        'coordinate_alignment': {
            'method': 'A2를 A1 좌표계로 평행 이동',
            'description': (
                'A1(101동 동체)은 도엽 S30-001 SW 기준 정규화 좌표. '
                'A2(주변 주차장)는 지하주차장 도엽 SW 기준 정규화 좌표. '
                'A2의 "101" 텍스트 상대 좌표를 A1의 동체 솔리드 중심에 정렬.'
            ),
            'a1_center_mm': [round(a1_cx, 1), round(a1_cy, 1)],
            'a2_dong101_relative_mm': [
                round(A2_DONG_101_CX_RELATIVE, 1),
                round(A2_DONG_101_CY_RELATIVE, 1),
            ],
            'translation_vector_mm': [round(dx, 1), round(dy, 1)],
        },
        'totals': {
            'solids': total_solids,
            'columns': a1_data['totals']['columns'] + a2_data['totals']['columns'],
            'girders': a1_data['totals']['girders'] + a2_data['totals']['girders'],
            'volume_m3': round(total_volume_m3, 3),
            'invalid_solids': invalid_count,
        },
        'bounding_box_mm': {
            'x_min': round(bb.XMin, 1), 'x_max': round(bb.XMax, 1),
            'y_min': round(bb.YMin, 1), 'y_max': round(bb.YMax, 1),
            'z_min': round(bb.ZMin, 1), 'z_max': round(bb.ZMax, 1),
            'width_m': round(w_m, 2), 'height_m': round(h_m, 2),
        },
        'validation': {
            'bbox_reasonable': bool(bbox_ok),
            'invalid_solids': invalid_count,
            'note': (
                'BoundBox 폭·높이 ≤ 200m이면 좌표 정렬 합리적. '
                '두 모델이 겹치거나 110m×107m 범위 내에 있어야 함.'
            ),
        },
        'elapsed_s': elapsed,
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'[메타] {OUT_JSON}')

    print(f'\n{"="*65}')
    print(f'[종합 결과]')
    print(f'  A1 솔리드: {len(a1_solids)}개 (기둥 {a1_data["totals"]["columns"]} + 거더 {a1_data["totals"]["girders"]})')
    print(f'  A2 솔리드: {len(a2_solids)}개 (기둥 {a2_data["totals"]["columns"]} + 거더 {a2_data["totals"]["girders"]})')
    print(f'  통합 솔리드: {total_solids}개')
    print(f'  통합 부피: {total_volume_m3:.3f} m³')
    print(f'  무효 솔리드: {invalid_count}개')
    print(f'  통합 BBox: 폭 {w_m:.1f}m × 높이 {h_m:.1f}m')
    print(f'  처리 시간: {elapsed}초')
    print(f'{"="*65}')


if __name__ == '__main__':
    main()
