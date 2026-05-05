"""
F-1 anchor PoC — 102동 9도엽 합본 (이천 자력 첫 호미)
=====================================================

본영 골격 (core/f1_anchor_aligner.py) + 이천 검출 함수 결합 첫 PoC.

본 도면 패턴 진단 결과:
  · TEXT a 후보 (E/V, EV, 엘리, 승강) 라벨: 직접 라벨 0건
  · 레이어 c 단서 (CORE, EV): 0건
  · INSERT 블록 단서: 0건 (외부참조 XR로 본체 봉인)
  · → F-2 폴백(d 휴리스틱) 전환: 도엽 본체 BoundBox SE 모서리

본영 알고리즘 조정 청 1건:
  · 9도엽 합본은 도엽 박스 격자 배치 → 절대 좌표 SE는 도엽마다 다름
  · 도엽 *정규화 좌표*(표제 빼기)에서 SE 추출해야 9도엽 정합성 검증 가능
  · 본 PoC는 정규화 좌표로 anchor 생성 (이천 자력 우회)

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_f1_anchor_102_9sheets.py
"""
import os, sys, json, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
from core.f1_anchor_aligner import EVAnchor, F1Aligner, verify_multi_sheet_alignment

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-021~029-102동 구조평면도.dxf"
OUT = "output/f1_anchor_102_9sheets.json"


def iter_all(container, depth=0, max_d=8):
    if depth > max_d:
        return
    for e in container:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), depth + 1, max_d)
            except Exception:
                pass
        else:
            yield e


def detect_body_bbox(msp, sx, sy, sheet_w=126000, sheet_h=178200, inset=0.05):
    """도엽 박스 안 본체(주거동) BoundBox 추출 (F-2 폴백).

    휴리스틱:
      1) 도엽 영역 안쪽 5% inset (도면틀 외곽 사각형 제외)
      2) LINE/LWPOLYLINE 좌표 수집
      3) BoundBox 반환
    """
    x0, y0 = sx, sy
    x1, y1 = sx + sheet_w, sy + sheet_h
    ix0 = x0 + sheet_w * inset
    iy0 = y0 + sheet_h * inset
    ix1 = x1 - sheet_w * inset
    iy1 = y1 - sheet_h * inset

    pts = []
    for e in iter_all(msp):
        if e.dxftype() == 'LINE':
            for p in (e.dxf.start, e.dxf.end):
                if ix0 <= p.x <= ix1 and iy0 <= p.y <= iy1:
                    pts.append((p.x, p.y))
        elif e.dxftype() == 'LWPOLYLINE':
            for x, y, *_ in e.get_points():
                if ix0 <= x <= ix1 and iy0 <= y <= iy1:
                    pts.append((x, y))

    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def main():
    print(f'[도면] {DXF}')
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()

    # 1. 도엽 표제 검출
    sheets = {}
    for e in iter_all(msp):
        if e.dxftype() == 'TEXT':
            try:
                t = e.dxf.text.strip()
                m = re.match(r'^S30-(02[1-9])$', t)
                if m:
                    sheets[t] = (e.dxf.insert.x, e.dxf.insert.y)
            except Exception:
                pass

    print(f'[도엽] {len(sheets)}장 검출')
    for sid, pos in sorted(sheets.items()):
        print(f'  {sid:10} 표제 ({pos[0]:.0f}, {pos[1]:.0f})')

    # 도엽 박스 크기 추정 (인접 표제 거리)
    xs_uniq = sorted(set(p[0] for p in sheets.values()))
    ys_uniq = sorted(set(p[1] for p in sheets.values()))
    sheet_w = (xs_uniq[1] - xs_uniq[0]) if len(xs_uniq) >= 2 else 126000
    # 세로 간격 (다른 행 표제 간 차이)
    if len(ys_uniq) >= 2:
        sheet_h = ys_uniq[-1] - ys_uniq[-2]
    else:
        sheet_h = 178200
    print(f'[도엽 박스] 가로={sheet_w:.0f}, 세로={sheet_h:.0f}')

    # 2. 각 도엽 anchor 생성 (정규화 좌표 = 표제 빼기)
    anchors = []
    for sid, (sx, sy) in sorted(sheets.items()):
        bbox_abs = detect_body_bbox(msp, sx, sy, sheet_w, sheet_h)
        if bbox_abs is None:
            print(f'  [SKIP] {sid} — 본체 BoundBox 검출 실패')
            continue

        # 도엽 정규화 (표제 좌하단 빼기)
        rel = (bbox_abs[0] - sx, bbox_abs[1] - sy,
               bbox_abs[2] - sx, bbox_abs[3] - sy)
        sw = (rel[0], rel[1])  # SW = (xmin, ymin) — 좌하단, 정규화 좌표

        sheet_num = int(sid.split('-')[1])
        # 가설: 021=B2, 022=B1, 023=1F, ..., 029=옥상 (검증 필요)
        floor_guess = sheet_num - 23  # 021=-2, 022=-1, 023=0=1F, 024=1=2F ...

        anchor = EVAnchor(
            ev_box=rel,
            sw_corner=sw,
            dong='102',
            floor=floor_guess,
            sheet_id=sid,
            confidence=0.5,  # F-2 폴백 — 신뢰도 낮춤
        )
        anchors.append(anchor)
        w = rel[2] - rel[0]
        h = rel[3] - rel[1]
        print(f'  [{sid}] floor={floor_guess:+d} body=({rel[0]:.0f},{rel[1]:.0f},{rel[2]:.0f},{rel[3]:.0f}) '
              f'W={w:.0f} H={h:.0f} SW={sw}')

    # 3. 9도엽 정합성 검증 (다양 tolerance)
    print()
    for tol in [50, 200, 500, 2000, 10000]:
        passed, warnings = verify_multi_sheet_alignment(anchors, dong='102', tol_mm=tol)
        verdict = 'PASS' if passed else 'FAIL'
        print(f'[검증 tol={tol:>5}mm] {verdict}')
        if not passed and tol == 50:
            for w in warnings[:5]:
                print(f'    {w}')

    # 4. 결과 박제
    os.makedirs('output', exist_ok=True)
    out = {
        'dong': '102',
        'sheet_count': len(anchors),
        'anchor_method': 'F-2 fallback (body BoundBox in normalized sheet coords)',
        'sheet_box': {'w': sheet_w, 'h': sheet_h},
        'anchors': [
            {
                'sheet_id': a.sheet_id,
                'floor_guess': a.floor,
                'ev_box': a.ev_box,
                'sw_corner': a.sw_corner,
                'confidence': a.confidence,
            }
            for a in anchors
        ],
        'verification': {
            f'tol_{t}mm': verify_multi_sheet_alignment(anchors, dong='102', tol_mm=t)
            for t in [50, 200, 500, 2000, 10000]
        },
    }
    # tuple → list 변환 (JSON 직렬화)
    out['verification'] = {k: {'passed': v[0], 'warnings': v[1]}
                           for k, v in out['verification'].items()}

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[박제] {OUT}')

    # 5. F1Aligner 변환 PoC — 첫 anchor로 v3 트림 결과 변환 시뮬
    if anchors:
        a0 = anchors[0]
        aligner = F1Aligner(a0)
        sample_pts = [a0.ev_box[:2], a0.ev_box[2:], a0.sw_corner]
        print(f'\n[F1Aligner PoC — anchor={a0.sheet_id}]')
        for pt in sample_pts:
            t = aligner.to_aligned(pt)
            print(f'  {pt} → aligned {t}')


if __name__ == '__main__':
    main()
