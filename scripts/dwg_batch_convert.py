"""
DWG → DXF 일괄 변환 (AutoCAD accoreconsole)

부산 에코델타 24BL 강역의 모든 DWG 도면을 DXF로 일괄 변환.

원칙:
- 한 장 한 장 살핀다 (방부장 친명)
- 변환 실패 시 즉시 박제 (이상치 통계)
- 진행 상황 실시간 출력
"""

import os
import sys
import subprocess
from pathlib import Path

ACCORE = r"C:\Program Files\Autodesk\AutoCAD 2024\accoreconsole.exe"
SOURCE_DIRS = [
    r"D:\06.3지국 전용방\01. 설계도면\01. 건축",
    r"D:\06.3지국 전용방\01. 설계도면\02. 구조",
    r"D:\06.3지국 전용방\01. 설계도면\02. 구조 260121",
]
OUT_BASE = r"D:\06.3지국 전용방\01. 설계도면\dxf_out"

SCR_TEMPLATE = """FILEDIA 0
-DXFOUT
{out_path}
V
2018
16
FILEDIA 1
QUIT
Y
"""

def make_scr(scr_path, dxf_path):
    with open(scr_path, 'w', encoding='cp949') as f:
        f.write(SCR_TEMPLATE.format(out_path=dxf_path))

def convert_one(dwg_path, dxf_path, scr_path, timeout=180):
    make_scr(scr_path, dxf_path)
    try:
        result = subprocess.run(
            [ACCORE, '/i', dwg_path, '/s', scr_path],
            capture_output=True, timeout=timeout
        )
        return os.path.exists(dxf_path)
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def main():
    os.makedirs(OUT_BASE, exist_ok=True)
    scr_tmp = os.path.join(OUT_BASE, "_convert.scr")

    # 모든 DWG 수집
    targets = []
    for src in SOURCE_DIRS:
        sub_name = os.path.basename(src)
        for f in os.listdir(src):
            if f.lower().endswith('.dwg'):
                src_path = os.path.join(src, f)
                base = os.path.splitext(f)[0]
                # 출력 디렉터리: dxf_out/[01. 건축, 02. 구조, ...]/
                out_subdir = os.path.join(OUT_BASE, sub_name)
                os.makedirs(out_subdir, exist_ok=True)
                dxf_path = os.path.join(out_subdir, base + '.dxf')
                targets.append((src_path, dxf_path))

    print(f"[총 대상] DWG {len(targets)}장")

    success = 0
    failed = []
    for i, (dwg, dxf) in enumerate(targets, 1):
        if os.path.exists(dxf):
            success += 1
            print(f"  [{i}/{len(targets)}] SKIP (이미 있음): {os.path.basename(dwg)}")
            continue
        ok = convert_one(dwg, dxf, scr_tmp)
        status = "OK" if ok else "FAIL"
        print(f"  [{i}/{len(targets)}] {status}: {os.path.basename(dwg)}")
        if ok:
            success += 1
        else:
            failed.append(dwg)

    print(f"\n{'='*50}")
    print(f"변환 결과: {success}/{len(targets)} 성공")
    print(f"실패: {len(failed)}")
    if failed:
        print("실패 목록:")
        for f in failed[:20]:
            print(f"  - {os.path.basename(f)}")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
