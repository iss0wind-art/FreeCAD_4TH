import sys
from pathlib import Path
sys.path.insert(0, '.')

import ezdxf
from core.v2.inspect.meta_pipeline import inspect
from core.v2.extract.extract_pipeline import extract_all_members

def main():
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    
    # 기둥 4개 (S-COL 레이어, 600x600 LWPOLYLINE)
    for cx, cy in [(0, 0), (6000, 0), (0, 8000), (6000, 8000)]:
        msp.add_lwpolyline(
            [(cx - 300, cy - 300), (cx + 300, cy - 300),
             (cx + 300, cy + 300), (cx - 300, cy + 300)],
            dxfattribs={"layer": "S-COL"},
            close=True,
        )

    doc.saveas('test_col.dxf')
    meta = inspect(Path('test_col.dxf'))
    res = extract_all_members(meta)
    
    print('Sheets:', len(meta.sheets))
    if meta.sheets:
        print('Sheet bbox:', meta.sheets[0].bbox)
    print('Columns extracted:', len(res.columns))

if __name__ == '__main__':
    main()
