"""
DWG → DXF 일괄 변환 (ODA File Converter)

방부장 친히 ODA File Converter 설치 완료 (2026-05-05).
이천이 175장 일괄 자동 변환.
"""

import os
import sys
import time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ODA 경로 명시 (버전 폴더 포함)
ODA_PATH = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"

from ezdxf.addons import odafc
odafc.win_exec_path = ODA_PATH  # 직접 설정

SOURCE_DIRS = [
    (r"D:\06.3지국 전용방\01. 설계도면\01. 건축",          "01_건축"),
    (r"D:\06.3지국 전용방\01. 설계도면\02. 구조",          "02_구조"),
    (r"D:\06.3지국 전용방\01. 설계도면\02. 구조 260121",  "02_구조_260121"),
]
OUT_BASE = r"D:\06.3지국 전용방\01. 설계도면\dxf_out"

import subprocess

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

        # 이전 변환 결과 카운트
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
        print(f"  → {new_count}/{dwg_count}장 변환 ({elapsed:.0f}초)")

    print(f"\n{'='*50}")
    print(f"전체 변환: {total_out}/{total_in}장")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
