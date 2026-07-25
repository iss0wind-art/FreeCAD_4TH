import os, sys, ezdxf
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.pc_layer_adapter import RawEntity, classify_entities, PCKind

DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"

SHEETS = {
    'B1': {'sw': (877250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0},
}

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
    doc = ezdxf.readfile(DXF, encoding='cp949')
    msp = doc.modelspace()
    
    sheet = SHEETS['B1']
    sw = sheet['sw']; w = sheet['w']; h = sheet['h']
    ix0, iy0 = sw[0] + w * 0.02, sw[1] + h * 0.02
    ix1, iy1 = sw[0] + w * 0.98, sw[1] + h * 0.98
    
    raws = []
    raw_meta = []
    eid = 0
    
    # 1. iter_all과 영역 필터링 검사
    total_scanned = 0
    column_layer_scanned = 0
    column_layer_passed = 0
    
    for e in iter_all(msp):
        total_scanned += 1
        try:
            ly = e.dxf.layer
        except Exception:
            continue
            
        if ly == '00_COLUMN':
            column_layer_scanned += 1
            
        et = e.dxftype()
        if et == 'LINE':
            try:
                p = e.dxf.start
                if ix0 <= p.x <= ix1 and iy0 <= p.y <= iy1:
                    raws.append(RawEntity(entity_id=eid, layer=ly, geometry_kind=et))
                    raw_meta.append((eid, e, et, ly))
                    if ly == '00_COLUMN':
                        column_layer_passed += 1
                    eid += 1
            except Exception:
                pass
                
    print(f"Total scanned via iter_all: {total_scanned}")
    print(f"Total '00_COLUMN' layer entities scanned: {column_layer_scanned}")
    print(f"Total '00_COLUMN' layer LINEs passed spatial filter: {column_layer_passed}")
    print(f"Collected total raw entities for B1: {len(raw_meta)}")
    
    # Classification
    classified_pc = classify_entities(raws)
    pc_kind_by_id = {c.entity_id: c.kind for c in classified_pc}
    
    col_lines_count = 0
    for eid, e, et, ly in raw_meta:
        if et != 'LINE':
            continue
        if pc_kind_by_id.get(eid) != PCKind.NON_PC:
            continue
        if 'COL' in ly.upper() or '기둥' in ly.upper():
            col_lines_count += 1
            
    print(f"NON-PC 'COL' LINEs count: {col_lines_count}")

if __name__ == '__main__':
    main()
