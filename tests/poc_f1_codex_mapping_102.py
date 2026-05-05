"""
F-1 + Codex 매핑 PoC — 셋째 호미: 익명 → 식별
=================================================

본영 골격 (core/codex_instance_mapper.py) + F-1 anchor (코어 #1).

50점 회고 §실패 1 (데이터-모델 단절) 직격 해소 PoC.

[흐름]
  1) 9도엽 합본 로드
  2) S30-022 도엽 (B1F 정상) 기둥 후보 박스 추출 (LWPOLYLINE closed, W·H 400~3000)
  3) F-1 anchor (코어 #1 SW=(73040, 52178)) 적용 → 정렬 좌표
  4) BoxInstance 생성 (source_hint='101~112동', floor_hint=-1)
  5) load_codex + map_instances → 식별 매핑
  6) 결과 박제 (정직 — 매칭 성공/실패 모두)

실행: "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_f1_codex_mapping_102.py
"""
import os, sys, json, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
from core.f1_anchor_aligner import EVAnchor, F1Aligner
from core.codex_instance_mapper import (
    BoxInstance, load_codex, map_instances, report_markdown, save_mappings,
)

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-021~029-102동 구조평면도.dxf"
CODEX = "output/codex_columns_unified.json"
OUT_JSON = "output/f1_codex_mapping_102_S30-022.json"
OUT_MD = "output/f1_codex_mapping_102_S30-022.md"

TARGET_SHEET = 'S30-022'  # B1F 정상 도엽
SOURCE_HINT = '101~112동'  # 102동의 기둥 일람표 출처
FLOOR_HINT = -1  # B1F


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


