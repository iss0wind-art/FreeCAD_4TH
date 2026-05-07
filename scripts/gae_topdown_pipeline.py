"""
gae_topdown_pipeline.py — 개팀장 전용 탑다운(역산) 물량 산출 파이프라인
====================================================================
11명 에이전트 병렬화의 시작점. DXF에서 부재를 파싱하고 역산 컷을 수행하여
실제 거푸집(Formwork) 물량을 산출한다.
"""
import sys, os, time, math
import ezdxf

FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"
sys.path.insert(0, FREECAD_BIN)

try:
    import FreeCAD
    import Part
except ImportError:
    print("FreeCAD 파이썬 환경에서 실행해야 합니다.")
    sys.exit(1)

def main():
    print("[개팀장] 탑다운 물량산출 파이프라인 가동 (제로베이스)")
    t0 = time.time()
    
    dxf_path = r"E:\Git\dxf_out\02_구조\260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"
    
    print(f" -> 도면 로드 중: {os.path.basename(dxf_path)}")
    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
    except:
        doc = ezdxf.readfile(dxf_path, encoding='utf-8')
    msp = doc.modelspace()
    
    # 1. 원시 좌표 수집 및 BBox 계산
    cols_data = [] # (cx, cy, w, d)
    
    for e in msp.query('LWPOLYLINE'):
        layer = e.dxf.layer.upper()
        if 'COL' in layer and 'NAME' not in layer and e.is_closed:
            pts = [(p[0], p[1]) for p in e.get_points()]
            if len(pts) >= 4:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                w, d = max(xs) - min(xs), max(ys) - min(ys)
                if w < 3000 and d < 3000 and w > 100 and d > 100:
                    cols_data.append((min(xs)+w/2, min(ys)+d/2, w, d))

    print(f" -> 추출된 기둥 개수: {len(cols_data)}개")
    if not cols_data:
        print("[오류] 기둥을 찾을 수 없습니다.")
        sys.exit(1)
        
    # BBox
    all_x = [c[0] for c in cols_data]
    all_y = [c[1] for c in cols_data]
    min_x, max_x = min(all_x)-2000, max(all_x)+2000
    min_y, max_y = min(all_y)-2000, max(all_y)+2000
    
    SL_TOP = 3000
    SL_BOT = 0
    SLAB_THICK = 200
    BEAM_DEPTH = 600
    
    print(" -> 수평 부재(Ceiling) 구축 중...")
    # 임시 슬라브 (전체 BBox 덮기)
    slab = Part.makeBox(max_x - min_x, max_y - min_y, SLAB_THICK)
    slab.translate(FreeCAD.Vector(min_x, min_y, SL_TOP - SLAB_THICK))
    
    ceiling = slab
    
    # 임시 보 (기둥들을 X축으로 연결하는 가상의 보 생성 - 테스트용)
    # 실제로는 DXF의 S-BEM 라인을 파싱해야 함
    
    print(" -> 수직 부재(Columns) 구축 및 역산(Boolean Cut) 수행 중...")
    final_cols = []
    total_concrete_vol = 0.0
    total_formwork_area = 0.0
    
    for cx, cy, w, d in cols_data:
        # 기둥 바닥부터 층고 끝까지 올림
        col_raw = Part.makeBox(w, d, SL_TOP - SL_BOT)
        col_raw.translate(FreeCAD.Vector(cx - w/2, cy - d/2, SL_BOT))
        
        # 역산 (슬라브/보 덩어리로 자르기)
        col_final = col_raw.cut(ceiling)
        final_cols.append(col_final)
        
        # 물량 산출 (부피, 거푸집 면적)
        total_concrete_vol += col_final.Volume
        
        # 거푸집 면적 = 수직면(Z축 방향의 법선 벡터가 아닌 면)의 넓이 합
        formwork = 0.0
        for face in col_final.Faces:
            # Z축 성분이 0에 가까우면 수직면(측면)
            normal = face.normalAt(0,0)
            if abs(normal.z) < 0.01:
                formwork += face.Area
        total_formwork_area += formwork
        
    print(f"\n=== [개팀장] 물량 산출 결과 (기둥 {len(cols_data)}개 기준) ===")
    print(f"  - 순수 콘크리트 체적: {total_concrete_vol / 1e9:.2f} m³")
    print(f"  - 거푸집 면적 (측면): {total_formwork_area / 1e6:.2f} m²")
    
    print("\n -> STEP 파일 저장 중...")
    comp = Part.makeCompound(final_cols + [ceiling])
    out_step = os.path.join("output", "topdown_pkg_pilot.step")
    comp.exportStep(out_step)
    
    print(f"[완료] {time.time()-t0:.1f}초 소요. 파일: {out_step}")

if __name__ == '__main__':
    main()
