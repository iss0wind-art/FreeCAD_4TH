
import sys
import os
import ezdxf
import math
from shapely.geometry import Polygon

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.coord_unifier import CoordUnifier

def verify_slabs():
    dong_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    pkg_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    
    print("--- Slab Unification Verification ---")
    unifier = CoordUnifier()
    
    # 1. 확정된 정밀 앵커로 등록
    unifier.add('dong', dong_path, dong='101', manual_anchor=(149013, 2321258))
    unifier.add('pkg', pkg_path, dong='PKG', manual_anchor=(470983, -1300555))
    unifier.unify(reference='dong')
    
    # 2. 슬래브 추출
    extractor = StructuralExtractor()
    print("Extracting Dong slabs...")
    res_dong = extractor.extract(unifier.get_doc('dong'))
    
    print("Extracting PKG slabs...")
    res_pkg = extractor.extract(unifier.get_doc('pkg'))
    
    # 3. 중합 검증
    print("\n[Verification Report]")
    matches = 0
    total_dong_slabs = len(res_dong.slab_outlines)
    
    pkg_polys = []
    for slab in res_pkg.slab_outlines:
        if len(slab.pts) < 3: continue
        # PKG 슬래브를 Unified 좌표로 변환
        unified_pts = unifier.apply_pts('pkg', slab.pts)
        pkg_polys.append(Polygon(unified_pts))
        
    print(f"  Dong Slabs: {total_dong_slabs}")
    if total_dong_slabs > 0:
        all_dong_pts = [pt for s in res_dong.slab_outlines for pt in s.pts]
        min_x = min(p[0] for p in all_dong_pts); max_x = max(p[0] for p in all_dong_pts)
        min_y = min(p[1] for p in all_dong_pts); max_y = max(p[1] for p in all_dong_pts)
        print(f"    Dong BBox: ({min_x:.0f}, {min_y:.0f}) ~ ({max_x:.0f}, {max_y:.0f})")
        
    print(f"  PKG Slabs (Unified): {len(pkg_polys)}")
    if pkg_polys:
        all_pkg_pts = [pt for p in pkg_polys for pt in p.exterior.coords]
        min_x = min(p[0] for p in all_pkg_pts); max_x = max(p[0] for p in all_pkg_pts)
        min_y = min(p[1] for p in all_pkg_pts); max_y = max(p[1] for p in all_pkg_pts)
        print(f"    PKG BBox: ({min_x:.0f}, {min_y:.0f}) ~ ({max_x:.0f}, {max_y:.0f})")
        
    for slab in res_dong.slab_outlines:
        if len(slab.pts) < 3: continue
        dong_poly = Polygon(slab.pts)
        
        # 중첩되는 PKG 슬래브 찾기 (IOU > 0.5)
        for p_poly in pkg_polys:
            if dong_poly.intersects(p_poly):
                inter = dong_poly.intersection(p_poly).area
                union = dong_poly.union(p_poly).area
                iou = inter / union if union > 0 else 0
                if iou > 0.5:
                    matches += 1
                    break
                    
    print(f"  Matched Slabs: {matches}")
    print(f"  Total Dong Slabs: {total_dong_slabs}")
    print(f"  Slab Overlap Rate: {matches/total_dong_slabs*100:.1f}%" if total_dong_slabs > 0 else "  N/A")

if __name__ == "__main__":
    verify_slabs()
