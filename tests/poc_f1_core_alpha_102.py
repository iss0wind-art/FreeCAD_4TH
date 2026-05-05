"""
F-1 코어 α 검출 PoC — 102동 9도엽 (둘째 호미)
=================================================

본영 골격 (core/f1_core_cluster.py) + 이천 검출 함수 결합.
첫 호미(F-2 폴백)의 ④ 게이트 미통과를 둘째 호미(α 코어 클러스터링)으로 해소 시도.

이천 책무 (extract_closed_rectangles 채움):
  - LWPOLYLINE closed=True + 사각형 vertex
  - 도엽 영역 안 (within_box) 필터
  - 정규화 좌표 (도엽 표제 빼기) SheetBox 반환

본영 책무 (자동 호출):
  - infer_floor_kind (γ — BoundBox로 1F·옥상 자동 분류)
  - detect_core_by_clustering (α — 7+ 도엽 같은 위치 작은 사각형 군집)
  - verify_multi_sheet_alignment (④ 게이트)

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_f1_core_alpha_102.py
"""
import os, sys, json, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
from core.f1_anchor_aligner import EVAnchor, F1Aligner, verify_multi_sheet_alignment
from core.f1_core_cluster import (
    SheetBox, infer_floor_kind, filter_normal_sheets,
    detect_core_by_clustering,
)

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-021~029-102동 구조평면도.dxf"
OUT = "output/f1_core_alpha_102.json"


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


def extract_closed_rectangles_in_sheet(msp, sheet_id, sx, sy,
                                       sheet_w, sheet_h, inset=0.05):
    """도엽 안 폐합 사각형 추출 (정규화 좌표 SheetBox).

    이천 자율 구현 — extract_closed_rectangles 충족.
    조건:
      - LWPOLYLINE closed=True
      - vertex 4~6 (사각형 약간 허용)
      - 도엽 inset 안쪽 (도면틀 제외)
    """
    ix0, iy0 = sx + sheet_w * inset, sy + sheet_h * inset
    ix1, iy1 = sx + sheet_w * (1 - inset), sy + sheet_h * (1 - inset)

    boxes = []
    for e in iter_all(msp):
        if e.dxftype() != 'LWPOLYLINE':
            continue
        try:
            if not e.is_closed:
                continue
            pts = [(x, y) for x, y, *_ in e.get_points()]
            if not (4 <= len(pts) <= 6):
                continue
        except Exception:
            continue
        # 도엽 영역 안 (중심점)
        cx_abs = sum(p[0] for p in pts) / len(pts)
        cy_abs = sum(p[1] for p in pts) / len(pts)
        if not (ix0 <= cx_abs <= ix1 and iy0 <= cy_abs <= iy1):
            continue
        # BoundBox
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        w, h = xmax - xmin, ymax - ymin
        if w < 100 or h < 100:  # 노이즈 제거
            continue
        # 정규화 좌표
        nxmin, nymin = xmin - sx, ymin - sy
        nxmax, nymax = xmax - sx, ymax - sy
        ncx, ncy = (nxmin + nxmax) / 2, (nymin + nymax) / 2
        boxes.append(SheetBox(
            sheet_id=sheet_id,
            cx=ncx, cy=ncy, w=w, h=h,
            raw_box=(nxmin, nymin, nxmax, nymax),
        ))
    return boxes


