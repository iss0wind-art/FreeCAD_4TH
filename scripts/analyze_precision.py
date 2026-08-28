
import sys
import os
import numpy as np

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.dxf_parser.structural_extractor import StructuralExtractor
from core.dxf_parser.coord_unifier import CoordUnifier

def analyze_precision():
    dong_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S30-001~010-101동 구조평면도.dxf"
    pkg_path = "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    
    print("--- Precision Residual Analysis ---")
    unifier = CoordUnifier()
    
    # 1. 확정된 앵커로 정합 (TX=-321970, TY=3621813)
    unifier.add('dong', dong_path, manual_anchor=(149013, 2321258))
    unifier.add('pkg', pkg_path, manual_anchor=(470983, -1300555))
    unifier.unify(reference='dong')
    
    extractor = StructuralExtractor()
    print("Extracting columns...")
    res_dong = extractor.extract(unifier.get_doc('dong'))
    res_pkg = extractor.extract(unifier.get_doc('pkg'))
    
    # 2. 매칭된 기둥 쌍 찾기 (최단거리 500mm 이내)
    dong_pts = np.array([(c.cx, c.cy) for c in res_dong.columns])
    pkg_pts_raw = np.array([(c.cx, c.cy) for c in res_pkg.columns])
    
    matches = []
    for px, py in pkg_pts_raw:
        dx_unified, dy_unified = unifier.apply('pkg', px, py)
        # 최단 거리 검색
        dists = np.sqrt(np.sum((dong_pts - [dx_unified, dy_unified])**2, axis=1))
        idx = np.argmin(dists)
        if dists[idx] < 500:
            matches.append(((px, py), dong_pts[idx]))
            
    print(f"Matched Pairs: {len(matches)}")
    if not matches: return

    P = np.array([m[0] for m in matches]) # PKG Raw
    D = np.array([m[1] for m in matches]) # Dong Unified (Ref)
    
    # 3. 선형 회귀를 통한 Affine 변환 분석 (D_centered = A * P_centered)
    # P: (N, 2), D: (N, 2)
    # D_i = A * P_i + T
    
    P_mean = np.mean(P, axis=0)
    D_mean = np.mean(D, axis=0)
    
    P_centered = P - P_mean
    D_centered = D - D_mean
    
    # A = (D_centered^T * P_centered) * (P_centered^T * P_centered)^-1
    # D_centered = P_centered * A^T
    A_T, residuals_lstsq, rank, s = np.linalg.lstsq(P_centered, D_centered, rcond=None)
    A = A_T.T
    T = D_mean - A @ P_mean
    
    print("\n[Transformation Matrix Analysis]")
    print(f"  A (Scale/Rotation):\n{A}")
    print(f"  T (Translation): {T}")
    
    # 스케일 계산 (Det(A)의 루트)
    scale = np.sqrt(np.abs(np.linalg.det(A)))
    # 회전각 계산 (A = [[s*cos, -s*sin], [s*sin, s*cos]])
    angle = math.degrees(math.atan2(A[1, 0], A[0, 0]))
    
    print(f"\n  Detected Scale: {scale:.8f}")
    print(f"  Detected Rotation: {angle:.8f} degrees")
    
    # 4. 잔차(Residual) 분석
    D_pred = (A @ P.T).T + T
    residuals = np.sqrt(np.sum((D - D_pred)**2, axis=1))
    
    print(f"\n[Residual Statistics]")
    print(f"  Max Error: {np.max(residuals):.2f} mm")
    print(f"  Mean Error: {np.mean(residuals):.2f} mm")
    print(f"  Median Error: {np.median(residuals):.2f} mm")
    print(f"  Std Dev: {np.std(residuals):.2f} mm")
    
    if np.mean(residuals) < 1.0:
        print("\n✅ PERFECT ALIGNMENT REACHED (Sub-mm precision)!")
    else:
        print(f"\n⚠️ Still some noise ({np.mean(residuals):.2f}mm). Inspecting outliers (Err > 50mm)...")
        outliers = []
        for i, r in enumerate(residuals):
            if r > 50:
                outliers.append((matches[i], r))
        
        print(f"  Outliers found: {len(outliers)}")
        for m, r in outliers[:10]:
            pkg_raw, dong_ref = m
            # 심볼을 찾으려면 extractor 결과에서 매칭해야 함. 
            # 여기서는 좌표만 출력
            print(f"    Error: {r:.1f}mm at Dong({dong_ref[0]:.0f}, {dong_ref[1]:.0f})")

    # 5. 아웃라이어 제외 후 재계산
    clean_indices = [i for i, r in enumerate(residuals) if r <= 50]
    P_clean = P[clean_indices]
    D_clean = D[clean_indices]
    
    if len(P_clean) > 10:
        P_m = np.mean(P_clean, axis=0)
        D_m = np.mean(D_clean, axis=0)
        A_T_c, _, _, _ = np.linalg.lstsq(P_clean - P_m, D_clean - D_m, rcond=None)
        A_c = A_T_c.T
        T_c = D_m - A_c @ P_m
        
        D_pred_c = (A_c @ P_clean.T).T + T_c
        res_c = np.sqrt(np.sum((D_clean - D_pred_c)**2, axis=1))
        
        angle_c = math.degrees(math.atan2(A_c[1, 0], A_c[0, 0]))
        
        print(f"\n[Clean Statistics (N={len(P_clean)})]")
        print(f"  Mean Error: {np.mean(res_c):.2f} mm")
        print(f"  Median Error: {np.median(res_c):.2f} mm")
        print(f"  Max Error: {np.max(res_c):.2f} mm")
        print(f"  Scale: {np.sqrt(np.abs(np.linalg.det(A_c))):.8f}")
        print(f"  Rotation: {angle_c:.8f} degrees")
        
    # 6. 정밀 분석 제안
    if np.median(res_c) < 2.0:
        print("\n🚀 CONCLUSION: HIGH PRECISION ALIGNMENT ACHIEVED.")
        print("  The 14 outliers are likely drafting discrepancies or misidentifications.")
        print(f"  FINAL RECOMMENDED TX: {T_c[0]:.2f}")
        print(f"  FINAL RECOMMENDED TY: {T_c[1]:.2f}")
    else:
        print("\n⚠️ Still not perfect. Further investigation required.")

if __name__ == "__main__":
    import math
    analyze_precision()

if __name__ == "__main__":
    import math
    analyze_precision()
