
import sys
import os
import ezdxf
import math
from collections import Counter

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.coord_unifier import CoordUnifier

def cluster_offsets():
    dong_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    pkg_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    
    print("--- Symbol Offset Clustering ---")
    unifier = CoordUnifier()
    
    # 1. 도면 등록 (초기 앵커 - 무의미하더라도 일단 등록)
    unifier.add('dong', dong_path, dong='101', manual_anchor=(0, 0))
    unifier.add('pkg', pkg_path, dong='PKG', manual_anchor=(0, 0))
    unifier.unify(reference='dong')
    
    # 2. 기둥 추출
    extractor = StructuralExtractor()
    print("Extracting Dong columns...")
    res_dong = extractor.extract(unifier.get_doc('dong'))
    cols_dong = {c.symbol: (c.cx, c.cy) for c in res_dong.columns if c.symbol != "NOCOL"}
    
    print("Extracting PKG columns...")
    res_pkg = extractor.extract(unifier.get_doc('pkg'))
    cols_pkg = {c.symbol: (c.cx, c.cy) for c in res_pkg.columns if c.symbol != "NOCOL"}
    
    # 3. 오프셋 계산 (Dong_Coord - PKG_Coord)
    # 목표: Unified_Dong = PKG_Raw + TX_PKG
    # 여기서 Dong_Raw = PKG_Raw + TX_PKG  (Dong이 기준이므로)
    # TX_PKG = Dong_Raw - PKG_Raw
    
    offsets = []
    common_symbols = set(cols_dong.keys()) & set(cols_pkg.keys())
    print(f"Common Symbols Found: {len(common_symbols)}")
    
    for sym in common_symbols:
        dx, dy = cols_dong[sym]
        px, py = cols_pkg[sym]
        tx, ty = dx - px, dy - py
        offsets.append((sym, round(tx, -1), round(ty, -1), tx, ty)) # 10mm 단위로 반올림하여 클러스터링
        
    # 4. 클러스터링
    clusters = {}
    for sym, ctx, cty, rtx, rty in offsets:
        key = (ctx, cty)
        if key not in clusters:
            clusters[key] = []
        clusters[key].append((sym, rtx, rty))
        
    sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)
    
    print("\n[Offset Clusters]")
    for i, (key, members) in enumerate(sorted_clusters[:5]):
        avg_tx = sum(m[1] for m in members) / len(members)
        avg_ty = sum(m[2] for m in members) / len(members)
        print(f"Cluster #{i+1}: Count={len(members)}, Approx Offset={key}")
        print(f"  Avg TX={avg_tx:.1f}, Avg TY={avg_ty:.1f}")
        print(f"  Symbols: {[m[0] for m in members]}")
        
    if sorted_clusters:
        best_key, best_members = sorted_clusters[0]
        final_tx = sum(m[1] for m in best_members) / len(best_members)
        final_ty = sum(m[2] for m in best_members) / len(best_members)
        print(f"\n🚀 Best Alignment Candidate:")
        print(f"  TX = {final_tx:.1f}")
        print(f"  TY = {final_ty:.1f}")
        
        # 앵커로 환산 (Dong Anchor가 149013, 2321258 일 때)
        # TX = Dong_Anchor - PKG_Anchor
        # PKG_Anchor = Dong_Anchor - TX
        dong_ax, dong_ay = 149013, 2321258
        pkg_ax = dong_ax - final_tx
        pkg_ay = dong_ay - final_ty
        print(f"  If Dong Anchor is ({dong_ax}, {dong_ay}),")
        print(f"  PKG Anchor should be ({pkg_ax:.1f}, {pkg_ay:.1f})")

if __name__ == "__main__":
    cluster_offsets()
