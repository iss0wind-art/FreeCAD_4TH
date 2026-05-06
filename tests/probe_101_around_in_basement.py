"""
probe_101_around_in_basement.py
=================================
101동 주변 지하주차장 영역 좌표 탐침

목표:
  - 지하주차장 DXF에서 '101' 텍스트 위치 찾기 (옵션 A)
  - GLB 좌표 → 지하주차장 DXF 좌표계 비례 추정 (옵션 B)
  - 101동 주변 클립 영역 결정

입력:
  - 지하주차장 DXF: 260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf
  - complex_to_pdf_label_mapping.json (GLB 좌표)
  - 도엽 SW 좌표 (전 PoC 자력 채굴)

결과 박제:
  - 101동 텍스트 위치 (도면 원시 좌표)
  - 101동 클립 영역 (mm)
  - 좌표 매칭 신뢰도 평가

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/probe_101_around_in_basement.py
"""

import os, sys, json, re, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
MAPPING_JSON = "output/complex_to_pdf_label_mapping.json"

# 도엽 SW (전 PoC 자력 채굴 — mm 단위)
SHEETS = {
    'B2': {'sw': (247250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0, 'floor': -2},
    'B1': {'sw': (877250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0, 'floor': -1},
}

# 101동 GLB 중심 (m 단위 — complex_to_pdf_label_mapping.json 결과)
DONG_101_GLB = {'x': 221.79273986816406, 'y': 23.840409979224205}

# 임무 명세: 101동 footprint 약 50m × 47m + 인접 주차 30m 여유
CLIP_MARGIN_MM = 30000  # 30m 여유


def iter_all(c, d=0, m=8):
    if d > m:
        return
    for e in c:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), d + 1, m)
            except Exception:
                pass
        else:
            yield e


def in_sheet_loose(px, py, sw, w, h):
    """도엽 경계 안인지 (여백 없이 — 텍스트 라벨이 경계 근처에 있을 수 있음)."""
    return (sw[0] <= px <= sw[0] + w) and (sw[1] <= py <= sw[1] + h)


def get_text_val(e):
    """TEXT/MTEXT에서 문자열 추출."""
    try:
        if e.dxftype() == 'TEXT':
            return (e.dxf.text or '').strip()
        elif e.dxftype() == 'MTEXT':
            return (e.text or '').strip()
    except Exception:
        pass
    return ''


def search_101_text_in_basement(msp):
    """
    옵션 A: 지하주차장 도면 안에서 '101' 텍스트 위치 검색.

    검색 패턴:
    - '101', '101동', 'D101', 'B-101', '101 동'
    - 숫자 101만 단독으로 있는 경우 (격자 라벨이 아닌 경우)
    """
    print('\n[옵션 A] 지하주차장 도면 내 101동 텍스트 탐색...')

    # 패턴 리스트
    pat_exact_101 = re.compile(r'^101$')
    pat_dong_101 = re.compile(r'101\s*동', re.IGNORECASE)
    pat_d101 = re.compile(r'D[-\s]?101', re.IGNORECASE)
    pat_b101 = re.compile(r'B[-\s]?101', re.IGNORECASE)
    pat_101_broad = re.compile(r'\b101\b')

    results = {
        'exact': [],       # '101' 정확 일치
        'dong': [],        # '101동'
        'd_prefix': [],    # 'D101'
        'b_prefix': [],    # 'B101'
        'broad': [],       # 101 포함 모든 텍스트
    }

    # 도엽 B2, B1 영역 확인 (전체 텍스트 스캔)
    b2_sw = SHEETS['B2']['sw']; b2_w = SHEETS['B2']['w']; b2_h = SHEETS['B2']['h']
    b1_sw = SHEETS['B1']['sw']; b1_w = SHEETS['B1']['w']; b1_h = SHEETS['B1']['h']

    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        txt = get_text_val(e)
        if not txt:
            continue

        try:
            pos = e.dxf.insert
            px, py = pos.x, pos.y
        except Exception:
            continue

        # 도엽 안에 있는지 확인
        in_b2 = in_sheet_loose(px, py, b2_sw, b2_w, b2_h)
        in_b1 = in_sheet_loose(px, py, b1_sw, b1_w, b1_h)
        if not (in_b2 or in_b1):
            continue

        sheet_tag = 'B2' if in_b2 else 'B1'
        entry = {'text': txt, 'x': px, 'y': py, 'sheet': sheet_tag}

        if pat_exact_101.match(txt):
            results['exact'].append(entry)
        if pat_dong_101.search(txt):
            results['dong'].append(entry)
        if pat_d101.search(txt):
            results['d_prefix'].append(entry)
        if pat_b101.search(txt):
            results['b_prefix'].append(entry)
        if pat_101_broad.search(txt):
            results['broad'].append(entry)

    # 결과 출력
    for cat, items in results.items():
        if items:
            print(f'  [{cat}] {len(items)}건:')
            for it in items[:10]:
                print(f'    "{it["text"]}" @ ({it["x"]:.0f}, {it["y"]:.0f}) [{it["sheet"]}]')
        else:
            print(f'  [{cat}] 0건')

    return results