def extract_column_boxes(msp, sheet_id, sx, sy, sheet_w, sheet_h,
                         w_min=400, w_max=3000, inset=0.05):
    """기둥 후보 폐합 사각형 추출.

    조건:
      - LWPOLYLINE closed=True
      - vertex 4~6 (사각형 약간 허용)
      - W·H 400~3000mm (codex 91종 단면 범위 + 여유)
      - 도엽 inset 안쪽
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
        cx_abs = sum(p[0] for p in pts) / len(pts)
        cy_abs = sum(p[1] for p in pts) / len(pts)
        if not (ix0 <= cx_abs <= ix1 and iy0 <= cy_abs <= iy1):
            continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        w, h = xmax - xmin, ymax - ymin
        if not (w_min <= w <= w_max and w_min <= h <= w_max):
            continue
        boxes.append({
            'cx_abs': cx_abs, 'cy_abs': cy_abs,
            'w': w, 'h': h,
            'box_abs': (xmin, ymin, xmax, ymax),
        })
    return boxes


def main():
    print(f'[도면] {DXF}')
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()

    # 1. 도엽 표제
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
    if TARGET_SHEET not in sheets:
        print(f'[FAIL] {TARGET_SHEET} 표제 없음')
        return

    sx, sy = sheets[TARGET_SHEET]
    sheet_w, sheet_h = 126000, 178200
    print(f'[도엽 {TARGET_SHEET}] 표제 ({sx:.0f}, {sy:.0f})')

    # 2. 기둥 후보 박스 추출
    boxes = extract_column_boxes(msp, TARGET_SHEET, sx, sy, sheet_w, sheet_h)
    print(f'[기둥 후보 박스] {len(boxes)}개')
    # 박스 사이즈 분포 미리보기
    if boxes:
        ws = sorted(b['w'] for b in boxes)
        hs = sorted(b['h'] for b in boxes)
        print(f'  W 분포: min={ws[0]:.0f} median={ws[len(ws)//2]:.0f} max={ws[-1]:.0f}')
        print(f'  H 분포: min={hs[0]:.0f} median={hs[len(hs)//2]:.0f} max={hs[-1]:.0f}')

    # 3. F-1 anchor 적용 (코어 #1 SW=(73040, 52178) — 정규화 좌표)
    # 도엽 표제(sx, sy)를 더해 절대 좌표 anchor 만들기
    core_sw_norm = (73040.0, 52178.0)  # 정규화 좌표 (둘째 호미 결과)
    core_sw_abs = (sx + core_sw_norm[0], sy + core_sw_norm[1])
    anchor = EVAnchor(
        ev_box=(core_sw_abs[0], core_sw_abs[1],
                core_sw_abs[0] + 4307, core_sw_abs[1] + 4860),
        sw_corner=core_sw_abs,
        dong='102',
        floor=FLOOR_HINT,
        sheet_id=TARGET_SHEET,
        confidence=0.85,
    )
    aligner = F1Aligner(anchor)
    print(f'[F-1 anchor] 절대 SW=({core_sw_abs[0]:.0f}, {core_sw_abs[1]:.0f})')

    # 박스 좌표 정렬
    for b in boxes:
        x0, y0 = aligner.to_aligned((b['box_abs'][0], b['box_abs'][1]))
        x1, y1 = aligner.to_aligned((b['box_abs'][2], b['box_abs'][3]))
        b['box_aligned'] = (x0, y0, x1, y1)
        cx, cy = aligner.to_aligned((b['cx_abs'], b['cy_abs']))
        b['cx_aligned'] = cx
        b['cy_aligned'] = cy

    # 4. BoxInstance 생성
    instances = []
    for i, b in enumerate(boxes):
        instances.append(BoxInstance(
            box_id=f'102_{TARGET_SHEET}_col_{i:03d}',
            width=b['w'], height=b['h'],
            label=None,
            source_hint=SOURCE_HINT,
            floor_hint=FLOOR_HINT,
        ))

    # 5. codex 로드 + 매핑
    codex = load_codex(CODEX)
    print(f'[codex] {len(codex)}종 로드')

    mappings, unmatched = map_instances(instances, codex)
    print(f'[매핑] 성공 {len(mappings)} / 실패 {len(unmatched)} '
          f'(매칭률 {100*len(mappings)/(len(instances) or 1):.1f}%)')

    # 매핑 방법별 분포
    by_method = {}
    for m in mappings:
        by_method[m.method] = by_method.get(m.method, 0) + 1
    print(f'  방법별:')
    for k, v in sorted(by_method.items(), key=lambda x: -x[1]):
        print(f'    {k}: {v}')

    # 매핑 symbol별 분포
    by_symbol = {}
    for m in mappings:
        by_symbol[m.matched_symbol] = by_symbol.get(m.matched_symbol, 0) + 1
    print(f'  symbol별 (top 10):')
    for k, v in sorted(by_symbol.items(), key=lambda x: -x[1])[:10]:
        print(f'    {k}: {v}')

    # 6. 박제
    os.makedirs('output', exist_ok=True)
    save_mappings(mappings, unmatched, OUT_JSON)

    # 추가 메타: 정렬 좌표
    with open(OUT_JSON, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    json_data['anchor'] = {
        'sw_abs': list(core_sw_abs),
        'sw_norm': list(core_sw_norm),
        'sheet_id': TARGET_SHEET,
        'dong': '102',
        'floor': FLOOR_HINT,
    }
    json_data['box_geometry'] = [
        {
            'box_id': f'102_{TARGET_SHEET}_col_{i:03d}',
            'w': b['w'], 'h': b['h'],
            'cx_aligned': b['cx_aligned'], 'cy_aligned': b['cy_aligned'],
            'box_aligned': list(b['box_aligned']),
        }
        for i, b in enumerate(boxes)
    ]
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    md = report_markdown(mappings, unmatched)
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write(f'# F-1 + Codex 매핑 — 102동 {TARGET_SHEET} (B1F)\n\n')
        f.write(f'> 셋째 호미: 익명 → 식별. F-1 anchor 적용 + codex 91종 단면 매핑.\n\n')
        f.write(f'- 도엽: {TARGET_SHEET} (정규화 좌표계)\n')
        f.write(f'- F-1 anchor SW (norm): {core_sw_norm}\n')
        f.write(f'- 추출 박스: {len(boxes)}개\n')
        f.write(f'- codex 후보: {len(codex)}종\n\n')
        f.write(md)

    print(f'\n[박제] {OUT_JSON}')
    print(f'[박제] {OUT_MD}')


if __name__ == '__main__':
    main()
