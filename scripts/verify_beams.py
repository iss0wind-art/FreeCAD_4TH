
import sys
import os
import ezdxf
import math

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.coord_unifier import CoordUnifier

def verify_beams():
    dong_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    pkg_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    
    print("--- Beam Unification Verification ---")
    unifier = CoordUnifier()
    
    # 확정된 정밀 앵커
    unifier.add('dong', dong_path, dong='101', manual_anchor=(149013, 2321258))
    unifier.add('pkg', pkg_path, dong='PKG', manual_anchor=(470983, -1300555))
    unifier.unify(reference='dong')
    
    extractor = StructuralExtractor()
    print("Extracting Dong beams...")
    res_dong = extractor.extract(unifier.get_doc('dong'))
    
    print("Extracting PKG beams...")
    res_pkg = extractor.extract(unifier.get_doc('pkg'))
    
    print("\n[Verification Report]")
    matches = 0
    total_dong_beams = len(res_dong.beams)
    
    # 빔 매칭: 중심점이 가깝고 (500mm), 각도가 비슷할 것
    pkg_beams_unified = []
    for b in res_pkg.beams:
        x0, y0 = unifier.apply('pkg', b.x0, b.y0)
        x1, y1 = unifier.apply('pkg', b.x1, b.y1)
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        pkg_beams_unified.append((cx, cy))
        
    for b in res_dong.beams:
        cx = (b.x0 + b.x1) / 2
        cy = (b.y0 + b.y1) / 2
        
        for pcx, pcy in pkg_beams_unified:
            if math.hypot(cx - pcx, cy - pcy) < 500:
                matches += 1
                break
                
    print(f"  Matched Beams: {matches}")
    print(f"  Total Dong Beams: {total_dong_beams}")
    print(f"  Beam Overlap Rate: {matches/total_dong_beams*100:.1f}%" if total_dong_beams > 0 else "  N/A")

if __name__ == "__main__":
    verify_beams()
