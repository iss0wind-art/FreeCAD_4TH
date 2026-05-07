"""
test_topdown_method.py — 탑다운(역산) 방식의 솔리드 절단 테스트
==============================================================
수평부재(슬라브, 보)를 먼저 그리고, 수직부재(기둥, 벽)를 아래에서 위로 올려
닿으면 멈추는(Boolean Cut) 특허 방식을 검증한다.
"""
import sys
import FreeCAD
import Part

def main():
    doc = FreeCAD.newDocument("TopDownTest")
    
    # 1. 층 설정
    SL_TOP = 3000
    SL_BOT = 0
    
    # 2. 수평 부재 (먼저 그리기)
    # 슬라브: 두께 200 (Z: 2800 ~ 3000)
    slab = Part.makeBox(5000, 5000, 200)
    slab.translate(FreeCAD.Vector(-1000, -1000, SL_TOP - 200))
    
    # 보: 춤 600 (Z: 2400 ~ 3000)
    beam = Part.makeBox(400, 5000, 600)
    beam.translate(FreeCAD.Vector(1000, -1000, SL_TOP - 600))
    
    # 수평 부재 결합 (천장)
    ceiling = slab.fuse(beam)
    
    # 3. 수직 부재 (아래에서 위로 끝까지 올림)
    # 기둥 1: 슬라브와만 만나는 기둥 (Z: 0 ~ 3000)
    col1_raw = Part.makeBox(600, 600, SL_TOP - SL_BOT)
    col1_raw.translate(FreeCAD.Vector(0, 0, SL_BOT))
    
    # 기둥 2: 보와 만나는 기둥 (Z: 0 ~ 3000)
    col2_raw = Part.makeBox(600, 600, SL_TOP - SL_BOT)
    col2_raw.translate(FreeCAD.Vector(900, 0, SL_BOT)) # X=900~1500, 보(X=1000~1400)와 겹침
    
    # 4. 역산 (수평부재 닿으면 멈추기 -> Boolean Cut)
    col1_final = col1_raw.cut(ceiling)
    col2_final = col2_raw.cut(ceiling)
    
    # 5. 결과 검증
    print("=== 탑다운 역산 방식 검증 결과 ===")
    print(f"기둥 1 (슬라브 하단 부착):")
    print(f"  - 원본 높이: {col1_raw.BoundBox.ZLength} mm")
    print(f"  - 절단 후 높이: {col1_final.BoundBox.ZLength} mm (예상: 2800)")
    
    print(f"기둥 2 (보 하단 부착):")
    print(f"  - 원본 높이: {col2_raw.BoundBox.ZLength} mm")
    print(f"  - 절단 후 높이: {col2_final.BoundBox.ZLength} mm (예상: 2400)")
    
    # 파일 저장 (육안 확인용)
    Part.show(col1_final)
    Part.show(col2_final)
    Part.show(ceiling)
    doc.saveAs("output/topdown_test.FCStd")
    print("\n[성공] output/topdown_test.FCStd 저장 완료.")

if __name__ == '__main__':
    main()
