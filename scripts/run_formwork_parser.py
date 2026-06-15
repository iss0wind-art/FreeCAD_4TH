import os
import json
import dataclasses
from core.dxf_parser.structural_extractor import parse_structural_frame

TARGET_FILES = {
    "101_dong": r"D:\06.3지국 전용방\01. 설계도면\dxf_out\02_구조\S30-001~010-101동 구조평면도.dxf"
}

OUTPUT_DIR = r"D:\Git\FreeCAD_4TH\output"

def wall_to_dict(wall):
    return {
        "p1": wall.centerline_p1,
        "p2": wall.centerline_p2,
        "thickness": wall.thickness,
        "wall_type": "SHEAR",
        "layer": ""
    }

def process_file(name, filepath):
    print(f"[{name}] 파싱 시작: {filepath}")
    if not os.path.exists(filepath):
        print(f"오류: 파일을 찾을 수 없습니다 -> {filepath}")
        return
        
    data = parse_structural_frame(filepath)
    
    out_data = {
        "columns": [dataclasses.asdict(c) for c in data.columns],
        "beams": [dataclasses.asdict(b) for b in data.beams],
        "slabs": [dataclasses.asdict(s) for s in data.slab_outlines],
        "walls": [wall_to_dict(w) for w in data.shear_walls]
    }
    
    # 3D 뷰어 검증용 JSON 저장
    out_path = os.path.join(OUTPUT_DIR, f"{name}_formwork_3d.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)
        
    print(f"[{name}] 완료. 추출된 부재:")
    print(f"  - 기둥: {len(data.columns)} 개")
    print(f"  - 보: {len(data.beams)} 개")
    print(f"  - 벽체: {len(data.shear_walls)} 쌍")
    print(f"  - 슬래브: {len(data.slab_outlines)} 개")
    print(f"  - 저장 위치: {out_path}")
    
    # NOCOL, NOBEAM 등 매칭 실패 개수 확인
    nocol = sum(1 for c in data.columns if c.symbol == 'NOCOL')
    nobeam = sum(1 for b in data.beams if b.symbol == 'NOBEAM')
    print(f"  [무결성 검사] 라벨 누락(NOCOL): {nocol}개, (NOBEAM): {nobeam}개")
    print("-" * 50)

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for name, path in TARGET_FILES.items():
        process_file(name, path)
