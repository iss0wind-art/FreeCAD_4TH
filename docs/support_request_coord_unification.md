# 지원 요청: DXF 다중 도면 좌표 통일 — 상세 현황 보고

**요청일**: 2026-05-06  
**프로젝트**: 부산 에코델타 24BL 지하주차장 + 101동 FreeCAD 3D 모델  
**작업 디렉토리**: `D:\Git\FreeCAD_4TH`  
**요청자**: 이천(李蕆) 3지국  

---

## 지원 요청 핵심

**목표**: DXF 도면 2개 파일의 좌표계를 통일해서 하나의 3D 모델로 합치기  
**현재 상태**: 두 파일 간 정밀 정합(TX, TY 값) 미해결  
**필요한 것**: E/V 코어(엘리베이터 코어) 기준점을 두 파일에서 찾아 정확한 TX, TY 계산

---

## 1. 도면 파일 구조

### 파일 1: 101동 구조평면도
```
경로: D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/
      S30-001~010-101동 구조평면도.dxf
인코딩: CP949 (한국 도면)
내용: 101동 타워 지하2층(B2F), 지하1층(B1F) 등 구조평면도가 
      X 방향으로 나란히 배치된 멀티시트 DXF
```

**도면 내 시트 레이아웃**:
```
[S30-001 B2F]         [S30-002 B1F]         [S30-003 이상...]
offset_x = 116247     offset_x = 242247
offset_y = 2290548    offset_y = 2290548
← X 126000mm 간격 →
```

검증 완료 데이터:
- S30-001 기둥 260개, 모델 X: 122763~239133, 모델 Y: 2296516~2451963
- S30-002 기둥 139개 (B2F 절반 범위만 포함, 미완전)
- S-GIRDER 보: 3399개, 모델 X: 56884~232893, 모델 Y: 2090534~2387914
- **S30-001 첫 기둥(C1) 모델 좌표**: (129241, 2381804)
- **가장 가까운 보 끝점**: (129491, 2381554), 거리 354mm (기둥 단면 내 ✓)

### 파일 2: 지하주차장 구조평면도
```
경로: D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/
      260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf
인코딩: CP949
내용: 24BL 전체 지하주차장 (B2F + B1F 및 다수 동 포함한 거대 도면)
```

**101동 인접 구역 클립**:
```python
# 101동 인접 B2F (검증 완료)
PKG_B2F_CLIP = (552082, -1376738, 712082, -1216738)  # DXF 좌표
# 추출 결과: 144개 기둥, DXF X: 552082~712082

# 101동 인접 B1F (= B2F + X 630000, Y1 기준점으로 검증)
PKG_B1F_CLIP = (1182082, -1376738, 1342082, -1216738)  # DXF 좌표
# 추출 결과: 164개 기둥
```

**Y1 기준점으로 확인된 B2F↔B1F 간격**:
```
B2F Y1 라벨: DXF X=757132, Y=-1318257
B1F Y1 라벨: DXF X=1387132, Y=-1318257
간격: 1387132 - 757132 = 630000mm (정확히 일치)
```

---

## 2. 현재까지 적용한 좌표 변환

```python
TX_PKG = -448000.0   # BSMNT → DONG 통일 (문제: 정밀도 낮음)
TY_PKG =  3622000.0

DONG_B1F_DX = -126000.0  # S30-002 → S30-001 (에이전트 160쌍 검증 완료)
PKG_B1F_DX  = -630000.0  # PKG-B1 → PKG-B2 (Y1 기준점 검증 완료)

# 변환 함수
def tfm_dong_b2(x, y): return x, y                           # S30-001 그대로
def tfm_dong_b1(x, y): return x + DONG_B1F_DX, y            # -126000 보정
def tfm_pkg_b2(x, y):  return x + TX_PKG, y + TY_PKG         # BSMNT→DONG
def tfm_pkg_b1(x, y):  return x + PKG_B1F_DX + TX_PKG, y + TY_PKG  # -630000+btrans
```

**현재 TX=-448000의 문제**:
- 출처: `output/coord_align_result.json` (컬럼 브루트포스 매칭)
- 매칭 결과: 4쌍 매칭, 매칭률 13.3%, 오차 189mm
- **문제**: 매칭 쌍이 너무 적어 통계적으로 불안정

---

## 3. 지원 요청 핵심: E/V 코어 기준점 정합

### 3.1 왜 E/V 코어인가

한국 구조도면은 다중 층 도면을 한 파일에 배치할 때 **엘리베이터 코어(E/V Core) SW 모서리**를 공통 기준점으로 사용합니다. 이 점이 두 파일에 존재하면 정확한 TX, TY를 계산할 수 있습니다.

### 3.2 이미 만들어진 탐지기

```python
# 경로: core/dxf_parser/ev_detector.py
# 두 가지 탐지 방법:
from core.dxf_parser.ev_detector import TextLabelEVDetector, GridAnchorDetector

# 방법1: TEXT 라벨 ('EV', 'E/V', '엘리베이터' 등) 기반
detector = TextLabelEVDetector()
ev_dong  = detector.detect(doc_dong,  clip=DONG_CLIP)

# 방법2: X1/Y1 격자 교점 기반
grid_det = GridAnchorDetector()
anchor   = grid_det.detect(doc_dong, clip=DONG_CLIP)
```

### 3.3 올바른 TX 계산 방법

