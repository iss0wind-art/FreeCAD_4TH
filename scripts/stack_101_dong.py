import os
import json
import dataclasses
import copy
import math

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# DXF에서 추출한 각 층별 텍스트 앵커 좌표 (X, Y 분리)
FLOOR_ANCHORS_X = {
    "B2F": 85703.6,
    "B1F": 211703.6,
    "1F": 337703.6,
    "2F": 463703.6,
    "TYP": 589841.1,
    "16F": 713897.0,
    "PH2": 906671.2,
    "ROOF": 949702.9,
    "PH3": 968614.3
}

FLOOR_ANCHORS_Y = {
    "B2F": 2082025.4,
    "B1F": 2082025.4,
    "1F": 2082025.4,
    "2F": 2082025.4,
    "TYP": 2082025.4,
    "16F": 2082025.4,
    "PH2": 2132397.5,
    "ROOF": 2077818.8,
    "PH3": 2084499.4
}

# 단면도 기반 층고 데이터 (Z값 mm)
FLOOR_HEIGHTS = {
    "B2F": 3300,
    "B1F": 4500,
    "1F": 2930,
    "2F": 2900,
    "TYP": 2900,
    "16F": 2900,
    "PH2": 3000,
    "ROOF": 3000,
    "PH3": 3000
}

ELEVATIONS = {}
current_z = 0
ELEVATIONS["1F"] = 0
ELEVATIONS["B1F"] = -FLOOR_HEIGHTS["B1F"]
ELEVATIONS["B2F"] = ELEVATIONS["B1F"] - FLOOR_HEIGHTS["B2F"]
ELEVATIONS["2F"] = FLOOR_HEIGHTS["1F"]
current_z = ELEVATIONS["2F"] + FLOOR_HEIGHTS["2F"]
for f in range(3, 16):
    ELEVATIONS[f"{f}F"] = current_z
    current_z += FLOOR_HEIGHTS["TYP"]
ELEVATIONS["16F"] = current_z
ELEVATIONS["ROOF"] = current_z + FLOOR_HEIGHTS["16F"]
ELEVATIONS["PH2"] = ELEVATIONS["ROOF"] + FLOOR_HEIGHTS["ROOF"]
ELEVATIONS["PH3"] = ELEVATIONS["PH2"] + FLOOR_HEIGHTS["PH2"]

def get_floor_by_x(x):
    """정확한 Midpoint 구간으로 분할하여 건물이 찢어지는 현상 방지"""
    if x < 135500: return "B2F"  # 지하2층과 지하1층 경계 정밀 조정
    if x < 274800: return "B1F"
    if x < 400000: return "1F"
    if x < 526700: return "2F"
    if x < 651800: return "TYP"
    if x < 831800: return "16F"
    if x < 930000: return "PH2"
    if x < 955000: return "ROOF"
    return "PH3"

def normalize_entity(entity, floor_key, entity_type):
    anchor_x = FLOOR_ANCHORS_X[floor_key]
    anchor_y = FLOOR_ANCHORS_Y[floor_key]
    
    e = copy.deepcopy(entity)
    if entity_type == "columns":
        e["cx"] -= anchor_x
        e["cy"] -= anchor_y
    elif entity_type == "beams":
        e["x0"] -= anchor_x
        e["y0"] -= anchor_y
        e["x1"] -= anchor_x
        e["y1"] -= anchor_y
    elif entity_type == "walls":
        e["p1"][0] -= anchor_x
        e["p1"][1] -= anchor_y
        e["p2"][0] -= anchor_x
        e["p2"][1] -= anchor_y
    elif entity_type == "slabs":
        for pt in e["pts"]:
            pt[0] -= anchor_x
            pt[1] -= anchor_y
    return e

def process_stack():
    input_file = r"D:\Git\FreeCAD_4TH\output\101_dong_formwork_3d.json"
    output_file = r"D:\Git\FreeCAD_4TH\output\101_stacked_formwork_3d.json"
    
    print("스택 생성 시작 (노이즈 필터링 및 옥탑 좌표 정밀 정렬 포함)...")
    data = load_json(input_file)
    stacked_data = {"columns": [], "beams": [], "walls": [], "slabs": []}
    
    def process_entities(entity_list, entity_type):
        for e in entity_list:
            x, y = 0, 0
            if entity_type == "columns": 
                if max(e["w"], e["h"]) > 4000: continue
                x, y = e["cx"], e["cy"]
            elif entity_type == "beams": 
                length = math.hypot(e["x1"]-e["x0"], e["y1"]-e["y0"])
                if length > 15000: continue
                x, y = (e["x0"]+e["x1"])/2, (e["y0"]+e["y1"])/2
            elif entity_type == "walls": 
                if not e["p1"]: continue
                x, y = (e["p1"][0]+e["p2"][0])/2, (e["p1"][1]+e["p2"][1])/2
            elif entity_type == "slabs":
                if not e["pts"]: continue
                x, y = e["pts"][0][0], e["pts"][0][1]
                
            base_floor = get_floor_by_x(x)
            if not base_floor: continue
            
            # 아파트 날개(Wing)가 55m까지 뻗어나가므로 허용 오차를 100m로 늘려 날개 유실 방지 (대신 200m 밖 기초 평면도는 차단)
            if abs(y - FLOOR_ANCHORS_Y[base_floor]) > 100000:
                continue

                
            norm_e = normalize_entity(e, base_floor, entity_type)
            
            if base_floor == "TYP":
                for f in range(3, 16):
                    floor_name = f"{f}F"
                    dup_e = copy.deepcopy(norm_e)
                    dup_e["z"] = ELEVATIONS[floor_name]
                    dup_e["floor"] = floor_name
                    stacked_data[entity_type].append(dup_e)
            else:
                norm_e["z"] = ELEVATIONS[base_floor]
                norm_e["floor"] = base_floor
                stacked_data[entity_type].append(norm_e)

    process_entities(data.get("columns", []), "columns")
    process_entities(data.get("beams", []), "beams")
    process_entities(data.get("walls", []), "walls")
    process_entities(data.get("slabs", []), "slabs")
    
    save_json(stacked_data, output_file)
    print(f"완료! 적층된 부재 수: 기둥={len(stacked_data['columns'])}, 보={len(stacked_data['beams'])}, 벽={len(stacked_data['walls'])}, 슬래브={len(stacked_data['slabs'])}")

if __name__ == "__main__":
    process_stack()
