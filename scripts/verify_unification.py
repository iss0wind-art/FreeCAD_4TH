
import sys
import os
import ezdxf
import math

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.dxf_parser.coord_unifier import CoordUnifier
from core.dxf_parser.structural_extractor import StructuralExtractor

def verify():
    dong_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    pkg_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    
    print("--- Coordination Unification Verification ---")
    unifier = CoordUnifier()
    
    # 1. 도면 등록 (심볼 매칭 클러스터링 결과 기반 정밀 앵커)
    print("\n[Step 1] Registering Drawings with Precision Anchors...")
    # Dong Anchor: SW(149013, 2321258)
    unifier.add('dong', dong_path, dong='101', manual_anchor=(149013, 2321258))
    
    # PKG Anchor: Precision Adjusted (TX=-321970, TY=3621813)
    unifier.add('pkg', pkg_path, dong='PKG', manual_anchor=(470983, -1300555))
    
    # 2. 기준 도면 설정 및 통일
    print("\n[Step 2] Unifying Coordinates (Ref: Dong)...")
    unifier.unify(reference='dong')
    
    # 3. 각 도면에서 기둥 추출
    print("\n[Step 3] Extracting Columns with Symbols...")
    extractor = StructuralExtractor()
    
    doc_dong = unifier.get_doc('dong')
    res_dong = extractor.extract(doc_dong)
    # 기둥 정보
    cols_dong_list = [(c.cx, c.cy) for c in res_dong.columns]
    cols_dong_sym = {c.symbol: (c.cx, c.cy) for c in res_dong.columns if c.symbol != "NOCOL"}
    print(f"  Dong Columns: {len(cols_dong_list)} (Labeled: {len(cols_dong_sym)})")
    
    doc_pkg = unifier.get_doc('pkg')
    res_pkg = extractor.extract(doc_pkg)
    cols_pkg_list = [(c.cx, c.cy) for c in res_pkg.columns]
    cols_pkg_sym = {c.symbol: (c.cx, c.cy) for c in res_pkg.columns if c.symbol != "NOCOL"}
    print(f"  PKG Columns: {len(cols_pkg_list)} (Labeled: {len(cols_pkg_sym)})")
    
    # 4. 겹침 검증 (Overlap)
    print("\n[Step 4] Verifying Overlap (Tol: 500mm)...")
    report = unifier.verify_overlap('dong', 'pkg', cols_dong_list, cols_pkg_list, tol_mm=500.0)
    
    print("\n[Verification Report]")
    print(f"  Matched Columns: {report['matched']}")
    print(f"  Overlap Rate: {report['rate']*100:.1f}%")
    print(f"  Average Error: {report['avg_dist']:.1f} mm")
    
    if report['matched'] > 50:
        print("\n✅ SUCCESS: Coordination alignment verified by geometric overlap!")
    else:
        print("\n❌ FAILURE: Low overlap count.")

if __name__ == "__main__":
    verify()