```python
# 목표 코드 (다음 세션에서 구현)
ev_dong  = find_ev_core(DONG_DXF,  DONG_CLIP)   # 101동 DXF의 E/V 코어
ev_bsmnt = find_ev_core(BSMNT_DXF, PKG_B2F_CLIP) # 주차장 DXF의 동일 E/V 코어

# 정확한 오프셋 (추측 없음)
TX_EXACT = ev_dong.cx - ev_bsmnt.cx
TY_EXACT = ev_dong.cy - ev_bsmnt.cy

print(f"정확한 TX = {TX_EXACT:.0f}mm (현재 사용중: -448000)")
print(f"정확한 TY = {TY_EXACT:.0f}mm (현재 사용중: +3622000)")
```

---

## 4. 현재 모델 산출물 현황

### 4.1 최신 빌드 파일

| 파일 | 경로 | 내용 |
|------|------|------|
| STEP | `output/v9_clean.step` | 7411 솔리드, 55MB |
| BOQ JSON | `output/v9_boq.json` | 7411 부재 전체 목록 |
| BOQ CSV | `output/v9_boq.csv` | 집계 산출서 |
| 빌드 스크립트 | `tests/build_v9_clean.py` | 메인 빌드 |
| B2F 검증 | `tests/build_v10_b2f_only.py` | 101동 B2F 단독 |
| 시행착오 매뉴얼 | `docs/coord_unification_trials.md` | 이번 세션 전체 기록 |

### 4.2 현재 모델 부재 집계

```
기둥:   644개   1314.3 m³  (C1, TC1, PC2 등 도면 이름 적용)
보(X): 3734개   6557.0 m³  (400X800, 500X600 등 치수 TEXT 직독)
보(Y): 2902개   7289.5 m³
전단벽: 131개    302.7 m³
────────────────────────────
합계:  7411개  15463.6 m³
```

### 4.3 부재 ID 체계 (방부장 결정)

```
기둥:   {도면원래명}-{층}-{구역}-{seq}   예) C1-B2F-DONG-0001
보:     {치수TEXT}-{층}-{구역}-{seq}    예) 400X800-B2F-DONG-0001
전단벽: SW-{층}-{구역}-{seq}            예) SW-B2F-DONG-0001
```

---

## 5. 시각적 현황

### 5.1 현재 모델 구성

```
101동 타워 (DONG):
  - B2F + B1F 기둥: S30-001 기준 (동일 XY, Z만 다름) ✓
  - 보: S-GIRDER LINE 직독 (3399개) ✓
  - 타워는 site plan에서 회전되어 있어 기울어져 보임 (정상)

주차장 (PKG):
  - B2F 기둥: 144개, 모델 X=104082~198422 ✓
  - B1F 기둥: 151개, 모델 X=104082~198422 (B2F와 동일 ✓)
  - 보: S-GIRDER 레이어 없음 → 미구현
```

### 5.2 남은 시각적 문제

1. **일부 부유 점**: Y 필터로 많이 줄었으나 잔존 (전단벽 미필터 가능성)
2. **DONG-PKG 정밀 정합**: TX=-448000이 대략적, E/V 코어로 교체 필요
3. **주차장 보 없음**: PKG 구역에 보가 없어서 기둥만 표시됨

---

## 6. 실행 환경 및 의존성

```bash
# 실행 명령
freecadcmd tests/build_v9_clean.py

# 필요 환경
- FreeCAD 1.1 (C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe)
- Python packages: ezdxf, numpy
- 작업 디렉토리: D:/Git/FreeCAD_4TH

# 핵심 모듈
core/dxf_parser/
  ├── entity_scanner.py    # iter_all (INSERT 재귀 스캔)
  ├── ev_detector.py       # E/V 코어 탐지 ← 다음 세션 핵심
  ├── coord_unifier.py     # 좌표 통일
  ├── structural_extractor.py  # S-GIRDER, 기둥 추출
  ├── grid_extractor.py    # 격자선 추출
  └── pipeline.py          # 단일 진입점
```

---

## 7. 다음 세션 즉시 실행 순서

```python
# Step 1: E/V 코어 탐지 (두 파일에서)
python -c "
import ezdxf, sys
sys.path.insert(0, 'D:/Git/FreeCAD_4TH')
from core.dxf_parser.ev_detector import TextLabelEVDetector

DONG_DXF  = '...S30-001~010-101동 구조평면도.dxf'
BSMNT_DXF = '...260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf'
DONG_CLIP  = (69013, 2241258, 229013, 2401258)
PKG_B2_CLIP = (552082, -1376738, 712082, -1216738)

det = TextLabelEVDetector()
ev_dong  = det.detect(ezdxf.readfile(DONG_DXF, encoding='cp949'), clip=DONG_CLIP)
ev_bsmnt = det.detect(ezdxf.readfile(BSMNT_DXF, encoding='cp949'), clip=PKG_B2_CLIP)

print(f'DONG  E/V: {ev_dong}')
print(f'BSMNT E/V: {ev_bsmnt}')
print(f'TX = {ev_dong.cx - ev_bsmnt.cx:.0f}')
print(f'TY = {ev_dong.cy - ev_bsmnt.cy:.0f}')
"

# Step 2: TX 업데이트 후 rebuild
# TX_PKG = <계산값>으로 교체 → freecadcmd tests/build_v9_clean.py
```

---

## 8. 참고 JSON 파일

```
output/coord_align_result.json     # 현재 TX=-448000 출처 (신뢰도 낮음)
output/poc_v3_101.json             # 4개 시트 기둥 데이터 (abs_cx/cy 포함)
output/codex_beams_basement.json   # 보 일람표 (RB1~RG3A 치수)
output/v9_boq.json                 # 최신 BOQ
```

---

*작성: 이천(李蕆) 3지국 | 2026-05-06 | 弘益人間*