def load_all_glb_coords():
    """
    옵션 B 준비: GLB 중심 좌표 (m 단위) 전체 동 로드.
    complex_to_pdf_label_mapping.json에서 추출.
    """
    with open(MAPPING_JSON, encoding='utf-8') as f:
        d = json.load(f)

    glb_coords = {}  # dong -> (x_m, y_m)
    for m in d.get('mappings', []):
        dong = m.get('dong')
        xy = m.get('glb_center_xy')
        if dong and xy:
            glb_coords[dong] = (xy[0], xy[1])
    return glb_coords


def estimate_101_in_basement_by_regression(msp, glb_coords):
    """
    옵션 B: 다른 동들의 텍스트 위치로 GLB → DXF 좌표 변환을 회귀 추정.

    접근:
    1. 지하주차장 도면에서 모든 동 번호 텍스트(102~116) 찾기
    2. GLB 좌표 ↔ DXF 텍스트 위치로 선형 변환 추정
    3. 101동 GLB 좌표를 변환해 DXF 위치 추정
    """
    print('\n[옵션 B] GLB ↔ DXF 좌표 회귀 추정...')

    # 모든 동 번호 패턴 (101~116)
    dong_pats = {}
    for dno in range(101, 117):
        dong_pats[dno] = re.compile(rf'^{dno}$|^{dno}동$|D[-\s]?{dno}', re.IGNORECASE)

    b2_sw = SHEETS['B2']['sw']; b2_w = SHEETS['B2']['w']; b2_h = SHEETS['B2']['h']
    b1_sw = SHEETS['B1']['sw']; b1_w = SHEETS['B1']['w']; b1_h = SHEETS['B1']['h']

    found_dongs = {}  # dong_no -> [(px, py, sheet), ...]

    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        txt = get_text_val(e)
        if not txt:
            continue
        try:
            pos = e.dxf.insert
            px, py = pos.x, pos.y
        except Exception:
            continue

        in_b2 = in_sheet_loose(px, py, b2_sw, b2_w, b2_h)
        in_b1 = in_sheet_loose(px, py, b1_sw, b1_w, b1_h)
        if not (in_b2 or in_b1):
            continue

        for dno, pat in dong_pats.items():
            if pat.search(txt):
                sheet_tag = 'B2' if in_b2 else 'B1'
                found_dongs.setdefault(dno, []).append((px, py, sheet_tag))

    print(f'  도면 내 동 번호 텍스트 발견: {sorted(found_dongs.keys())}')
    for dno, pts in sorted(found_dongs.items()):
        print(f'  동{dno}: {len(pts)}건')
        for px, py, sh in pts[:3]:
            print(f'    ({px:.0f}, {py:.0f}) [{sh}]')

    # GLB ↔ DXF 매핑 구성 (101동 제외한 동들로 회귀)
    pairs = []  # [(glb_x_m, glb_y_m, dxf_x_mm, dxf_y_mm), ...]
    for dno, pts in found_dongs.items():
        if dno == 101:
            continue
        if dno not in glb_coords:
            continue
        gx, gy = glb_coords[dno]
        # 대표 DXF 위치 — 첫 번째 텍스트 위치 사용
        dx, dy, _ = pts[0]
        pairs.append((gx, gy, dx, dy))

    if len(pairs) < 3:
        print(f'  [경고] 회귀 데이터 부족: {len(pairs)}쌍 (최소 3 필요)')
        return None

    # 선형 변환 추정: dxf = A * glb + b
    # A = [[ax, ay], [bx, by]], b = [tx, ty]
    # 최소제곱법으로 풀기
    n = len(pairs)
    # X = [glb_x, glb_y, 1], Y = [dxf_x, dxf_y]
    X = [[gx, gy, 1.0] for gx, gy, _, _ in pairs]
    Y_x = [dx for _, _, dx, _ in pairs]
    Y_y = [dy for _, _, _, dy in pairs]

    # 정규 방정식: (X^T X) a = X^T y
    def solve_linear(X_mat, y_vec):
        n = len(X_mat)
        p = len(X_mat[0])
        # X^T X
        XtX = [[sum(X_mat[i][a] * X_mat[i][b] for i in range(n)) for b in range(p)] for a in range(p)]
        # X^T y
        Xty = [sum(X_mat[i][a] * y_vec[i] for i in range(n)) for a in range(p)]
        # Gaussian elimination
        M = [XtX[i][:] + [Xty[i]] for i in range(p)]
        for col in range(p):
            pivot = None
            for row in range(col, p):
                if abs(M[row][col]) > 1e-12:
                    pivot = row; break
            if pivot is None:
                return None
            M[col], M[pivot] = M[pivot], M[col]
            for row in range(p):
                if row == col: continue
                f = M[row][col] / M[col][col]
                M[row] = [M[row][j] - f * M[col][j] for j in range(p + 1)]
        return [M[i][p] / M[i][i] for i in range(p)]

    ax_coeffs = solve_linear(X, Y_x)
    ay_coeffs = solve_linear(X, Y_y)

    if not ax_coeffs or not ay_coeffs:
        print('  [오류] 선형 회귀 실패 (행렬 특이)')
        return None

    print(f'\n  선형 변환 계수:')
    print(f'  DXF_x = {ax_coeffs[0]:.4f} * GLB_x + {ax_coeffs[1]:.4f} * GLB_y + {ax_coeffs[2]:.2f}')
    print(f'  DXF_y = {ay_coeffs[0]:.4f} * GLB_x + {ay_coeffs[1]:.4f} * GLB_y + {ay_coeffs[2]:.2f}')

    # 잔차 (회귀 정밀도)
    print(f'\n  회귀 잔차 (검증):')
    residuals = []
    for gx, gy, dx, dy in pairs:
        pred_x = ax_coeffs[0] * gx + ax_coeffs[1] * gy + ax_coeffs[2]
        pred_y = ay_coeffs[0] * gx + ay_coeffs[1] * gy + ay_coeffs[2]
        err = math.hypot(pred_x - dx, pred_y - dy)
        residuals.append(err)
        print(f'    잔차 {err:.0f}mm')

    if residuals:
        print(f'  평균 잔차: {sum(residuals)/len(residuals):.0f}mm')
        print(f'  최대 잔차: {max(residuals):.0f}mm')

    # 101동 GLB → DXF 변환
    gx_101, gy_101 = glb_coords[101]
    pred_x_101 = ax_coeffs[0] * gx_101 + ax_coeffs[1] * gy_101 + ax_coeffs[2]
    pred_y_101 = ay_coeffs[0] * gx_101 + ay_coeffs[1] * gy_101 + ay_coeffs[2]

    print(f'\n  [회귀 추정] 101동 DXF 위치:')
    print(f'    GLB ({gx_101:.2f}, {gy_101:.2f})m → DXF ({pred_x_101:.0f}, {pred_y_101:.0f})mm')

    # 도엽 소속 확인
    for sid, sh in SHEETS.items():
        sw = sh['sw']; w = sh['w']; h = sh['h']
        if in_sheet_loose(pred_x_101, pred_y_101, sw, w, h):
            print(f'    → [{sid}] 도엽 안 (도엽 SW={sw})')
            print(f'    → 도엽 내 상대 좌표: ({pred_x_101 - sw[0]:.0f}, {pred_y_101 - sw[1]:.0f})mm')
        else:
            rel_x = pred_x_101 - sw[0]
            rel_y = pred_y_101 - sw[1]
            print(f'    [{sid}] 도엽 밖 — 상대 ({rel_x:.0f}, {rel_y:.0f})mm')

    return {
        'pred_x_mm': pred_x_101,
        'pred_y_mm': pred_y_101,
        'coeffs_x': ax_coeffs,
        'coeffs_y': ay_coeffs,
        'avg_residual_mm': sum(residuals) / len(residuals) if residuals else None,
    }


