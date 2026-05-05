"""
3개 벽체 일람표 DXF에서 모든 OLE2FRAME 일괄 추출

도면당 OLE 수십~수백 개 → 도엽별 데이터 모두 확보
"""

import os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ezdxf
import olefile
import io

DXF_FILES = [
    r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-311~359 101~105동 벽체 일람표.dxf",
    r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-361~406 106~110동 벽체 일람표.dxf",
    r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-411~463 111~116동 벽체 일람표.dxf",
]

OUT_DIR = r"d:/Git/FreeCAD_4TH/tmp_analysis/ole_all"
os.makedirs(OUT_DIR, exist_ok=True)

OLE2_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
ZIP_MAGIC = b'PK\x03\x04'

def extract_xlsx_from_ole(ole_bin, out_path_base):
    """AutoCAD OLE 컨테이너 → 내부 OLE2/ZIP magic 검색 → xlsx 저장"""
    try:
        # 1) OLE2 magic 검색
        ole2_pos = ole_bin.find(OLE2_MAGIC)
        if ole2_pos >= 0:
            clean = ole_bin[ole2_pos:]
            if olefile.isOleFile(io.BytesIO(clean)):
                ole = olefile.OleFileIO(io.BytesIO(clean))
                if ole.exists('Package'):
                    with ole.openstream('Package') as s:
                        data = s.read()
                    if data[:2] == b'PK':
                        out_path = out_path_base + '.xlsx'
                        with open(out_path, 'wb') as f:
                            f.write(data)
                        return out_path
                    elif data[:4] == OLE2_MAGIC[:4]:
                        out_path = out_path_base + '.xls'
                        with open(out_path, 'wb') as f:
                            f.write(data)
                        return out_path
        # 2) 직접 ZIP magic 검색 (xlsx)
        zip_pos = ole_bin.find(ZIP_MAGIC)
        if zip_pos >= 0:
            out_path = out_path_base + '.xlsx'
            with open(out_path, 'wb') as f:
                f.write(ole_bin[zip_pos:])
            return out_path
        return None
    except Exception as ex:
        return None

for dxf_path in DXF_FILES:
    if not os.path.exists(dxf_path):
        print(f"[건너뜀] {dxf_path}")
        continue
    base = os.path.splitext(os.path.basename(dxf_path))[0]
    print(f"\n[처리] {base} ({os.path.getsize(dxf_path)/1024/1024:.1f} MB)")

    doc = ezdxf.readfile(dxf_path, encoding='cp949')
    msp = doc.modelspace()

    ole_count = 0
    success = 0
    for e in msp.query('OLE2FRAME'):
        ole_count += 1
        try:
            bin_data = e.binary_data()
        except Exception:
            continue
        if not bin_data:
            continue
        out_base = os.path.join(OUT_DIR, f"{base}_ole{ole_count}")
        result = extract_xlsx_from_ole(bin_data, out_base)
        if result:
            success += 1

    print(f"  OLE 발견: {ole_count}, 추출 성공: {success}")

print(f"\n[저장] {OUT_DIR}")
