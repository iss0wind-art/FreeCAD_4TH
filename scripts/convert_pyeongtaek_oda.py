"""
평택 고덕 DWG → DXF 일괄 변환 (ODA File Converter)
"""

import os
import sys
import time
import subprocess

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ODA_PATH = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"

BASE_DIR = r"D:\06.3지국 전용방\02. 평택 고덕\평택251022 허가 접수도서 CADS파일"
SOURCE_DIRS = []
if os.path.exists(BASE_DIR):
    for item in sorted(os.listdir(BASE_DIR)):
        item_path = os.path.join(BASE_DIR, item)
        if os.path.isdir(item_path):
            clean_name = item.replace(".", "_").replace(" ", "").replace(",", "_")
            SOURCE_DIRS.append((item_path, clean_name))

OUT_BASE = r"D:\06.3지국 전용방\02. 평택 고덕\dxf_out"

def convert_directory_oda(input_dir, output_dir, version="ACAD2018"):
    """ODA 디렉터리 일괄 변환 — 폴더 안 모든 DWG → DXF"""
    os.makedirs(output_dir, exist_ok=True)
    cmd = [
        ODA_PATH,
        input_dir,         # input folder
        output_dir,        # output folder
        version,           # output version
        "DXF",             # output format
        "0",               # recurse (0=no)
        "1",               # audit (1=yes)
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=3600)
    return result.returncode == 0

def main():
    os.makedirs(OUT_BASE, exist_ok=True)
    total_in = 0
    total_out = 0
    
    for src, sub_name in SOURCE_DIRS:
        if not os.path.isdir(src):
            print(f"[건너뜀] 입력 폴더 없음: {src}")
            continue
        out_subdir = os.path.join(OUT_BASE, sub_name)
        os.makedirs(out_subdir, exist_ok=True)

        before = len([f for f in os.listdir(out_subdir)
                      if f.lower().endswith('.dxf')]) if os.path.isdir(out_subdir) else 0

        dwg_count = len([f for f in os.listdir(src) if f.lower().endswith('.dwg')])
        total_in += dwg_count
        print(f"\n[변환 시작] {sub_name} ({dwg_count}장)")
        print(f"  입력: {src}")
        print(f"  출력: {out_subdir}")
        
        t0 = time.time()
        ok = convert_directory_oda(src, out_subdir)
        elapsed = time.time() - t0
        
        after = len([f for f in os.listdir(out_subdir)
                     if f.lower().endswith('.dxf')]) if os.path.isdir(out_subdir) else 0
        new_count = after - before
        total_out += new_count
        print(f"  → {new_count}/{dwg_count}장 변환 완료 ({elapsed:.1f}초)")

    print(f"\n{'='*50}")
    print(f"전체 변환 결과: {total_out}/{total_in}장 성공")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