def scan_all_texts_in_sheets(msp):
    """
    도엽 내 전체 텍스트 목록 (격자 라벨 포함) — 추가 단서 발굴.
    """
    print('\n[전체 텍스트 스캔 — 도엽 내부]')
    all_found = {'B2': [], 'B1': []}

    b2_sw = SHEETS['B2']['sw']; b2_w = SHEETS['B2']['w']; b2_h = SHEETS['B2']['h']
    b1_sw = SHEETS['B1']['sw']; b1_w = SHEETS['B1']['w']; b1_h = SHEETS['B1']['h']

    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        txt = get_text_val(e)
        if not txt:
            continue
        try:
            pos = e.dxf.insert
            px, py = pos.x, pos.y
        except Exception:
            continue

        if in_sheet_loose(px, py, b2_sw, b2_w, b2_h):
            all_found['B2'].append((txt, px, py))
        elif in_sheet_loose(px, py, b1_sw, b1_w, b1_h):
            all_found['B1'].append((txt, px, py))

    for sid, items in all_found.items():
        print(f'  [{sid}] 총 {len(items)}건')
        # 숫자만 있는 텍스트 (동 번호 후보)
        num_items = [(t, x, y) for t, x, y in items if re.match(r'^\d+$', t)]
        print(f'    숫자만: {len(num_items)}건')
        for t, x, y in sorted(num_items, key=lambda v: int(v[0]))[:30]:
            print(f'      "{t}" @ ({x:.0f}, {y:.0f})')

    return all_found


