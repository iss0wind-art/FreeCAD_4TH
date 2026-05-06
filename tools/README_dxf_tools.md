# DXF 파서 도구 사용 가이드
## 다음 사람, 다음 도면을 위한 완전 가이드

### 목적
새 도면을 받았을 때 즉시 사용할 수 있는 표준화된 도구 세트.
이 도구들은 한국 건설 구조 DXF 도면을 파싱하여 FreeCAD 3D 모델을 생성한다.

---

## 1. 도면 검사 (inspect_drawing.py)

새 도면을 받았을 때 **첫 번째로 실행**한다.

```bash
# 전체 검사
python tools/inspect_drawing.py <DXF파일> --all

# 선택적 검사
python tools/inspect_drawing.py <DXF파일> --levels          # 표고 파싱만
python tools/inspect_drawing.py <DXF파일> --slab-outline   # 슬라브 외곽만
python tools/inspect_drawing.py <DXF파일> --ev             # E/V 기준점만
python tools/inspect_drawing.py <DXF파일> --grid           # 격자 라벨만
python tools/inspect_drawing.py <DXF파일> --steps          # 단차 구역만
python tools/inspect_drawing.py <DXF파일> --text-grep "SL|EL"  # 텍스트 검색

# 특정 영역만 검사
python tools/inspect_drawing.py <DXF파일> --all --clip "xmin,ymin,xmax,ymax"
```

**출력**: `output/inspect_<파일명>.json`

**주요 확인 항목**:
- 레이어명 (기둥/보/슬라브/벽 레이어 확인)
- 블록명 (기둥 블록 패턴: C400X800, B2-B1 C2 등)
- 격자 라벨 (X1~Xn, Y1~Yn)
- SL/GL 표고값 (층고 계산용)
- E/V 코어 위치 (좌표 통일 기준점)

---

## 2. 좌표 정렬 탐색 (probe_coord_align.py)

두 도면의 기둥 좌표를 자동으로 매핑하여 오프셋 계산.

```bash
python tests/probe_coord_align.py
```

**결과**: `output/coord_align_result.json`
- `alignment.tx`, `alignment.ty`: 지하주차장 → 101동 변환 오프셋 (mm)

---

## 3. 파서 패키지 (core/dxf_parser/)

```python
from core.dxf_parser import (
    scan,               # 전수 엔티티 스캔
    CoordUnifier,       # 다중 도면 좌표 통일
    FullExtractor,      # 기둥·슬라브·벽 추출
    parse_levels,       # 표고 파싱
    parse_step_zones,   # 단차 구역 파싱
    TextLabelEVDetector, GridAnchorDetector,  # E/V·격자 검출
)
```

### 표준 파싱 흐름

```python
# 1. 엔티티 인벤토리
result = scan(dxf_path, clip=(xmin,ymin,xmax,ymax))
print(result.report())

# 2. 층고 파싱
level_set = parse_levels(dxf_path)
print(level_set.floor_sl)  # {'B2F': -9050.0, 'B1F': -5600.0, '1F': 370.0}
print(level_set.floor_height('B2F', 'B1F'))  # 3450.0

# 3. 좌표 통일
unifier = CoordUnifier()
unifier.add('dong', dong_dxf, dong='101')
unifier.add('basement', bsmnt_dxf, dong='지하주차장',
            manual_anchor=(632082, -1296738))
transforms = unifier.unify(reference='dong')
unified_x, unified_y = unifier.apply('basement', raw_x, raw_y)

# 4. 구조 부재 추출
import ezdxf
doc = ezdxf.readfile(dxf_path, encoding='cp949')
extractor = FullExtractor(min_slab_area_m2=100.0)
result = extractor.extract(doc, clip=(xmin,ymin,xmax,ymax))
# result.columns: 기둥 목록
# result.slab_outlines: 슬라브 외곽 목록 (면적 큰 것 먼저)

# 5. 단차 구역
zone_map = parse_step_zones(dxf_path, clip=clip)
actual_z = zone_map.slab_z(col_x, col_y, 'B2F')  # 실제 바닥 Z
```

---

## 4. 확정 치수 (부산 에코델타 24BL 101동)

| 항목 | 값 | 출처 |
|-----|---|------|
| B2F SL | -9050 mm | S30-001~010 GL. -9.05 |
| B1F SL | -5600 mm | S30-001~010 GL. -5.60 |
| 1F SL | +370 mm | 지하주차장 도면 |
| B2F 슬라브 두께 | 150 mm | S40-051~057 826건 |
| B1F 슬라브 두께 | 150 mm | S40-061~070 2370건 |
| 보 높이 | 900 mm | codex_beams_basement.json 40종 |
| 층고 B2F→B1F | 3450 mm | 계산값 |
| 층고 B1F→1F | 5970 mm | 계산값 |

---

## 5. 좌표 통일 오프셋 (v4 확정값)

| 시트 | TX (mm) | TY (mm) | 기준 |
|-----|---------|---------|------|
| S30-001 B2F | 0 | 0 | **기준** |
| S30-002 B1F | -112,279 | -834 | centroid 정렬 |
| PKG-B2 B2F | -425,014 | +3,616,519 | centroid 정렬 |
| PKG-B1 B1F | -1,066,789 | +3,632,247 | centroid 정렬 |

---

## 6. 다음 도면 대응 체크리스트

새 도면을 받았을 때:
1. `inspect_drawing.py --all` 실행 → 레이어명 확인
2. 레이어명이 다르면 → `full_extractor.py` 정규식 업데이트
3. 격자 라벨 확인 → `ev_detector.py` GridAnchorDetector 패턴 업데이트
4. SL TEXT 형식 확인 → `level_parser.py` 패턴 업데이트
5. `probe_coord_align.py` 실행 → 오프셋 계산
6. 결과로 `poc_v4_build_3d.py` SHEET_TX 업데이트

---

*2026-05-06 이천(李蕆) 작성. 도면에 있으면 도면에서 읽는다.*
