"""101동 구조평면도 진단 — 도엽 SW + 도엽 식별 TEXT."""
import sys, re, time
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import ezdxf

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"


def iter_all(c, d=0, m=8):
    if d > m: return
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

    sheet_pat = re.compile(r'^S30-(00[1-9]|010)$')
    sheets = {}
    floor_pat = re.compile(r'(B[12]F|지하\s*[12]\s*층|1F|2F|3F|4F|5F|6F|지붕|PIT)')
    floor_text = []
    big_boxes = []
    type_count = Counter()

    for e in iter_all(msp):
        type_count[e.dxftype()] += 1
        if e.dxftype() in ('TEXT', 'MTEXT'):
            try:
                txt = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip()
                pos = e.dxf.insert
                m = sheet_pat.match(txt)
                if m:
                    sheets[txt] = (pos.x, pos.y)
                if floor_pat.search(txt) and len(txt) <= 20:
                    floor_text.append((txt, pos.x, pos.y))
            except Exception:
                pass
        if e.dxftype() == 'LWPOLYLINE':
            try:
                if not e.is_closed: continue
                pts = [(x,y) for x,y,*_ in e.get_points()]
                if not (4<=len(pts)<=6): continue
                xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
                w=max(xs)-min(xs); h=max(ys)-min(ys)
                if w>50000 and h>50000:
                    big_boxes.append((min(xs), min(ys), w, h, e.dxf.layer))
            except Exception:
                pass

    print(f'\n[엔티티 분포]')
    for t, c in type_count.most_common(8):
        print(f'  {t:15s} {c}')

    print(f'\n[도엽 식별 TEXT S30-XXX] {len(sheets)}건')
    for sid in sorted(sheets):
        x, y = sheets[sid]
        print(f'  {sid}  ({x:.0f}, {y:.0f})')

    print(f'\n[층 식별 TEXT 후보] {len(floor_text)}건 (상위 30)')
    seen = set()
    for tx, px, py in floor_text:
        key = tx[:15]
        if key in seen: continue
        seen.add(key)
        print(f'  "{tx[:30]}"  ({px:.0f}, {py:.0f})')
        if len(seen) >= 30: break

    print(f'\n[큰 도엽 박스 50m+] {len(big_boxes)}건 (상위 15, X 정렬)')
    for sx, sy, w, h, ly in sorted(big_boxes)[:15]:
        print(f'  sw=({sx:.0f}, {sy:.0f})  size={w:.0f}x{h:.0f}  layer={ly}')


if __name__ == '__main__':
    main()