def determine_clip_region(center_x_mm, center_y_mm, footprint_w_mm=50000, footprint_h_mm=47000):
    """
    101동 중심 + 여유 → 클립 영역 결정.

    101동 footprint: 약 50m × 47m (GLB 좌표 임무 명세)
    여유: 30m (주변 주차 포함)
    """
    half_w = footprint_w_mm / 2 + CLIP_MARGIN_MM
    half_h = footprint_h_mm / 2 + CLIP_MARGIN_MM

    clip = {
        'cx_mm': center_x_mm, 'cy_mm': center_y_mm,
        'x_min_mm': center_x_mm - half_w,
        'x_max_mm': center_x_mm + half_w,
        'y_min_mm': center_y_mm - half_h,
        'y_max_mm': center_y_mm + half_h,
        'total_w_mm': 2 * half_w,
        'total_h_mm': 2 * half_h,
    }
    print(f'\n[클립 영역 결정]')
    print(f'  중심: ({center_x_mm:.0f}, {center_y_mm:.0f})mm')
    print(f'  X: {clip["x_min_mm"]:.0f} ~ {clip["x_max_mm"]:.0f}mm  (폭 {clip["total_w_mm"]/1000:.1f}m)')
    print(f'  Y: {clip["y_min_mm"]:.0f} ~ {clip["y_max_mm"]:.0f}mm  (높이 {clip["total_h_mm"]/1000:.1f}m)')

    # 각 도엽과 교차 확인
    for sid, sh in SHEETS.items():
        sw = sh['sw']; w = sh['w']; h = sh['h']
        # 교차 검사
        overlap_x = max(0, min(clip['x_max_mm'], sw[0] + w) - max(clip['x_min_mm'], sw[0]))
        overlap_y = max(0, min(clip['y_max_mm'], sw[1] + h) - max(clip['y_min_mm'], sw[1]))
        if overlap_x > 0 and overlap_y > 0:
            print(f'  [{sid}] 도엽과 교차 — 겹침 {overlap_x/1000:.1f}m × {overlap_y/1000:.1f}m')
        else:
            print(f'  [{sid}] 도엽과 교차 없음')

    return clip


