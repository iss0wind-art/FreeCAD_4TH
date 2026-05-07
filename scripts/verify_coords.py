"""
verify_coords.py — 좌표 오프셋 검증 스크립트
==============================================
두 도면에서 공통 기준점(기둥) N개를 뽑아
오프셋 적용 후 거리 오차를 측정한다.

기준:
  오차 < 100mm → PASS
  오차 >= 100mm → FAIL + 이유 출력

실행: python scripts/verify_coords.py
"""
import sys
import os
import json
import math
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf

DXF_DONG = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf'
DXF_PKG  = 'D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
COORD_JSON = 'output/coord_config.json'

PASS_THRESHOLD_MM = 100


def iter_all(container, depth=0, max_depth=8):
    if depth > max_depth:
        return
    for e in container:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), depth+1, max_depth)
            except Exception:
                pass
        else:
            yield e


def extract_columns(msp, clip):
    """닫힌 LWPOLYLINE 400~3000mm 크기 → 기둥 중심 목록."""
    cols = []
    for e in iter_all(msp):
        if e.dxftype() != 'LWPOLYLINE':
            continue
        try:
            if not e.is_closed:
                continue
            pts = list(e.get_points())
            if len(pts) < 4:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx = (min(xs) + max(xs)) / 2
            cy = (min(ys) + max(ys)) / 2
            if clip:
                xmin, ymin, xmax, ymax = clip
                if not (xmin <= cx <= xmax and ymin <= cy <= ymax):
                    continue
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if 400 <= w <= 3000 and 400 <= h <= 3000:
                cols.append((cx, cy, round(w), round(h)))
        except Exception:
            pass
    return cols


def dedup(cols, tol=50):
    """중심이 tol mm 이내인 중복 제거."""
    out = []
    for c in cols:
        if not any(math.hypot(c[0]-e[0], c[1]-e[1]) < tol for e in out):
            out.append(c)
    return out


def match_columns(pkg_cols, dong_cols, tx, ty, match_tol=300):
    """PKG 기둥을 TX,TY 변환 후 DONG과 매칭. 매칭 쌍 + 오차 반환."""
    matched = []
    for px, py, pw, ph in pkg_cols:
        ux = px + tx
        uy = py + ty
        best_d = float('inf')
        best = None
        for dx, dy, dw, dh in dong_cols:
            d = math.hypot(ux - dx, uy - dy)
            if d < best_d:
                best_d = d
                best = (dx, dy, dw, dh)
        if best_d < match_tol and best is not None:
            matched.append({
                'pkg': [round(px), round(py)],
                'dong': [round(best[0]), round(best[1])],
                'pkg_unified': [round(ux), round(uy)],
                'error_mm': round(best_d, 1),
            })
    return matched


