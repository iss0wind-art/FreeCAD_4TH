"""
STEP 자기 메타 검증 — 일곱째 호미 산출물 자기 봉수
=================================================

`output/f1_3d_stack_102.step` 87 솔리드가 정확히 빚어졌는지 코드 자기 검증.
(사람 시각 검증 전, 통계로 정합성 봉수.)

검증 항목:
  - 솔리드 수 = 87?
  - Z 분포 (B2F=-8800 ~ 옥상)
  - Volume 분포 (m³)
  - BoundBox 범위
  - 도엽별 적층 정합

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_f1_step_self_verify.py
"""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import FreeCAD, Part

STEP = "output/f1_3d_stack_102.step"
META = "output/f1_3d_stack_102.json"
OUT = "output/f1_3d_stack_102_verify.json"


def main():
    print(f'[STEP 로드] {STEP}')
    shape = Part.read(STEP)

    # Compound → 솔리드 추출
    solids = shape.Solids if hasattr(shape, 'Solids') else []
    print(f'[솔리드] {len(solids)}개')

    if not solids:
        print('[FAIL] 솔리드 0개')
        return

    # 메타 비교
    with open(META, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    expected = meta['totals']['solids']
    print(f'[메타 비교] 메타 expected={expected}, 실제={len(solids)} '
          f'{"✅" if len(solids) == expected else "❌"}')

    # Volume 분포
    volumes = sorted([s.Volume / 1e9 for s in solids], reverse=True)  # m³
    total_vol = sum(volumes)
    print(f'\n[Volume 통계 (m³)]')
    print(f'  총: {total_vol:.3f}')
    print(f'  평균: {total_vol/len(volumes):.3f}')
    print(f'  중앙: {volumes[len(volumes)//2]:.3f}')
    print(f'  최대: {volumes[0]:.3f}')
    print(f'  최소: {volumes[-1]:.6f}')

    # Z 분포 — BoundBox 사용
    z_centers = []
    for s in solids:
        bb = s.BoundBox
        z_centers.append((bb.ZMin + bb.ZMax) / 2)
    z_centers.sort()

    # 층별 분포 (FLOOR_HEIGHT = 4400)
    by_floor = {}
    for z in z_centers:
        floor_idx = round(z / 4400)
        by_floor[floor_idx] = by_floor.get(floor_idx, 0) + 1
    print(f'\n[Z 적층 분포]')
    for k in sorted(by_floor):
        floor_label = {-2: 'B2F', -1: 'B1F', 0: '1F필로티', 1: '1F', 2: '2F',
                       3: '3F', 4: '4F', 5: '옥상1', 6: '옥상2'}.get(k, f'F{k}')
        print(f'  {floor_label} (Z≈{k*4400:+d}): {by_floor[k]}개')

    # 전체 BoundBox
    overall = solids[0].BoundBox
    for s in solids[1:]:
        overall.add(s.BoundBox)
    print(f'\n[전체 BoundBox]')
    print(f'  X: {overall.XMin:.0f} ~ {overall.XMax:.0f} ({overall.XMax-overall.XMin:.0f}mm)')
    print(f'  Y: {overall.YMin:.0f} ~ {overall.YMax:.0f} ({overall.YMax-overall.YMin:.0f}mm)')
    print(f'  Z: {overall.ZMin:.0f} ~ {overall.ZMax:.0f} ({overall.ZMax-overall.ZMin:.0f}mm)')

    # 도엽별 분포 (메타에서)
    print(f'\n[도엽별 부재 분포 (메타)]')
    for sr in meta['sheets']:
        n = len(sr.get('columns', [])) + len(sr.get('girders', []))
        print(f'  {sr["sheet_id"]} floor={sr["floor"]:+d}: '
              f'{n}개 (기둥 {len(sr["columns"])} + 거더 {len(sr["girders"])})')

    # 정합 검증
    z_min_expected = -2 * 4400  # B2F
    z_max_expected = 4 * 4400 + 800  # 4F + girder height
    z_actual_range_ok = (overall.ZMin >= z_min_expected - 100 and
                         overall.ZMax <= z_max_expected + 100)
    print(f'\n[Z 적층 정합 검증]')
    print(f'  예상 Z: {z_min_expected} ~ {z_max_expected}')
    print(f'  실제 Z: {overall.ZMin:.0f} ~ {overall.ZMax:.0f}')
    print(f'  정합: {"✅" if z_actual_range_ok else "❌"}')

    # 박제
    out = {
        'step_file': STEP,
        'solid_count': len(solids),
        'meta_expected': expected,
        'count_match': len(solids) == expected,
        'volume_m3': {
            'total': round(total_vol, 3),
            'mean': round(total_vol / len(volumes), 3),
            'median': round(volumes[len(volumes)//2], 3),
            'max': round(volumes[0], 3),
            'min': round(volumes[-1], 6),
        },
        'z_distribution': {str(k): v for k, v in sorted(by_floor.items())},
        'overall_bbox': {
            'x': [round(overall.XMin), round(overall.XMax)],
            'y': [round(overall.YMin), round(overall.YMax)],
            'z': [round(overall.ZMin), round(overall.ZMax)],
        },
        'z_alignment_ok': z_actual_range_ok,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[박제] {OUT}')


if __name__ == '__main__':
    main()