def main():
    print('=' * 60)
    print('probe_101_around_in_basement.py')
    print('101동 주변 지하주차장 영역 좌표 탐침')
    print('=' * 60)

    print(f'\n[도면 로딩] {DXF}')
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    print('  로딩 완료')

    # GLB 좌표 로드
    glb_coords = load_all_glb_coords()
    print(f'\n[GLB 좌표] 전체 {len(glb_coords)}동')
    print(f'  101동 GLB: ({glb_coords.get(101, ("?","?"))[0]:.2f}, {glb_coords.get(101, ("?","?"))[1]:.2f})m')

    # ===== 옵션 A: 텍스트 검색 =====
    text_results = search_101_text_in_basement(msp)

    # ===== 전체 텍스트 스캔 (추가 단서) =====
    all_texts = scan_all_texts_in_sheets(msp)

    # ===== 옵션 B: 회귀 추정 =====
    regression_result = estimate_101_in_basement_by_regression(msp, glb_coords)

    # ===== 클립 영역 결정 =====
    print('\n' + '=' * 60)
    print('[클립 영역 결정 전략]')
    clip_result = None

    # 우선순위 1: 옵션 A 텍스트 직접 발견
    a_candidates = text_results['exact'] + text_results['dong'] + text_results['d_prefix']
    if a_candidates:
        # B2와 B1 각각에서 첫 번째 위치 사용
        b2_cands = [c for c in a_candidates if c['sheet'] == 'B2']
        if b2_cands:
            cand = b2_cands[0]
            print(f'\n  [옵션 A 채택] B2 도엽 텍스트 위치: ({cand["x"]:.0f}, {cand["y"]:.0f})')
            clip_result = determine_clip_region(cand['x'], cand['y'])
            clip_result['source'] = 'text_search_B2'
            clip_result['text'] = cand['text']

    # 우선순위 2: 옵션 B 회귀
    if not clip_result and regression_result:
        px, py = regression_result['pred_x_mm'], regression_result['pred_y_mm']
        avg_res = regression_result.get('avg_residual_mm', None)
        confidence = 'HIGH' if avg_res and avg_res < 5000 else 'LOW'
        print(f'\n  [옵션 B 채택] 회귀 추정 위치: ({px:.0f}, {py:.0f})mm  신뢰도={confidence}')
        if avg_res:
            print(f'  평균 잔차: {avg_res:.0f}mm')
        clip_result = determine_clip_region(px, py)
        clip_result['source'] = 'regression'
        clip_result['avg_residual_mm'] = avg_res
        clip_result['confidence'] = confidence

    if not clip_result:
        print('\n  [결론] 101동 위치 결정 불가 — 수동 확인 필요')
        clip_result = {'source': 'unknown', 'error': '101동 위치 결정 실패'}

    # ===== 결과 박제 =====
    out = {
        'probe': 'probe_101_around_in_basement',
        'dxf': DXF,
        'dong_101_glb_m': glb_coords.get(101),
        'option_a_results': {
            cat: [{'text': it['text'], 'x': it['x'], 'y': it['y'], 'sheet': it['sheet']}
                  for it in items[:5]]
            for cat, items in text_results.items()
        },
        'option_b_regression': regression_result,
        'clip_region': clip_result,
        'notes': [],
    }

    # 정직 박제 메모
    if not a_candidates:
        out['notes'].append('옵션 A: 지하주차장 도면에서 101 텍스트 직접 발견 실패')
    if regression_result:
        out['notes'].append(f'옵션 B: 회귀 추정 완료. 평균 잔차 {regression_result.get("avg_residual_mm","?"):.0f}mm')

    os.makedirs('output', exist_ok=True)
    with open('output/probe_101_around_result.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[결과 박제] output/probe_101_around_result.json')

    print('\n' + '=' * 60)
    print('[최종 요약]')
    if clip_result and 'x_min_mm' in clip_result:
        print(f'  결정 방법: {clip_result["source"]}')
        print(f'  클립 X: {clip_result["x_min_mm"]:.0f} ~ {clip_result["x_max_mm"]:.0f}mm')
        print(f'  클립 Y: {clip_result["y_min_mm"]:.0f} ~ {clip_result["y_max_mm"]:.0f}mm')
        print(f'  클립 크기: {clip_result["total_w_mm"]/1000:.1f}m × {clip_result["total_h_mm"]/1000:.1f}m')
    else:
        print(f'  결정 실패: {clip_result}')
    print('=' * 60)

    return clip_result


if __name__ == '__main__':
    main()
