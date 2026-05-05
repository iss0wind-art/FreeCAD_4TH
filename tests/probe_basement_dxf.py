"""
지하주차장 통합 DXF 구조 자력 채굴 — B1·B2 도엽 분리 방식 진단
====================================================================

목적:
  1) TEXT 엔티티에서 'B1F'/'B2F' 또는 도엽 번호 위치 채굴
  2) 폐합 LWPOLYLINE 큰 박스 (도엽 프레임) 추출
  3) 레이어 목록 + 엔티티 분포
  4) 전체 BoundingBox

자수 보정: 본 진단은 본 PoC 시작 전 강역 학습. 코드 한 줄 안 빌고 자력.
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
    print(f'[도면] {DXF}')
    t0 = time.time()
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    print(f'[로드] {time.time()-t0:.1f}s')

    # 1) 레이어 목록
    layers = sorted(l.dxf.name for l in doc.layers)
    print(f'\n[레이어] {len(layers)}개')
    for l in layers[:40]:
        print(f'  {l}')
    if len(layers) > 40:
        print(f'  ... ({len(layers)-40} 더)')

    # 2) 엔티티 분포 + BoundingBox + TEXT 패턴
    type_count = Counter()
    layer_count = Counter()
    xs, ys = [], []
    text_floor = []   # 도엽 식별 텍스트 후보
    text_grid = []    # 격자 라벨 후보
    closed_polys = [] # 폐합 폴리라인 (도엽 박스 후보)

    floor_pat = re.compile(r'^\s*(B?[12]F|지하\s*[12]\s*층|지하주차장\s*[12])\s*$', re.IGNORECASE)
    sheet_pat = re.compile(r'^S\d{2}-\d{3}.*$')
    grid_pat  = re.compile(r'^[A-Z]\d?$|^\d{1,2}$')

    n = 0
    for e in iter_all(msp):
        n += 1
        t = e.dxftype()
        type_count[t] += 1
        try:
            layer_count[e.dxf.layer] += 1
        except Exception:
            pass

        if t == 'TEXT' or t == 'MTEXT':
            try:
                txt = e.dxf.text if t == 'TEXT' else e.text
                txt = (txt or '').strip()
                pos = e.dxf.insert if hasattr(e.dxf, 'insert') else None
                px = pos.x if pos else 0
                py = pos.y if pos else 0
                if floor_pat.match(txt):
                    text_floor.append((txt, px, py, e.dxf.layer))
                if sheet_pat.match(txt):
                    text_floor.append((txt, px, py, e.dxf.layer))
                if grid_pat.match(txt) and len(txt) <= 3:
                    text_grid.append((txt, px, py, e.dxf.layer))
                xs.append(px); ys.append(py)
            except Exception:
                pass

        if t == 'LWPOLYLINE':
            try:
                if e.is_closed:
                    pts = [(x, y) for x, y, *_ in e.get_points()]
                    if 4 <= len(pts) <= 6:
                        xs2 = [p[0] for p in pts]
                        ys2 = [p[1] for p in pts]
                        w = max(xs2) - min(xs2)
                        h = max(ys2) - min(ys2)
                        # 도엽 프레임 후보 (50m 이상)
                        if w > 50000 or h > 50000:
                            closed_polys.append((min(xs2), min(ys2), w, h, e.dxf.layer))
            except Exception:
                pass

        if t in ('LINE',):
            try:
                xs.append(e.dxf.start.x); ys.append(e.dxf.start.y)
                xs.append(e.dxf.end.x);   ys.append(e.dxf.end.y)
            except Exception:
                pass

    print(f'\n[엔티티 분포] 총 {n}')
    for t, c in type_count.most_common(15):
        print(f'  {t:15s} {c:>8d}')

    print(f'\n[레이어 상위 20]')
    for l, c in layer_count.most_common(20):
        print(f'  {l:40s} {c:>7d}')

    if xs and ys:
        print(f'\n[BoundingBox]')
        print(f'  X: {min(xs):.0f} ~ {max(xs):.0f}  ({max(xs)-min(xs):.0f}mm)')
        print(f'  Y: {min(ys):.0f} ~ {max(ys):.0f}  ({max(ys)-min(ys):.0f}mm)')

    print(f'\n[도엽/층 식별 TEXT] {len(text_floor)}건 (상위 30)')
    for tx, px, py, ly in text_floor[:30]:
        print(f'  "{tx}"  ({px:.0f}, {py:.0f})  layer={ly}')

    print(f'\n[격자 라벨 후보] {len(text_grid)}건 (상위 20)')
    for tx, px, py, ly in text_grid[:20]:
        print(f'  "{tx}"  ({px:.0f}, {py:.0f})  layer={ly}')

    print(f'\n[도엽 프레임 후보 (50m+)] {len(closed_polys)}건 (상위 15)')
    for sx, sy, w, h, ly in closed_polys[:15]:
        print(f'  sw=({sx:.0f}, {sy:.0f})  size={w:.0f}x{h:.0f}  layer={ly}')

    print(f'\n[종결] 진단 {time.time()-t0:.1f}s')


if __name__ == '__main__':
    main()
