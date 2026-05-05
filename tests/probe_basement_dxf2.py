"""
지하주차장 통합 DXF 2차 진단 — 도엽 분리 정밀 채굴
====================================================

1차 진단 단서:
  - XREF 레이어 'XR지하2층평면도$0$...' → 지하 1·2층 분리 가능성
  - 도엽 프레임 18건 (대형 박스)
  - 한글 도엽 식별 TEXT 미캐치 — 패턴 재정비

2차 목표:
  1) 한글/영문 다양한 패턴으로 도엽/층 TEXT 채굴
  2) XREF 레이어 패턴 그룹화 (지하1층 / 지하2층)
  3) 큰 도엽 박스만 추려 정렬 (6개 정도?)
  4) 00_COLUMN 레이어 LWPOLYLINE 폐합 박스 통계 (기둥 후보 수)
  5) 00_BEAM 레이어 LINE 통계
"""
import os, sys, re, time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"


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


def main():
    t0 = time.time()
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    print(f'[로드] {time.time()-t0:.1f}s')

    # 1) 한글/영문 다양 패턴 도엽 텍스트
    floor_keywords = re.compile(
        r'(지하\s*[12]\s*층|지하주차장|B\s*[12]\s*F|B[12]F|地下|평면도|구조)',
        re.IGNORECASE
    )

    text_candidates = []  # (text, x, y, layer, height)
    layer_text_count = Counter()
    big_text = []  # 큰 글자 (도엽 제목 가능성)

    for e in iter_all(msp):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        try:
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            txt = (txt or '').strip()
            if not txt:
                continue
            pos = e.dxf.insert if hasattr(e.dxf, 'insert') else None
            px = pos.x if pos else 0
            py = pos.y if pos else 0
            ly = e.dxf.layer
            try:
                h = e.dxf.height if e.dxftype() == 'TEXT' else e.dxf.char_height
            except Exception:
                h = 0
            layer_text_count[ly] += 1
            if floor_keywords.search(txt):
                text_candidates.append((txt, px, py, ly, h))
            if h > 1000:  # 1m 이상 글자 — 도엽 제목
                big_text.append((txt, px, py, ly, h))
        except Exception:
            pass

    print(f'\n[한글/영문 도엽 키워드 매치] {len(text_candidates)}건')
    for tx, px, py, ly, h in text_candidates[:30]:
        print(f'  "{tx}"  ({px:.0f}, {py:.0f})  h={h:.0f}  layer={ly}')

    print(f'\n[큰 글자 (h>1000mm) — 도엽 제목 후보] {len(big_text)}건')
    for tx, px, py, ly, h in sorted(big_text, key=lambda x: -x[4])[:20]:
        print(f'  "{tx[:50]}"  ({px:.0f}, {py:.0f})  h={h:.0f}  layer={ly}')

    # 2) XREF 레이어 패턴 분석
    print('\n[XREF 레이어 분석]')
    xref_layers = [l.dxf.name for l in doc.layers if 'XR' in l.dxf.name or 'xr' in l.dxf.name]
    bf1 = [l for l in xref_layers if '지하1' in l or 'B1' in l.upper() or '1F' in l.upper()]
    bf2 = [l for l in xref_layers if '지하2' in l or 'B2' in l.upper() or '2F' in l.upper()]
    print(f'  XREF 레이어 총 {len(xref_layers)}개')
    print(f'  지하1층 패턴: {len(bf1)}개')
    for l in bf1[:5]:
        print(f'    {l}')
    print(f'  지하2층 패턴: {len(bf2)}개')
    for l in bf2[:5]:
        print(f'    {l}')

    # 3) 큰 도엽 박스만 추려 정렬
    big_boxes = []
    for e in iter_all(msp):
        if e.dxftype() != 'LWPOLYLINE':
            continue
        try:
            if not e.is_closed:
                continue
            pts = [(x, y) for x, y, *_ in e.get_points()]
            if not (4 <= len(pts) <= 6):
                continue
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            w = max(xs) - min(xs); h = max(ys) - min(ys)
            # 도엽 추정: 폭 400m+ × 높이 300m+
            if w > 400000 and h > 300000:
                big_boxes.append((min(xs), min(ys), w, h, e.dxf.layer))
        except Exception:
            pass

    print(f'\n[큰 도엽 박스 (400m+ × 300m+)] {len(big_boxes)}건')
    for sx, sy, w, h, ly in sorted(big_boxes):
        print(f'  sw=({sx:.0f}, {sy:.0f})  size={w:.0f}x{h:.0f}  layer={ly}')

    # 4) 00_COLUMN 레이어 LWPOLYLINE 폐합 박스 후보
    col_boxes = []
    for e in iter_all(msp):
        if e.dxftype() != 'LWPOLYLINE':
            continue
        try:
            if e.dxf.layer != '00_COLUMN':
                continue
            if not e.is_closed:
                continue
            pts = [(x, y) for x, y, *_ in e.get_points()]
            if not (4 <= len(pts) <= 6):
                continue
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            w = max(xs) - min(xs); h = max(ys) - min(ys)
            if 400 <= w <= 3000 and 400 <= h <= 3000:
                col_boxes.append((min(xs), min(ys), w, h))
        except Exception:
            pass
    print(f'\n[00_COLUMN 폐합 박스 (400~3000mm)] {len(col_boxes)}건')

    # 5) 00_BEAM 레이어 LINE 통계
    beam_lines = 0
    for e in iter_all(msp):
        if e.dxftype() != 'LINE':
            continue
        try:
            if e.dxf.layer == '00_BEAM':
                beam_lines += 1
        except Exception:
            pass
    print(f'\n[00_BEAM LINE] {beam_lines}건')

    print(f'\n[종결] 진단 {time.time()-t0:.1f}s')


if __name__ == '__main__':
    main()
