
import sys
import os
import ezdxf
# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.dxf_parser.safe_reader import safe_readfile
from core.dxf_parser.ev_detector import TextLabelEVDetector

def calc_offset():
    # 101동 도면 경로
    dong_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    # 지하주차장 통합 도면 경로
    pkg_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    
    print(f"--- Unification Strategy: E/V Core Alignment ---")
    
    print(f"Loading Dong drawing: {os.path.basename(dong_path)}")
    doc_dong = safe_readfile(dong_path)
    
    print(f"Loading PKG drawing: {os.path.basename(pkg_path)}")
    doc_pkg = safe_readfile(pkg_path)
    
    # 101동 클립 (B1F 영역으로 추정되는 곳 설정 - ev_detector 내에서 자동 클러스터링하므로 일단 None)
    detector = TextLabelEVDetector()
    
    print("\n[Step 1] Detecting E/V Anchor in Dong...")
    anchor_dong = detector.detect(doc_dong)
    if anchor_dong:
        print(f"  Found: SW({anchor_dong.sw_corner[0]:.0f}, {anchor_dong.sw_corner[1]:.0f}), Conf: {anchor_dong.confidence}")
    else:
        print("  Failed to find E/V anchor in Dong.")
    
    print("\n[Step 2] Detecting E/V Anchor in PKG...")
    anchor_pkg = detector.detect(doc_pkg)
    if anchor_pkg:
        print(f"  Found: SW({anchor_pkg.sw_corner[0]:.0f}, {anchor_pkg.sw_corner[1]:.0f}), Conf: {anchor_pkg.confidence}")
    else:
        print("  Failed to find E/V anchor in PKG.")
    
    if anchor_dong and anchor_pkg:
        dx = anchor_dong.sw_corner[0] - anchor_pkg.sw_corner[0]
        dy = anchor_dong.sw_corner[1] - anchor_pkg.sw_corner[1]
        
        print("\n[Unification Result]")
        print(f"  TX_EXACT (DX): {dx:.0f} mm")
        print(f"  TY_EXACT (DY): {dy:.0f} mm")
        print(f"\n  Proposed Config Update:")
        print(f"  TX_PKG = {dx:.0f}")
        print(f"  TY_PKG = {dy:.0f}")
    else:
        print("\n[Critical Error] Unification failed due to missing anchors.")

if __name__ == "__main__":
    calc_offset()