def detect_body_bbox(msp, sx, sy, sheet_w, sheet_h, inset=0.05):
    """γ 추론용 본체 BoundBox (첫 PoC 재사용)."""
    ix0, iy0 = sx + sheet_w * inset, sy + sheet_h * inset
    ix1, iy1 = sx + sheet_w * (1 - inset), sy + sheet_h * (1 - inset)
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
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def main():
    print(f'[도면] {DXF}')
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()

    # 도엽 표제
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
    print(f'[도엽] {len(sheets)}장')
    sheet_w, sheet_h = 126000, 178200

    # γ — 본체 BoundBox + 층 추론
    sheet_body_boxes = {}
    for sid, (sx, sy) in sheets.items():
        bb = detect_body_bbox(msp, sx, sy, sheet_w, sheet_h)
        if bb:
            sheet_body_boxes[sid] = (bb[2] - bb[0], bb[3] - bb[1])

    inferences = infer_floor_kind(sheet_body_boxes)
    print('[γ 층 추론]')
    for inf in sorted(inferences, key=lambda x: x.sheet_id):
        print(f'  {inf.sheet_id} W={inf.body_w:>7.0f} H={inf.body_h:>7.0f} → {inf.inferred_kind}')
    normal_sheets = filter_normal_sheets(inferences)
    print(f'\n[정상 평면 {len(normal_sheets)}장] {normal_sheets}')

    # α — 폐합 사각형 추출 (정상 도엽만)
    print('\n[α 폐합 사각형 추출]')
    per_sheet_boxes = {}
    for sid in normal_sheets:
        sx, sy = sheets[sid]
        per_sheet_boxes[sid] = extract_closed_rectangles_in_sheet(
            msp, sid, sx, sy, sheet_w, sheet_h
        )
        print(f'  [{sid}] 폐합 사각형 {len(per_sheet_boxes[sid])}개')

    # α 클러스터링
    min_member = min(7, len(normal_sheets))
    if min_member < 2:
        print(f'\n[FAIL] 정상 도엽 < 2 — 클러스터링 불가')
        return

    print(f'\n[α 클러스터링] min_member_sheets={min_member}')
    candidates = detect_core_by_clustering(
        per_sheet_boxes,
        min_member_sheets=min_member,
    )
    print(f'  코어 후보: {len(candidates)}개')
    for i, c in enumerate(candidates[:5]):
        print(f'  #{i+1}: cx={c.representative_cx:>7.0f} cy={c.representative_cy:>7.0f} '
              f'W={c.representative_w:>5.0f} H={c.representative_h:>5.0f} '
              f'멤버={c.member_count}장 std=({c.position_std_x:>4.0f},{c.position_std_y:>4.0f}) '
              f'conf={c.confidence:.2f}')

    # ④ 게이트 검증 — 최선 코어 후보로
    if candidates:
        best = candidates[0]
        anchors = []
        for sid in best.member_sheets:
            sbox_list = per_sheet_boxes[sid]
            closest = min(
                sbox_list,
                key=lambda b: abs(b.cx - best.representative_cx)
                + abs(b.cy - best.representative_cy),
            )
            anchors.append(EVAnchor(
                ev_box=closest.raw_box,
                sw_corner=(closest.raw_box[0], closest.raw_box[1]),
                dong='102',
                floor=int(sid.split('-')[1]) - 23,
                sheet_id=sid,
                confidence=best.confidence,
            ))

        print(f'\n[④ 게이트 검증 — best 코어 후보 #{1}]')
        gate_results = {}
        for tol in [50, 100, 200, 500]:
            passed, warnings = verify_multi_sheet_alignment(
                anchors, dong='102', tol_mm=tol
            )
            verdict = 'PASS' if passed else 'FAIL'
            print(f'  tol={tol:>4}mm  {verdict}')
            if not passed and tol == 100:
                for w in warnings[:5]:
                    print(f'    {w}')
            gate_results[f'tol_{tol}mm'] = {'passed': passed, 'warnings': warnings}
    else:
        gate_results = {}

    # 박제
    os.makedirs('output', exist_ok=True)
    out = {
        'dong': '102',
        'gamma_inferences': [
            {'sheet_id': i.sheet_id, 'body_w': i.body_w, 'body_h': i.body_h,
             'kind': i.inferred_kind} for i in inferences
        ],
        'normal_sheets': normal_sheets,
        'box_counts': {sid: len(b) for sid, b in per_sheet_boxes.items()},
        'core_candidates': [
            {
                'cx': c.representative_cx, 'cy': c.representative_cy,
                'w': c.representative_w, 'h': c.representative_h,
                'sw_corner': list(c.sw_corner),
                'member_sheets': c.member_sheets,
                'std_x': c.position_std_x, 'std_y': c.position_std_y,
                'confidence': c.confidence,
            } for c in candidates
        ],
        'gate_4_results': gate_results,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n[박제] {OUT}')


if __name__ == '__main__':
    main()