def main():
    t0 = time.time()
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print('=' * 60)
    print('verify_coords.py — 좌표 오프셋 검증')
    print('=' * 60)

    # coord_config 로드
    with open(COORD_JSON, encoding='utf-8') as f:
        cfg = json.load(f)

    TX = cfg['TX_PKG']
    TY = cfg['TY_PKG']
    TZ_B1F = cfg['TZ_B1F']
    TZ_B2F = cfg['TZ_B2F']
    print(f'\n검증 대상:')
    print(f'  TX={TX}, TY={TY}')
    print(f'  TZ_B1F={TZ_B1F}, TZ_B2F={TZ_B2F}')
    print(f'  method={cfg["method"]}, confidence={cfg["confidence"]}')

    # DXF 로드
    print(f'\n[DXF 로드]')
    doc_dong = ezdxf.readfile(DXF_DONG, encoding='cp949')
    msp_dong = doc_dong.modelspace()
    doc_pkg = ezdxf.readfile(DXF_PKG, encoding='cp949')
    msp_pkg = doc_pkg.modelspace()
    print(f'  로드 완료 ({time.time()-t0:.1f}s)')

    # 기둥 추출
    # DONG: S30-001 (B2F) — PKG와 같은 층
    B2F_SW = (116247.0, 2290548.0)
    dong_clip = (B2F_SW[0], B2F_SW[1],
                 B2F_SW[0] + 126000, B2F_SW[1] + 178200)

    # PKG: 101동 인근 (bsmnt_clip)
    try:
        with open('output/coord_align_result.json', encoding='utf-8') as f:
            align = json.load(f)
        bc = align['bsmnt_clip']
    except Exception:
        bc = [552082, -1376738, 712082, -1216738]

    print(f'\n[기둥 추출]')
    dong_cols = dedup(extract_columns(msp_dong, dong_clip))
    pkg_cols = dedup(extract_columns(msp_pkg, bc))
    print(f'  DONG B2F: {len(dong_cols)}개')
    print(f'  PKG 101동: {len(pkg_cols)}개')

    # 매칭
    print(f'\n[매칭 검증] tol=300mm')
    matched = match_columns(pkg_cols, dong_cols, TX, TY, match_tol=300)
    n_matched = len(matched)
    n_pkg = len(pkg_cols)
    match_rate = n_matched / n_pkg * 100 if n_pkg > 0 else 0

    print(f'  매칭: {n_matched}/{n_pkg} ({match_rate:.1f}%)')

    # 오차 통계
    if matched:
        errors = [m['error_mm'] for m in matched]
        errors_sorted = sorted(errors)
        e_min = min(errors)
        e_median = errors_sorted[len(errors_sorted) // 2]
        e_max = max(errors)
        e_mean = sum(errors) / len(errors)
        e_std = (sum((e - e_mean) ** 2 for e in errors) / len(errors)) ** 0.5

        n_pass = sum(1 for e in errors if e < PASS_THRESHOLD_MM)
        n_fail = len(errors) - n_pass

        print(f'\n  오차 통계:')
        print(f'    min={e_min:.1f}mm, median={e_median:.1f}mm, max={e_max:.1f}mm')
        print(f'    mean={e_mean:.1f}mm, std={e_std:.1f}mm')
        print(f'    < {PASS_THRESHOLD_MM}mm: {n_pass}/{len(errors)}개')
        print(f'    >= {PASS_THRESHOLD_MM}mm: {n_fail}/{len(errors)}개')

        # TX, TY 재계산 검증
        tx_from_match = [m['dong'][0] - m['pkg'][0] for m in matched]
        ty_from_match = [m['dong'][1] - m['pkg'][1] for m in matched]
        tx_calc = sum(tx_from_match) / len(tx_from_match)
        ty_calc = sum(ty_from_match) / len(ty_from_match)
        tx_std = (sum((v - tx_calc) ** 2 for v in tx_from_match) / len(tx_from_match)) ** 0.5
        ty_std = (sum((v - ty_calc) ** 2 for v in ty_from_match) / len(ty_from_match)) ** 0.5

        print(f'\n  TX 재계산: {tx_calc:.1f} (std={tx_std:.1f}, 설정값={TX})')
        print(f'  TY 재계산: {ty_calc:.1f} (std={ty_std:.1f}, 설정값={TY})')

        # PASS/FAIL 판정
        # 조건 1: 매칭률 > 70%
        # 조건 2: 오차 median < PASS_THRESHOLD_MM
        # 조건 3: TX/TY 재계산값이 설정값과 500mm 이내
        cond1 = match_rate > 70
        cond2 = e_median < PASS_THRESHOLD_MM
        cond3 = abs(tx_calc - TX) < 500 and abs(ty_calc - TY) < 500

        reasons = []
        if not cond1:
            reasons.append(f'매칭률 {match_rate:.1f}% < 70%')
        if not cond2:
            reasons.append(f'오차 중위값 {e_median:.1f}mm >= {PASS_THRESHOLD_MM}mm')
        if not cond3:
            reasons.append(f'TX/TY 재계산 편차 크다: ΔTX={tx_calc-TX:.0f}, ΔTY={ty_calc-TY:.0f}')

        passed = cond1 and cond2 and cond3

        print(f'\n  조건 1 (매칭률>70%): {"PASS" if cond1 else "FAIL"}')
        print(f'  조건 2 (중위값<{PASS_THRESHOLD_MM}mm): {"PASS" if cond2 else "FAIL"}')
        print(f'  조건 3 (TX/TY 재계산 일치): {"PASS" if cond3 else "FAIL"}')

        print(f'\n  상위 매칭 10쌍:')
        for m in sorted(matched, key=lambda v: v['error_mm'])[:10]:
            print(f'    PKG{m["pkg"]} + T -> {m["pkg_unified"]} ~ DONG{m["dong"]} '
                  f'err={m["error_mm"]}mm')

    else:
        passed = False
        reasons = ['매칭 쌍 0개']
        e_median = float('inf')
        e_max = float('inf')

    # TZ 검증 (도면 텍스트에서 확인된 값)
    tz_b2f_expected = -9050
    tz_b1f_expected = -5600
    tz_b2f_ok = TZ_B2F == tz_b2f_expected
    tz_b1f_ok = TZ_B1F == tz_b1f_expected

    print(f'\n[TZ 검증]')
    print(f'  TZ_B2F={TZ_B2F} (기대={tz_b2f_expected}): {"PASS" if tz_b2f_ok else "FAIL"}')
    print(f'  TZ_B1F={TZ_B1F} (기대={tz_b1f_expected}): {"PASS" if tz_b1f_ok else "FAIL"}')

    if not tz_b2f_ok:
        reasons.append(f'TZ_B2F={TZ_B2F} != {tz_b2f_expected}')
    if not tz_b1f_ok:
        reasons.append(f'TZ_B1F={TZ_B1F} != {tz_b1f_expected}')

    overall_pass = passed and tz_b2f_ok and tz_b1f_ok

    print(f'\n{"="*60}')
    if overall_pass:
        print(f'[결과] PASS')
        print(f'  TX={TX}mm, TY={TY}mm — 검증 완료')
        print(f'  매칭 {n_matched}/{n_pkg} ({match_rate:.1f}%), 오차 중위값={e_median:.1f}mm')
    else:
        print(f'[결과] FAIL')
        for r in reasons:
            print(f'  이유: {r}')
    print(f'{"="*60}')
    print(f'완료 ({time.time()-t0:.1f}s)')

    return overall_pass


if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
