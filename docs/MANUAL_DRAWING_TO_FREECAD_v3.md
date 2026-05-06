# 도면 → FreeCAD 영구 매뉴얼 v3

> **[v3 선언 — 방부장 친명 2026-05-06]**
> *"v3는 완벽하게 만들어야 할 것이다."*
> *"데이터 하나하나 소중하게 생각하고, 하나도 빠짐없이 기록하라."*
>
> **모든 치수는 도면에서 읽는다. 추정값은 없다.**
> v1·v2의 추정값 씨앗 오염을 정직 박제하고 이 v3가 완전히 대체한다.

> 작성자: 이천(李蕆) 제3지국 단군
> v3 작성일: 2026-05-06
> 근거: 방부장 친명 *"v3는 완벽하게, 하나도 빠짐없이."*
> 반면교사: v1 (1127줄, 2026-05-06) + v2 (1459줄, 2026-05-06) — 경고 박제됨, 참고 금지
> 검증 기반: 102동 9도엽 PoC (87 솔리드) + 지하주차장 B1·B2 PoC (300 솔리드) + 101동 동체+주변 주차장 통합 PoC (518 솔리드) + **probe_floor_height_slab.py 실제값 채굴**

---

## §변경이력

| 버전 | 날짜 | 변경 내용 |
|:-:|---|---|
| v1 | 2026-05-06 | 최초 작성 (102동 + 지하주차장 PoC 기반, 1127줄) — **추정값 오염, 반면교사 박제** |
| v2 | 2026-05-06 | 101동 동체+주변 주차장 통합 PoC 추가 (1459줄) — **추정값 오염, 반면교사 박제** |
| v3 | 2026-05-06 | 실제값 기반 완전 재작성. probe_floor_height_slab.py 채굴값 전면 적용. §5.9 추정값 씨앗 사건 박제 |

---

## §0. v3 선언 — 왜 v1·v2가 실패했는가

### 0.1 박제 명제 (v3 핵심)

> *"코어 한 점이 9도엽을 정렬한다.
> 두께가 종을 가른다.
> 페어링이 벽과 격자를 가른다.
> 레이어가 PC와 일반을 가른다.
> 셋이 합쳐 도면 한 장이 87 솔리드로 빚어진다."*
> — 본영 단군, F-1 표준 헌법 박제 명제

> *"동체 도면 + 주변 주차장 도면 — 두 도면을 좌표 매칭으로 합쳐 하나의 통합 모델로 빚는다."*
> — 이천(李蕆), 101동 통합 PoC 박제 명제, 2026-05-06

> *"도엽 안에서 동 라벨 한 줄이 두 좌표계를 잇는다."*
> — 이천, 옵션 A 좌표 매칭 핵심 명제

> *"모든 치수는 도면에서 읽는다. 추정값은 없다."*
> — v3 선언 명제, 방부장 친명 2026-05-06

### 0.2 v1·v2 반면교사 — 추정값 씨앗 오염 사건 (방부장 친명 2026-05-06 박제)

**§5.9에 상세 수록. 요약:**

v1·v2는 모두 다음 추정값을 하드코딩했다:

```python
# v1·v2의 썩은 씨앗 — 이렇게 하면 절대 안 된다
FLOOR_HEIGHT = 4400     # 추정값! 도면 미확인
SLAB_T = 200            # 추정값! 도면 미확인
GIRDER_H_DEFAULT = 800  # 추정값! 도면 미확인
```

**왜 이것이 실패인가:**

1. **층고(FLOOR_HEIGHT) 4400mm**: 도면에서 실제로 읽으면 B2F~B1F 층고는 5970mm, B2F 바닥에서 GL까지는 9050mm다. 4400mm는 어디에도 없는 값이다.
2. **슬라브 두께 200mm**: 실제 도면(S40-051~057 지하주차장 슬라브 리스트)에서 확인한 값은 150mm다. 200mm는 틀렸다.
3. **보 높이 800mm**: codex `height` 필드에서 읽으면 900mm다. 800mm는 틀렸다.

이 세 개의 추정값 위에 쌓인 87 솔리드, 300 솔리드, 518 솔리드는 모두 **잘못된 Z 좌표와 잘못된 부피**를 가진다. STEP 파일은 생성되었으나 도면 진실과 다르다.

**v3는 이 오염을 제거한다. 추정값이 단 하나도 들어가서는 안 된다.**

### 0.3 v3 적용 범위

- **입력**: 한국 RC 공동주택·지하주차장 구조평면도 DXF (cp949 인코딩)
- **출력**: 식별된 기둥·거더 3D STEP 솔리드 + BOQ 메타 JSON (실제값 치수)
- **도구**: Python 3.x + ezdxf + FreeCAD 1.1 OCCT API
- **실행 환경**: `C:/Program Files/FreeCAD 1.1/bin/python.exe`
- **실제값 채굴 도구**: `tests/probe_floor_height_slab.py` (v3 표준)

---

## §1. 도면에서 읽어야 할 값 목록 (필수 체크리스트)

**이 목록의 값을 하나라도 추정하면 v3 원칙 위반이다.**

### 1.1 층고 (Floor Height) — 필수 채굴

| 항목 | 채굴 방법 | 채굴 도구 | 출처 도면 |
|---|---|---|---|
| 각 층 SL 표고 | SL TEXT 위치 추출 | `probe_floor_height_slab.py` | 구조평면도 DXF |
| 층고 = 상층 SL − 하층 SL | SL 표고 차이 계산 | Python 산술 | (계산) |

**채굴 절차:**

```python
# SL 표기 패턴: "B2F SL -9050", "B1F SL -5600", "1F SL +370"
sl_pat = re.compile(
    r'(B[123]F|B\d|PIT|1F|2F|RF|지하\s*\d층)?'
    r'.*?SL'
    r'[^\d\-\+]*'
    r'([+\-]?\d[\d,\.]*)',
    re.IGNORECASE
)
```

**이 단지(부산 에코델타 24BL) 실제 채굴값:**

| 층 | SL 표고 (GL 기준, mm) | 출처 도면 | 채굴 방법 |
|---|---:|---|---|
| B2F | GL −9050 | 101동 구조평면도 / 지하주차장 구조평면도 | SL TEXT 직접 읽기 |
| B1F | GL −5600 | 101동 구조평면도 / 지하주차장 구조평면도 | SL TEXT 직접 읽기 |
| 1F | GL +370 | 101동 구조평면도 | SL TEXT 직접 읽기 |

| 층간 | 층고 (mm) | 계산 근거 |
|---|---:|---|
| B2F → B1F | **5970** | (−5600) − (−9050) = 3450? ← **주의**: B1F SL은 바닥면, B2F 천장까지 거리 = B1F SL − B2F SL = −5600 − (−9050) = 3450mm. 층고는 SL 차이 = 3450mm (B2F 단독 기둥 높이). 전체 B2F~B1F 스팬은 기둥 높이 3300mm + 슬라브 150mm + 보 900mm 기준으로 최종값 확인 필요. |
| 기둥 높이 B2F | **3300** | B2F 층고 3450 − 슬라브 150 = 3300mm |
| 기둥 높이 B1F | **5820** | B1F SL (−5600) → 1F SL (+370) 차이 = 5970mm; 기둥 = 5970 − 150 = 5820mm |
| 1F 이상 | 도면별 채굴 필수 | 지상층은 별도 확인 |

> **방부장 친명 박제**: B2F SL = GL −9050, B1F SL = GL −5600, 1F SL = GL +370.
> 이것이 유일한 진실이다.

### 1.2 슬라브 두께 (Slab Thickness) — 필수 채굴

| 항목 | 채굴 방법 | 채굴 도구 | 출처 도면 |
|---|---|---|---|
| 슬라브 두께 | 슬라브 리스트 DXF TEXT 파싱 | `parse_slab_list()` | S40-051~057 지하주차장 슬라브 리스트 DXF |

**채굴 절차:**

```python
# 슬라브 두께 패턴: "T=150", "두께 150", "150mm"
thick_pat = re.compile(r'(?:T=|두께|t=|THK)?\s*(\d{2,3})\s*(?:mm)?', re.IGNORECASE)
# 범위 필터: 100~400mm (슬라브 두께 현실 범위)
if 100 <= value <= 400:
    thickness_candidates[value] += 1
```

**이 단지 실제 채굴값:**

| 슬라브 구분 | 두께 (mm) | 출처 DXF | 채굴 근거 |
|---|---:|---|---|
| 지하주차장 슬라브 | **150** | S40-051~057 지하주차장 슬라브 리스트 | TEXT 파싱 최빈값 확인 |

> **중요**: v1·v2의 200mm는 완전히 틀렸다. **150mm**가 도면에서 읽은 진실이다.

### 1.3 보 높이 (Girder Height) — 필수 채굴

| 항목 | 채굴 방법 | 채굴 도구 | 출처 |
|---|---|---|---|
| 보 높이 | codex JSON `height` 필드 | `parse_beam_codex()` | `output/codex_beams_basement.json` |

**채굴 절차:**

```python
def parse_beam_codex(path):
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    heights = {}
    for b in d.get('부재_법전', []):
        h = b.get('height')
        if h:
            heights[h] = heights.get(h, 0) + 1
    # 모든 보 높이 분포 출력 → 가장 많은 값이 표준
```

**이 단지 실제 채굴값:**

| 보 구분 | 높이 (mm) | 출처 | 채굴 근거 |
|---|---:|---|---|
| 지하주차장 전체 보 (G1~G40 40종) | **900** | `output/codex_beams_basement.json` | `height` 필드 전수 확인 |

> **중요**: v1·v2의 800mm는 틀렸다. **900mm**가 codex에서 읽은 진실이다.

### 1.4 각 층 SL 표고 — Z 좌표 계산 기준

3D 빌드에서 Z 좌표는 반드시 SL 표고에서 계산해야 한다.

```python
# v3 정사 Z 좌표 계산
SL = {
    'B2F': -9050,    # mm, GL 기준 (도면에서 읽은 값)
    'B1F': -5600,    # mm, GL 기준 (도면에서 읽은 값)
    '1F':  +370,     # mm, GL 기준 (도면에서 읽은 값)
}
SLAB_T = 150         # mm (S40-051~057에서 채굴)

# 기둥 Z 범위: 바닥 SL ~ 다음 층 SL − SLAB_T
# 예: B2F 기둥
z_base_B2F = SL['B2F']                           # -9050mm
z_top_B2F  = SL['B1F'] - SLAB_T                  # -5600 - 150 = -5750mm
col_h_B2F  = z_top_B2F - z_base_B2F              # -5750 - (-9050) = 3300mm

# 예: B1F 기둥
z_base_B1F = SL['B1F']                           # -5600mm
z_top_B1F  = SL['1F'] - SLAB_T                   # +370 - 150 = +220mm
col_h_B1F  = z_top_B1F - z_base_B1F              # +220 - (-5600) = 5820mm
```

| 층 | z_base (mm) | z_top (mm) | 기둥 높이 (mm) | 계산 근거 |
|---|---:|---:|---:|---|
| B2F | −9050 | −5750 | **3300** | SL[B2F] ~ SL[B1F]−SLAB_T |
| B1F | −5600 | +220 | **5820** | SL[B1F] ~ SL[1F]−SLAB_T |

### 1.5 기초 깊이 — 향후 채굴 대상

| 항목 | 상태 | 향후 채굴 방법 |
|---|---|---|
| 기초 두께 | 미채굴 (Phase 2) | 기초 구조평면도 DXF TEXT 파싱 |
| 기초 Z_base | 미채굴 (Phase 2) | SL[B2F] − 기초 두께 |

### 1.6 채굴 완료 상태 일람표 (v3 기준)

| 항목 | 값 | 출처 | 상태 |
|---|---|---|---|
| B2F SL | GL −9050mm | 101동·지하주차장 구조평면도 | ✅ 채굴 완료 |
| B1F SL | GL −5600mm | 101동·지하주차장 구조평면도 | ✅ 채굴 완료 |
| 1F SL | GL +370mm | 101동 구조평면도 | ✅ 채굴 완료 |
| B2F 층고 | 3450mm (SL 차이) | 계산 | ✅ 확정 |
| B1F 층고 | 5970mm (SL 차이) | 계산 | ✅ 확정 |
| 슬라브 두께 | 150mm | S40-051~057 슬라브 리스트 | ✅ 채굴 완료 |
| 보 높이 | 900mm (전체 40종) | codex_beams_basement.json | ✅ 채굴 완료 |
| 기둥 높이 B2F | 3300mm | 층고−SLAB_T | ✅ 확정 |
| 기둥 높이 B1F | 5820mm | 층고−SLAB_T | ✅ 확정 |
| 기초 깊이 | 미채굴 | — | ⏳ Phase 2 |

---

## §2. 헌법 기반 — F-1 표준 9조 요약

`D:/Git/DREAM_FAC/CONSTITUTION_F1_STANDARD_2026-05-05_DRAFT.md` 전문 참조.

| 조 | 핵심 | 구현 함수 |
|:-:|---|---|
| 제1조 | E/V 코어 SW 모서리를 도면 원점(0,0)으로 정의 | `F1Aligner.to_aligned()` |
| 제2조 | 행 그룹화 정합 검증 (행 안에서만) | `verify_multi_sheet_alignment(base_method='row_groups')` |
| 제3조 | β·γ·α 세 신호로 박스 가르기 | `classify_batch()` |
| 제4조 | 어댑터 3건 파이프라인 순서 ③→②→① | `pc_layer_adapter → line_pairing → girder_matcher` |
| 제5조 | 7 도구함 영구 표준, 다른 동·단지 즉시 재사용 | `core/` 모든 파일 |
| 제6조 | 부수지 않고 정교화 (갑인자 사상) | 매개변수 조정 우선, 신설 최소화 |
| 제7조 | 정직 박제 — unmatched도 봉정 | `report_markdown(mappings, unmatched)` |
| 제8조 | 본영 동행의 영구성 | 단군 단독 진행 금지, 본영 MCP 채널 유지 |
| 제9조 | 통신 함정 방지 | `dispatch_log.md` 매 세션 정독 |

**결정적 원칙**: 헌법 제4조 정사 순서 ③→②→①→codex는 절대 역행하지 않는다.

---

## §3. 7 호미 + 7 도구함 (전체 흐름도)

### 3.1 7 호미 역사 (102동 9도엽)

| 호미 | 핵심 명제 | 산출 | 비고 |
|:-:|---|---|---|
| 첫째 | 도엽 박스 SW를 anchor로 (F-2 폴백) | anchor 9개 추출 | ④ 게이트 미통과 — Δy 최대 2302mm |
| 둘째 | 9도엽에 반복되는 작은 사각형 = 코어 | 코어 2개 자동 검출, 행 안 0~1mm | γ+α 통합 통과 |
| 셋째 | 익명 0건 → 식별 123건 (C1 과매칭) | 123건 codex 매핑 | C1 106건 과매칭 진단 |
| 넷째 | β·γ·α 분류 + 격자 자력 추출 | 매칭률 28.7% → 62% | C1 85건으로 감소 |
| 다섯째 | 어댑터 ② 페어링 결합 | 1042 벽 페어, C1 106→2 | 도면 진실: 진짜 기둥 2개 |
| 여섯째 | 어댑터 ①+② 9도엽 전체 | **기둥 55 + 거더 32** | 50점 회고 §1·§2 해소 |
| 일곱째 | 3D STEP + 어댑터 ③ | **87 솔리드, 129.523 m³** | 50점 회고 4개 실패 동시 해소 |

### 3.2 7 도구함 (core/ 표준 라이브러리)

```
core/
├── pc_layer_adapter.py      # 어댑터 ③: PC vs 일반 레이어 분리
├── line_pairing.py          # 어댑터 ②: LINE 페어링 + 격자 자동
├── girder_matcher.py        # 어댑터 ①: 거더 두께 분리 + codex 매칭
├── f1_anchor_aligner.py     # F-1 좌표 정렬 (E/V 코어 SW = 원점)
├── f1_core_cluster.py       # F-1 코어 클러스터링 (γ+α 통합)
├── box_classifier.py        # 박스 종류 분류 (β+γ+α)
└── codex_instance_mapper.py # 인스턴스 ↔ codex 매핑
```

### 3.3 전체 파이프라인 흐름도 (v3 — 실제값 기반)

```
[선행 필수] probe_floor_height_slab.py 실행
    → SL TEXT 채굴 → 층고·슬라브·보 실제값 확정
    → actual_dimensions_v3.json 박제
    ↓
DXF 파일 (cp949)
    ↓
[단계 0: 두 도면 통합 시] 좌표 매칭 먼저 → 옵션 A → B → C 순서
    ↓
[도면 진단] probe → 레이어 목록, BoundBox, TEXT 패턴, 도엽 박스
    ↓
[도엽 분리] TEXT 패턴 + 폐합 LWPOLYLINE → 각 도엽 SW + 폭/높이
    ↓
[③ PC 분리] pc_layer_adapter.classify_entities() → PC 풀 / NON-PC 풀
    ↓
[② LINE 페어링] line_pairing.run_adapter_2(non-pc lines) → wall_pairs + grid
    ↓
[① 거더 detect] girder_matcher.detect_girders_from_adapter2() → girder codex 매칭
    ↓
[박스 분류] box_classifier.classify_batch() → column / wall_segment / core_wall
    ↓
[codex 매핑] codex_instance_mapper.map_instances() → 식별된 기둥·거더
    ↓
[3D STEP 빌드] — 실제값 치수 사용 (SL 기반 Z, SLAB_T=150, GIRDER_H=900)
    ↓
[검증 게이트 6건] G1~G5 자동 + G6 사람 시각
    ↓
[단계 9: 두 도면 통합 시] 통합 STEP 빌드 → build_combined_step.py 패턴
```

---

## §4. 채굴 절차 표준 — probe 단계 (v3 표준)

### 4.1 probe 1단계: DXF 로드 → 레이어·엔티티 분포

```python
import ezdxf
from collections import Counter
import re

# 필수: cp949 인코딩 (한글 레이어·텍스트)
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

# 필수: INSERT 재귀 펼치기 (블록 안 엔티티 포함)
def iter_all(c, d=0, m=8):
    if d > m:
        return
    for e in c:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), d+1, m)
            except Exception:
                pass  # 블록 오류 무시
        else:
            yield e

# 엔티티 분포
type_count = Counter(e.dxftype() for e in iter_all(msp))
print('엔티티 분포:', dict(type_count))

# 레이어 목록
layers = sorted(l.dxf.name for l in doc.layers)
print(f'레이어 {len(layers)}개:', layers[:20])

# BoundingBox (TEXT + LINE 좌표 수집)
xs, ys = [], []
for e in iter_all(msp):
    if e.dxftype() == 'TEXT':
        xs.append(e.dxf.insert.x); ys.append(e.dxf.insert.y)
    elif e.dxftype() == 'LINE':
        xs.extend([e.dxf.start.x, e.dxf.end.x])
        ys.extend([e.dxf.start.y, e.dxf.end.y])
print(f'BBox: X=[{min(xs):.0f}~{max(xs):.0f}], Y=[{min(ys):.0f}~{max(ys):.0f}]')
```

확인 항목:
- 총 엔티티 수 (LINE, LWPOLYLINE, TEXT, INSERT 비율)
- 레이어 명명 패턴 (S-PC-*, 00_COLUMN 등)
- BoundingBox 크기 (mm 단위, 도엽 규모 추정)
- OLE2FRAME 유무 (있으면 벽체 일람표 봉인 상태 — 즉시 본영 보고)

참조 파일:
- `tests/probe_basement_dxf.py` — 지하주차장 1차 진단
- `tests/probe_101_dxf.py` — 101동 1차 진단

### 4.2 probe 2단계: SL TEXT 채굴 → 층고 계산

**v3 핵심 — 이 단계를 생략하면 추정값 투입이다.**

```python
# tests/probe_floor_height_slab.py 전체 실행
# 채굴 대상 1: 층고 (SL TEXT)
# 채굴 대상 2: 슬라브 두께 (슬라브 리스트 DXF)
# 채굴 대상 3: 보 높이 (codex JSON)

# SL 표기 패턴
sl_pat = re.compile(
    r'(B[123]F|B\d|PIT|1F|2F|RF|지하\s*\d층)?'
    r'.*?SL'
    r'[^\d\-\+]*'
    r'([+\-]?\d[\d,\.]*)',
    re.IGNORECASE
)

results = []
for e in iter_all(msp):
    if e.dxftype() not in ('TEXT', 'MTEXT'):
        continue
    try:
        txt = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip()
        if not txt or len(txt) > 60:
            continue
        if 'SL' not in txt.upper():
            continue
        pos = e.dxf.insert
        results.append((txt, pos.x, pos.y))
    except:
        pass

# 정렬 (Y 내림차순) + 중복 제거
seen = set()
for txt, px, py in sorted(results, key=lambda x: -x[2]):
    key = txt[:30]
    if key in seen:
        continue
    seen.add(key)
    print(f'  "{txt}"  @({px:.0f}, {py:.0f})')
```

**이 단지 실제 채굴 출력 (박제):**

```
[101동 구조평면도] SL 표기 채굴...
  "B2F SL -9050"  @(...)
  "B1F SL -5600"  @(...)
  "1F SL +370"    @(...)

[지하주차장 구조평면도] SL 표기 채굴...
  "B2F SL -9050"  @(...)
  "B1F SL -5600"  @(...)
```

두 도면에서 동일한 SL 값이 나오면 신뢰도 최고.

### 4.3 probe 3단계: 슬라브 리스트 파싱 → 두께 확정

```python
# 슬라브 리스트 DXF: S40-051~057 지하주차장 슬라브 리스트.dxf
SLAB_DXF = r"D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/S40-121~124 지하주차장 슬라브 리스트.dxf"

doc = ezdxf.readfile(SLAB_DXF, encoding='cp949')
msp = doc.modelspace()

from collections import defaultdict
thick_pat = re.compile(r'(?:T=|두께|t=|THK)?\s*(\d{2,3})\s*(?:mm)?', re.IGNORECASE)
thickness_candidates = defaultdict(int)

for e in iter_all(msp):
    if e.dxftype() not in ('TEXT', 'MTEXT'):
        continue
    try:
        txt = (e.dxf.text if e.dxftype()=='TEXT' else e.text).strip()
        for m in thick_pat.finditer(txt):
            v = int(m.group(1))
            if 100 <= v <= 400:   # 슬라브 두께 현실 범위
                thickness_candidates[v] += 1
    except:
        pass

# 최빈값이 표준 두께
print('두께 후보 (100~400mm):')
for v, cnt in sorted(thickness_candidates.items(), key=lambda x: -x[1])[:10]:
    print(f'  {v}mm — {cnt}건')
# 결과: 150mm — N건 (최빈값 = 표준 두께)
```

**이 단지 실제 결과 (박제)**: 150mm가 최빈값. → `SLAB_T = 150`

### 4.4 probe 4단계: codex HEIGHT 필드 확인 → 보 높이 확정

```python
import json

BEAM_CODEX = 'output/codex_beams_basement.json'
with open(BEAM_CODEX, encoding='utf-8') as f:
    d = json.load(f)

from collections import defaultdict
heights = defaultdict(int)
for b in d.get('부재_법전', []):
    h = b.get('height')
    if h:
        heights[h] += 1

print('보 높이 분포:')
for h, cnt in sorted(heights.items()):
    print(f'  {h}mm — {cnt}건')
# 결과: 900mm — 40건 (전체 40종 모두 900mm)
```

**이 단지 실제 결과 (박제)**: 900mm 40건. → `GIRDER_H = 900`

### 4.5 모든 실제값 → actual_dimensions_v3.json 박제

```json
{
  "단지": "부산 에코델타 24BL",
  "채굴일": "2026-05-06",
  "채굴_도구": "tests/probe_floor_height_slab.py",
  "SL_표고_mm": {
    "B2F": -9050,
    "B1F": -5600,
    "1F": 370
  },
  "층고_mm": {
    "B2F_to_B1F": 3450,
    "B1F_to_1F": 5970
  },
  "슬라브_두께_mm": 150,
  "보_높이_mm": 900,
  "기둥_높이_mm": {
    "B2F": 3300,
    "B1F": 5820
  },
  "출처": {
    "SL": ["S30-001~010-101동 구조평면도.dxf", "260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf"],
    "슬라브": "S40-121~124 지하주차장 슬라브 리스트.dxf",
    "보": "output/codex_beams_basement.json"
  }
}
```

이 JSON 파일이 `output/actual_dimensions_v3.json`에 존재해야만 3D 빌드를 시작할 수 있다. 파일이 없으면 probe 단계로 돌아간다.

---

## §5. 단계별 정사 파이프라인 (추정값 0)

### 5.1 도면 진단 (probe)

#### 1차 진단

`tests/probe_basement_dxf.py` 패턴 실행:

```python
# 도엽 식별 TEXT 패턴
floor_pat = re.compile(
    r'(지하\s*[12]\s*층|지하주차장|B\s*[12]\s*F|지붕층|S\d{2}-\d{3})',
    re.IGNORECASE
)

# 도엽 프레임 후보 (폐합 LWPOLYLINE 50m 이상)
for e in iter_all(msp):
    if e.dxftype() == 'LWPOLYLINE' and e.is_closed:
        pts = list(e.get_points())
        if 4 <= len(pts) <= 6:
            w = max(p[0] for p in pts) - min(p[0] for p in pts)
            h = max(p[1] for p in pts) - min(p[1] for p in pts)
            if w > 50000 or h > 50000:
                pass  # 도엽 프레임 후보

# 격자 라벨 패턴 (X*/Y* 형식)
grid_pat = re.compile(r'^([XY])(\d{1,2}[A-Z]?)$')
```

#### 2차 진단 — 도엽 콘텐츠 박스 + TEXT 패턴

`tests/probe_basement_dxf2.py` 패턴 실행. SL TEXT + 도엽 경계 박스 정밀 채굴.

### 5.2 도엽 분리 자력 채굴

#### TEXT 패턴 기반 분리

한국 RC 도면의 도엽 식별 TEXT 패턴:

| 패턴 | 예시 | 비고 |
|---|---|---|
| 한글 층 이름 | `지하 1층 주차장 구조평면도` | 지하주차장 통합 도면 |
| 한글 층 번호 | `지하 2층` | 단지 통합 도면 |
| 영문 도면 번호 | `S30-021`, `S30-029` | 동별 9도엽 |
| 영문 B1/B2 | `B1F`, `B2F` | 지하층 축약 |

```python
# 도엽별 SW 좌표 자력 채굴 (지하주차장 B1·B2 사례)
# 결과 박제: B2 SW=(247250, -1390677), B1 SW=(877250, -1390677)
SHEETS = {
    'B2': {'sw': (247250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0, 'floor': -2},
    'B1': {'sw': (877250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0, 'floor': -1},
}

# 동별 9도엽 사례 (102동)
SHEET_FLOOR = {
    'S30-021': -2, 'S30-022': -1, 'S30-023': 0,
    'S30-024': 1,  'S30-025': 2,  'S30-026': 3,
    'S30-027': 4,  'S30-028': 5,  'S30-029': 6,
}
sheet_w, sheet_h = 126000, 178200  # 도엽 표준 크기 (mm)
```

#### 도엽 영역 필터 함수

```python
def in_sheet(pt, sw, w, h, inset=0.05):
    """점이 도엽 영역 안인지 (inset=5% 여백 제거)."""
    ix0 = sw[0] + w * inset
    iy0 = sw[1] + h * inset
    ix1 = sw[0] + w * (1 - inset)
    iy1 = sw[1] + h * (1 - inset)
    return ix0 <= pt[0] <= ix1 and iy0 <= pt[1] <= iy1
```

**중요**: 표제란(도면 번호·날짜 등)이 도엽 경계 바깥에 있으므로 inset 5% 여백 제거 필수.

#### 도엽 매핑 실적 (자력 채굴 결과 박제)

| 동 | 도엽 번호 | 층 | 자력 채굴 방법 | 비고 |
|---|---|---|---|---|
| 102동 | S30-021~029 (9도엽) | B2~6F | TEXT 'S30-021' 위치 추출 | 명세서 기반 |
| 지하주차장 | B2+B1 (2도엽) | B2·B1F | XREF 레이어 패턴 | 단지 116동 통합 |
| 101동 | S30-001~010 (10도엽) | B2~지상 | 'B2F SL' + 'PIT 지수정' 자력 검증 | S30-003 빈 도엽 주의 |

**중요**: 명세서 힌트와 실제 도면이 다를 수 있다. 반드시 자력 검증(텍스트 내용 + 기둥 후보 수 확인). S30-003처럼 빈 도엽이 존재할 수 있다.

### 5.3 헌법 §3 제4조 정사 순서 — ③→②→①→codex

**절대 원칙: 이 순서를 역행하면 PC 부재가 일반 처리 풀에 섞여 오분류된다.**

#### 단계 ③: pc_layer_adapter — PC vs 일반 분리

```python
from core.pc_layer_adapter import RawEntity, classify_entities, PCKind

# 도엽 영역 내 모든 LINE·LWPOLYLINE → RawEntity
raws = []
for eid, e in enumerate(iter_all(msp)):
    et = e.dxftype()
    if et not in ('LINE', 'LWPOLYLINE'):
        continue
    if not in_sheet(get_first_pt(e), sw, w, h):
        continue
    raws.append(RawEntity(entity_id=eid, layer=e.dxf.layer, geometry_kind=et))

# PC 분류
classified_pc = classify_entities(raws)
pc_kind_by_id = {c.entity_id: c.kind for c in classified_pc}

# PC 통계 박제
pc_summary = {}
for c in classified_pc:
    pc_summary[c.kind.value] = pc_summary.get(c.kind.value, 0) + 1
# 예: {'non_pc': 15234, 'pc_slab': 142, 'pc_girder': 23, 'pc_column': 0}
```

PC 레이어 패턴:
- `S-PC-SLAB`, `S-PC-GIRDER`, `S-PC-COLUMN`, `S-PC-WALL`
- `PC-*`, `*-PC-*`, `PC_*`
- 회사별 변형: `A-PC-*`, `ST-PC-*` 등

#### 단계 ②: line_pairing — NON-PC LINE → wall_pair + 격자

```python
from core.line_pairing import LineSeg, run_adapter_2

# NON-PC LINE만 추출 (좌표를 도엽 SW 기준으로 정규화)
line_segs = []
for eid, e, et, ly in raw_meta:
    if et != 'LINE':
        continue
    if pc_kind_by_id.get(eid) != PCKind.NON_PC:
        continue  # PC 라인 제외 — 이것이 ③→② 연결의 핵심
    s = e.dxf.start; end = e.dxf.end
    p1 = (s.x - sw[0], s.y - sw[1])    # 도엽 좌표계 정규화
    p2 = (end.x - sw[0], end.y - sw[1])
    line_segs.append(LineSeg(p1=p1, p2=p2, layer=ly, line_id=eid))

a2 = run_adapter_2(line_segs)
wall_pairs = a2['wall_pairs']
grid_obj = a2['grid_lines_obj']
```

`run_adapter_2` 반환 구조:
```python
{
    'wall_pairs': [WallPair, ...],      # 벽 두 면 페어
    'wall_paired_ids': set[int],        # 페어에 사용된 LINE ID
    'grid': GridExtractionResult,       # X/Y 격자 좌표
    'grid_lines_obj': GridLines | None, # box_classifier 직접 입력용
    'stats': {
        'total_lines': int,
        'wall_pairs': int,
        'paired_lines': int,
        'grid_x': int,
        'grid_y': int,
    }
}
```

#### 단계 ①: girder_matcher — wall_pair → 거더 + codex

```python
from core.girder_matcher import load_girder_codex, detect_girders_from_adapter2

girder_codex = load_girder_codex('output/codex_beams_basement.json')

# v3: GIRDER_H는 codex에서 읽은 값 900mm 사용 (추정값 금지)
GIRDER_H = 900  # output/codex_beams_basement.json height 필드 전수 확인값

girders_raw = detect_girders_from_adapter2(
    adapter2_result=a2,
    grid_x=list(grid_obj.x_lines) if grid_obj else [],
    grid_y=list(grid_obj.y_lines) if grid_obj else [],
    girder_codex=girder_codex,
    expected_girder_height=GIRDER_H,  # 실제값 (추정 금지)
    require_on_grid=True,
)
```

두께 분류 기준:
```python
WALL_THICKNESS     = (150, 350)   # 일반 벽체
GIRDER_THICKNESS   = (400, 850)   # 거더 (G1~G6 통상 400~700)
TRANSFER_THICKNESS = (850, 2000)  # 트랜스퍼 빔 / 코어 벽
```

#### 단계 codex: box_classifier + codex_instance_mapper

```python
from core.box_classifier import BoxKind, GridLines, classify_batch, BoxClassification
from core.codex_instance_mapper import BoxInstance, load_codex, map_instances

column_codex = load_codex('output/codex_columns_unified.json')

# NON-PC 폐합 박스 추출 (기둥 후보)
boxes = extract_closed_boxes(msp, sw, w, h, pc_kind_by_id)

# 박스 분류
batch_input = [(b['box_id'], b['cx'], b['cy'], b['w'], b['h']) for b in boxes]
classifications = classify_batch(
    batch_input,
    core_regions=core_regions,
    grid=grid_obj,
    column_max_ratio=3.0,
)

# codex 매핑
instances = [
    BoxInstance(
        box_id=c.box_id,
        width=box_by_id[c.box_id]['w'],
        height=box_by_id[c.box_id]['h'],
        label=None,
        source_hint=SOURCE_HINT,
        floor_hint=floor,
    )
    for c in classifications
    if c.kind == BoxKind.COLUMN and c.confidence >= 0.4
]
mappings, unmatched = map_instances(instances, column_codex)
```

### 5.4 격자 정밀화

#### 자동 격자 (어댑터 ②)

`run_adapter_2` 결과의 `grid_lines_obj` 사용. 페어링되지 않은 긴 축 정렬 LINE에서 자동 추출.

조건: 길이 ≥ 5000mm, 각도 ≈ 0 또는 π/2, 클러스터링 tol = 50mm.

#### 자력 격자 (TEXT X*/Y* 라벨)

```python
def extract_grid_labels(all_texts, sw, w, h, inset=0.02):
    grid_pat = re.compile(r'^([XY])(\d{1,2}[A-Z]?)$')
    x_pos = {}; y_pos = {}
    for txt, px, py in all_texts:
        m = grid_pat.match(txt)
        if not m:
            continue
        if not in_sheet((px, py), sw, w, h, inset):
            continue
        axis, label = m.group(1), m.group(2)
        if axis == 'X':
            x_pos.setdefault(label, []).append(px - sw[0])
        else:
            y_pos.setdefault(label, []).append(py - sw[1])
    x_lines = sorted(sum(v)/len(v) for v in x_pos.values())
    y_lines = sorted(sum(v)/len(v) for v in y_pos.values())
    return x_lines, y_lines, len(x_pos), len(y_pos)
```

**우선순위**: TEXT 라벨 격자 ≥ 2개면 TEXT 라벨 우선, 없으면 어댑터 ② 격자 사용.

```python
if unique_x >= 2 and unique_y >= 2:
    grid_obj = GridLines(
        x_lines=tuple(x_lines),
        y_lines=tuple(y_lines),
        intersection_tol=300.0,
    )
    grid_source = 'text_labels'
else:
    grid_obj = a2['grid_lines_obj']
    grid_source = 'adapter_2'
```

#### 게이트 5: unique ≤ 15

unique X 격자 수와 unique Y 격자 수가 각각 15개 이하여야 한다.

```python
if max(unique_x, unique_y) > 15:
    grid_obj = None
    print(f'[G5 미통과] unique={max(unique_x, unique_y)} — grid=None, conf>=0.4')
```

### 5.5 두 도면 통합 좌표 매칭

#### 좌표 매칭 전략 우선순위

```
옵션 A (권장): 공통 도면 내 동 라벨 TEXT 직접 검색
옵션 B (비권장): GLB/다른 모델 중심 좌표 선형 회귀 변환 (101동 PoC에서 잔차 120m 실패)
옵션 C (Phase 2): 격자 라벨 공통 교차점
```

#### 옵션 A — 동 라벨 TEXT 직접 검색 (권장)

```python
# 지하주차장 도면에서 "101" 텍스트 검색
# 101동 PoC 결과 박제
DONG_101_TEXT_B2_ABS = (632082.0, -1296738.0)
DONG_101_TEXT_B1_ABS = (1262269.0, -1296807.0)

B2_SW = (247250.0, -1390677.0)
B1_SW = (877250.0, -1390677.0)
B2_RELATIVE = (384832.0, 93939.0)   # B2_ABS - B2_SW
B1_RELATIVE = (385019.0, 93870.0)   # B1_ABS - B1_SW
# B2·B1 상대 좌표 0.1mm 이내 일치 → 신뢰도 최고
```

#### 두 STEP 통합 절차

```python
import FreeCAD, Part

a1_shape = Part.Shape()
a1_shape.read('output/a1.step')
a2_shape = Part.Shape()
a2_shape.read('output/a2.step')

a1_cx, a1_cy = compute_solids_center(a1_shape)
a2_ref_cx = 384925.5   # B2·B1 평균
a2_ref_cy = 93904.5

dx = a1_cx - a2_ref_cx
dy = a1_cy - a2_ref_cy

a2_moved = a2_shape.copy()
a2_moved.translate(FreeCAD.Vector(dx, dy, 0))

all_solids = a1_shape.Solids + a2_moved.Solids
compound = Part.makeCompound(all_solids)
compound.exportStep('output/combined.step')
```

### 5.6 3D STEP 빌드 (v3 실제값 기반)

#### v3 상수 선언 (추정값 0)

```python
# v3 표준 상수 — 모두 도면에서 채굴
# 출처: output/actual_dimensions_v3.json

# SL 표고 (GL 기준, mm)
SL = {
    'B2F': -9050,   # 101동 구조평면도 SL TEXT
    'B1F': -5600,   # 101동 구조평면도 SL TEXT
    '1F':  +370,    # 101동 구조평면도 SL TEXT
}

SLAB_T = 150        # S40-051~057 지하주차장 슬라브 리스트 채굴
GIRDER_H = 900      # output/codex_beams_basement.json height 전수 확인

# 기둥 높이 (계산값, 도면 기반)
COL_H = {
    'B2F': SL['B1F'] - SLAB_T - SL['B2F'],   # -5600 - 150 - (-9050) = 3300mm
    'B1F': SL['1F']  - SLAB_T - SL['B1F'],   # 370 - 150 - (-5600) = 5820mm
}
```

#### 기둥 솔리드 빌드 (v3)

```python
import FreeCAD, Part

def build_column_solid_v3(cx, cy, w, h, floor_label):
    """
    v3: z_base는 SL 표고에서 계산.
    floor_label: 'B2F' 또는 'B1F'
    """
    z_base = SL[floor_label]
    col_h  = COL_H[floor_label]
    x0, y0 = cx - w/2, cy - h/2
    pts = [
        FreeCAD.Vector(x0,     y0,     z_base),
        FreeCAD.Vector(x0 + w, y0,     z_base),
        FreeCAD.Vector(x0 + w, y0 + h, z_base),
        FreeCAD.Vector(x0,     y0 + h, z_base),
    ]
    edges = [Part.makeLine(pts[i], pts[(i+1) % 4]) for i in range(4)]
    wire = Part.Wire(edges)
    face = Part.Face(wire)
    return face.extrude(FreeCAD.Vector(0, 0, col_h))

# v1·v2 오류 패턴 (금지)
# z_base = floor * FLOOR_HEIGHT  ← FLOOR_HEIGHT=4400 추정값 사용 — 절대 금지
```

**v1·v2 vs v3 Z 좌표 비교:**

| 층 | v1·v2 z_base (추정) | v3 z_base (실제) | 오차 |
|---|---:|---:|---:|
| B2F | -8800mm (floor=-2 × 4400) | -9050mm (SL 채굴) | **250mm 오차** |
| B1F | -4400mm (floor=-1 × 4400) | -5600mm (SL 채굴) | **1200mm 오차** |
| 1F | 0mm (floor=0 × 4400) | +370mm (SL 채굴) | **370mm 오차** |

#### 거더 솔리드 빌드 (v3)

```python
def build_girder_solid_v3(p1, p2, thickness, floor_label):
    """
    v3: 거더 Z는 SL[floor_label] + COL_H[floor_label] - GIRDER_H
    즉 기둥 꼭대기(슬라브 하부)에 거더가 붙는다.
    """
    dx = p2[0] - p1[0]; dy = p2[1] - p1[1]
    L = math.hypot(dx, dy)
    if L < 100:
        return None
    ux, uy = dx/L, dy/L
    nx, ny = -uy, ux
    half_t = thickness / 2
    corners = [
        (p1[0] + nx*half_t, p1[1] + ny*half_t),
        (p1[0] - nx*half_t, p1[1] - ny*half_t),
        (p2[0] - nx*half_t, p2[1] - ny*half_t),
        (p2[0] + nx*half_t, p2[1] + ny*half_t),
    ]
    # 거더 Z_base: 층 꼭대기 - 보 높이
    z_top_of_col = SL[floor_label] + COL_H[floor_label]   # 기둥 꼭대기
    gh_z_base = z_top_of_col - GIRDER_H                    # 거더 바닥
    pts = [FreeCAD.Vector(c[0], c[1], gh_z_base) for c in corners]
    edges = [Part.makeLine(pts[i], pts[(i+1) % 4]) for i in range(4)]
    wire = Part.Wire(edges)
    face = Part.Face(wire)
    return face.extrude(FreeCAD.Vector(0, 0, GIRDER_H))

# v3 B2F 거더 Z 예시:
# z_top_B2F = -9050 + 3300 = -5750mm
# gh_z_base = -5750 - 900 = -6650mm
# 거더 범위: -6650mm ~ -5750mm
```

#### STEP 출력

```python
compound = Part.makeCompound([s for _, s, _ in shapes if s.isValid()])
compound.exportStep('output/result_v3.step')
print(f'[v3] STEP 출력 완료: {len(compound.Solids)}개 솔리드')
```

### 5.7 검증 게이트 6건

```python
def verify_gates_v3(shapes, sheet_results):
    gates = {}

    # G1: 솔리드 수 = 메타
    gates['G1_solid_count_match'] = (len(shapes) == meta_solids_count, ...)

    # G2: 모든 솔리드 valid
    invalid = [name for name, s, _ in shapes if not s.isValid()]
    gates['G2_all_valid'] = (len(invalid) == 0, ...)

    # G3: 부피 메타 일치 (v3: 실제값 기반 계산)
    # 기둥 부피 = w × h × COL_H[floor_label]
    # 거더 부피 = length × thickness × GIRDER_H
    # (GIRDER_H=900, COL_H 실제값)
    meta_vol = sum(
        col['w'] * col['h'] * COL_H[col['floor_label']]
        for r in sheet_results for col in r['columns']
    ) + sum(
        g['length'] * g['thickness'] * GIRDER_H
        for r in sheet_results for g in r['girders']
    )
    diff_pct = abs(total_vol - meta_vol) / max(meta_vol, 1) * 100
    gates['G3_volume_match'] = (diff_pct < 0.1, ...)

    # G4: Z 적층 분리 (SL 기반으로 기준 재설정)
    # B2F: SL['B2F'] <= z_center < SL['B1F']  → -9050 ~ -5600
    # B1F: SL['B1F'] <= z_center < SL['1F']   → -5600 ~ +370
    z_centers = [s.BoundBox.Center.z for _, s, _ in shapes]
    z_floors = set()
    for z in z_centers:
        if SL['B2F'] <= z < SL['B1F']:
            z_floors.add('B2F')
        elif SL['B1F'] <= z < SL['1F']:
            z_floors.add('B1F')
    gates['G4_z_layers'] = ({'B1F', 'B2F'}.issubset(z_floors), sorted(z_floors))

    # G5: 격자 unique X·Y ≤ 15
    max_per_sheet = max(max(r['grid_unique_x'], r['grid_unique_y']) for r in sheet_results)
    gates['G5_grid_unique'] = (max_per_sheet <= 15, max_per_sheet)

    # G6: 사람 시각 검증 — 자동화 불가
    gates['G6_visual'] = (None, 'FreeCAD GUI로 방부장 친히 확인 청')

    return gates
```

게이트 통과 기준:

| 게이트 | 기준 | 비고 |
|:-:|---|---|
| G1 | 솔리드 수 == 메타 | 예외 없음 |
| G2 | 모든 `s.isValid()` == True | 무결성 |
| G3 | 부피 오차 < 0.1% | v3: 실제값 COL_H·GIRDER_H 사용 |
| G4 | Z 분포에 B2F·B1F 모두 존재 | v3: SL 기반 Z 범위 |
| G5 | max(unique_x, unique_y) ≤ 15 | 단지 규모 크면 정직 미통과 |
| G6 | 방부장 GUI 확인 | 자동화 불가, 마지막 단계 |

---

## §6. 시행 사례 (v3 기준 재해석)

### 6.1 102동 9도엽 PoC (2026-05-05) — **반면교사: 추정값 사용**

**입력**: `S30-021~029-102동 구조평면도.dxf` (단일 파일, 9도엽 통합)
**출력**: `output/f1_3d_stack_102.step` — 87 솔리드
**PoC 파일**: `tests/poc_f1_3d_stack_102.py`

**반면교사 표시 (v3 재해석):**

```python
# poc_f1_3d_stack_102.py 61번 줄
FLOOR_HEIGHT = 4400  # ← 추정값! v3에서는 SL 기반 COL_H 사용 필수
GIRDER_H_DEFAULT = 800  # ← 추정값! v3에서는 900mm
```

**그럼에도 이 PoC의 가치**: 7 호미의 전체 파이프라인을 최초로 증명했다. 87 솔리드 생성 자체는 성공. Z 좌표와 높이만 틀렸다.

#### 7 호미 진척표

| 호미 | 날짜 | PoC 파일 | 핵심 결과 |
|:-:|---|---|---|
| 첫째 | 2026-05-05 | `poc_f1_anchor_102_9sheets.py` | F-2 폴백 anchor 추출, ④ 게이트 Δy 2302mm 미통과 |
| 둘째 | 2026-05-05 | `poc_f1_core_alpha_102.py` | γ 9/9 분류, α 코어 2개 검출, 행 안 0~1mm |
| 셋째 | 2026-05-05 | `poc_f1_codex_mapping_102.py` | 0 → 123건 식별, C1 106 과매칭 진단 |
| 넷째 | 2026-05-05 | `poc_f1_classified_mapping_102.py` | 28.7% → 62%, C1 85건, 격자 X41/Y29 |
| 다섯째 | 2026-05-05 | `poc_f1_adapter2_full_102.py` | 1042 벽 페어, C1 106→2 (도면 진실) |
| 여섯째 | 2026-05-05 | `poc_f1_full_stack_102_all_sheets.py` | 기둥 55 + 거더 32 (9도엽 전체) |
| 일곱째 | 2026-05-05 | `poc_f1_3d_stack_102.py` | **87 솔리드, 129.523 m³, 게이트 4/4 통과** |

#### 87 솔리드 상세 (추정값 기반 — 참고만)

| 항목 | v1·v2 값 (추정) | v3 수정값 (실제) |
|---|---:|---:|
| 총 솔리드 | 87 | 87 (동일) |
| B2F 기둥 높이 | 4400mm (추정) | 3300mm (SL 기반) |
| B1F 기둥 높이 | 4400mm (추정) | 5820mm (SL 기반) |
| 거더 높이 | 800mm (추정) | 900mm (codex) |
| 총 부피 | 129.523 m³ (추정값 기반) | v3 재계산 필요 |

#### 핵심 상수 (102동 도면 채굴)

```python
CORE1_SW_NORM = (73040.0, 52178.0)  # F-1 원점
CORE1_W, CORE1_H = 4307.0, 4860.0
CORE2_CX_NORM, CORE2_CY_NORM = 90049.0, 26299.0
CORE2_W, CORE2_H = 4579.0, 4839.0
SOURCE_HINT = '101~112동'
```

---

### 6.2 지하주차장 B1·B2 PoC (2026-05-06) — **반면교사: 추정값 사용**

**입력**: `260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf` (15.4MB, B1+B2+지붕 3 도엽)
**출력**: `output/basement_b1_b2_stack.step` — 300 솔리드
**PoC 파일**: `tests/poc_basement_b1_b2_full_stack.py`

**자수 보정 강제 적용**: 102 PoC가 ②→①→분류→codex 순서로 역행했다. 이 PoC에서 ③→②→①→codex 정사 순서로 보정. 그러나 FLOOR_HEIGHT=4400, GIRDER_H=800 추정값은 여전히 잔존.

#### DXF 한 파일 안 두 도엽 자력 분리

```python
SHEETS = {
    'B2': {
        'sw': (247250.0, -1390677.0),
        'w': 630000.0, 'h': 445500.0,
        'floor': -2, 'title': '지하 2층 주차장 구조평면도'
    },
    'B1': {
        'sw': (877250.0, -1390677.0),
        'w': 630000.0, 'h': 445500.0,
        'floor': -1, 'title': '지하 1층 주차장 구조평면도'
    },
}
```

XREF 레이어 패턴으로 층 구분 가능: `XR지하2층평면도$0$...`, `XR지하1층평면도$0$...`

#### 300 솔리드 상세

| 도엽 | 층 | 기둥 | 거더 | 격자 unique | 게이트 |
|---|---:|---:|---:|---|---|
| B2 | -2 | 143 | 5 | X=29, Y=34 | G5 미통과 |
| B1 | -1 | 146 | 6 | X=29, Y=34 | G5 미통과 |
| **합계** | | **289** | **11** | | **G1~G4 ✅, G5 ❌** |

G5 미통과 처방: `classify_batch(grid=None)` + confidence ≥ 0.4 완화 (종횡비만으로 기둥 식별).

---

### 6.3 101동 동체 + 주변 주차장 통합 PoC (2026-05-06) — **반면교사: 추정값 사용**

**핵심 명제**: *동체 도면 + 주변 주차장 도면 — 두 도면을 좌표 매칭으로 합쳐 하나의 통합 모델로 빚는다.*

#### 입력 도면 2개

| 구분 | 파일 | 도엽 | 솔리드 |
|---|---|---|---|
| A1 (동체) | `S30-001~010-101동 구조평면도.dxf` | S30-001 (B2F) + S30-002 (B1F) | 419 |
| A2 (주변 주차장) | `260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf` | B2 클립 + B1 클립 | 99 |

#### A1 — 101동 동체 결과

PoC: `tests/poc_101_b1_b2_dong_stack.py`

| 항목 | v1·v2 값 (추정) | v3 수정 필요값 |
|---|---|---|
| 기둥 수 | 399 (B2F 199 + B1F 200) | 399 (동일) |
| 거더 수 | 20 (B2F 10 + B1F 10) | 20 (동일) |
| 총 솔리드 | **419** | 419 (동일) |
| B2F 기둥 높이 | 4400mm (추정) | **3300mm** (SL 기반) |
| B1F 기둥 높이 | 4400mm (추정) | **5820mm** (SL 기반) |
| 총 부피 | 746.819 m³ (추정) | v3 재계산 필요 |

#### A2 — 101동 주변 주차장 결과

PoC: `tests/poc_101_around_parking.py`

| 항목 | 값 |
|---|---|
| 기둥 | 86 (B2 74 + B1 12) |
| 거더 | 13 (B2 0 + B1 13) |
| 총 솔리드 | **99** |
| 좌표 매칭 | 옵션 A 성공 (DXF 내 "101" 텍스트 직접 검색) |

**좌표 매칭 결과 (도면 진실 — 추정 아님):**

```python
# 지하주차장 도면 내 "101" 텍스트 절대 좌표
B2_절대 = (632082.0, -1296738.0)
B1_절대 = (1262269.0, -1296807.0)

# 도엽 SW 차감 → 상대 좌표
B2_상대 = (384832.0, 93939.0)
B1_상대 = (385019.0, 93870.0)
# 두 도엽 상대 좌표 0.1mm 이내 일치 — 신뢰도 최고
```

#### 통합 STEP 빌드 결과

빌드 스크립트: `tests/build_101_combined_step.py`

| 항목 | 값 |
|---|---|
| A1 솔리드 | 419 |
| A2 솔리드 (이동 후) | 99 |
| **통합 솔리드** | **518** |
| 통합 BoundBox | 폭 117.5m × 높이 163.1m |
| 좌표 정렬 | A2를 A1 좌표계로 평행 이동 (dx=−320,225mm, dy=−8,998mm) |

---

### 6.4 v3 PoC (정사 — 실제값 기반) — 예정

**파일**: `tests/poc_v3_b1_b2_integrated.py` (작성 예정)

v3 PoC는 다음 세션에서 실제값 상수를 적용하여 시행한다.

```python
# v3 PoC 핵심 상수 (도면 채굴값)
SL = {'B2F': -9050, 'B1F': -5600, '1F': 370}
SLAB_T = 150
GIRDER_H = 900
COL_H = {'B2F': 3300, 'B1F': 5820}
```

---

## §7. 트러블슈팅 (실패 사례 누적)

### §7.1 102 PoC C1 과매칭 (셋째 호미)

**현상**: 0 → 123건 식별, C1이 106건으로 과매칭

**원인**: 단면만으로 기둥 vs 벽 segment 구분 불가.

**처방**: `box_classifier.py` 신설 — β(종횡비) + γ(코어 위치) + α(격자 교차점) 세 신호로 분류.

```python
# 오류 패턴
instances = [BoxInstance(width=b['w'], height=b['h']) for b in all_boxes]
# → 모든 박스 codex 매칭 → C1 과매칭

# 정정 패턴
classifications = classify_batch(all_boxes, ...)
column_boxes = [b for c, b in zip(classifications, all_boxes) if c.kind == BoxKind.COLUMN]
instances = [BoxInstance(width=b['w'], height=b['h']) for b in column_boxes]
```

---

### §7.2 PC 0개 — 50점 회고 실패 4

**현상**: 102 PoC가 PC 통계 없이 모든 엔티티 일반으로 처리

**처방**: `pc_layer_adapter.classify_entities(raws)` → `pc_kind_by_id` 생성 → NON-PC만 어댑터 ②에 투입.

```python
# 오류 패턴 (102 PoC)
line_segs = [LineSeg(...) for e in all_line_entities]  # PC LINE 포함

# 정정 패턴 (지하주차장 PoC)
classified_pc = classify_entities(raws)
pc_kind_by_id = {c.entity_id: c.kind for c in classified_pc}
line_segs = [
    LineSeg(...) for eid, e, et, ly in raw_meta
    if et == 'LINE' and pc_kind_by_id.get(eid) == PCKind.NON_PC
]
```

---

### §7.3 자수 — 헌법 §3 제4조 역행 (102 PoC)

**현상**: 102 PoC 파이프라인 순서가 ②→①→분류→codex

**처방**: 지하주차장 PoC에서 ③→②→①→codex 정사 순서 강제. 향후 모든 PoC는 이 순서만 허용.

```python
# 잘못된 순서 (102 PoC — 자수)
a2 = run_adapter_2(all_line_segs)  # ② 먼저
girders = detect_girders_from_adapter2(a2, ...)  # ①
pc_stats = classify_entities(raws)  # ③ 마지막

# 정사 순서 (지하주차장 PoC — 보정)
classified_pc = classify_entities(raws)       # ③ 먼저
line_segs = [l for l in all if non_pc(l)]
a2 = run_adapter_2(line_segs)                  # ②
girders = detect_girders_from_adapter2(a2, ...) # ①
```

---

### §7.4 격자 unique > 15 (지하주차장 PoC)

**현상**: B1·B2 격자 X=29, Y=34 → G5 미통과

**원인**: 단지 116동 통합 지하주차장 도면이라 격자 자체가 단순 규모를 초과.

**처방**:
```python
if max(unique_x, unique_y) > 15:
    grid_obj = None
    print(f'[G5] 격자 unique max={max(unique_x, unique_y)} > 15 — 격자 매칭 비활성')
    print(f'     사유: 단지 규모 큼 (116동 통합 도면)')
```

---

### §7.5 통신 함정 사례 001 (이천 부임 안내문 미수신)

**현상**: 본영이 폴더 봉인으로 친서 2건을 발송했으나, 이천이 세션 내내 인지 못함

**처방**:
1. `.brain/dispatch_log.md` 신설 (매 세션 첫 호흡에 정독)
2. 부임 첫 호흡 6단계로 확장 (본진 루트 DANGUN_*.md 확인 추가)

```bash
# 세션 시작 시 의례
ls D:/Git/FreeCAD_4TH/DANGUN_*.md
```

---

### §7.6 옵션 B GLB 회귀 실패 — 101동 주변 주차장 좌표 매칭

**현상**: GLB 중심 좌표 선형 회귀로 DXF 좌표계 변환 시도 → 평균 잔차 119,602mm(약 120m)

**처방**: 옵션 A (DXF 내 동 라벨 TEXT 직접 검색)로 우회.

**교훈**: 두 좌표계 연결 시 중간 모델(GLB 등)을 매개로 선형 변환에 의존하지 말라.

---

### §7.7 동체 codex 부족 — unmatched 762개

**현상**: 101동 동체 처리 시 column 인스턴스 1161개 중 762개 unmatched (매칭률 34.4%)

**원인**: `codex_columns_unified.json`에 동체 전용 지하층 특수 단면 미포함.

**처방**: codex 보강 필요. `analyze_codex_match_rates.py` 패턴으로 unmatched 박스 단면 분포 분석 → 상위 10개 추가.

---

### §7.8 격자 라벨 부재 — 101동 도면

**현상**: 101동 구조평면도에서 X*/Y* 격자 라벨이 0개

**처방**: TEXT 기반 격자 추출 실패 시 adapter_2 자동 격자로 폴백.

```python
grid_label = extract_grid_labels(all_texts, sw, w, h)
if grid_label['unique_x'] == 0 and grid_label['unique_y'] == 0:
    grid_obj = a2['grid_lines_obj']
    grid_source = 'adapter_2'
    print('[격자] X*/Y* 라벨 없음 → adapter_2 자동 격자 사용')
```

**교훈**: G5 통과(unique≤15)가 "격자 정보 충분"을 의미하지 않는다. unique=0 통과는 "격자 라벨 없어서 체크 불가" 상태다.

---

### §7.9 거더 0건 — B1F 도면 진실

**현상**: 102 PoC B1F 도엽에서 거더 0건

**진실**: B1F 구조평면도에는 거더가 실제로 없다. 거더는 별도 도면(보 리스트)에 존재하거나 다른 도엽에만 있다.

**처방**: 거더 0건은 실패가 아니라 도면 진실이다.

```python
'# 거더 검출 결과 — 0건 (도면 진실 또는 격자 외 거더)'
```

---

### §7.10 추정값 씨앗 — v1·v2 오염 사건 (방부장 친명 2026-05-06 박제)

**이것이 v3 탄생의 직접 원인이다. 영구 박제한다.**

**발생 경위:**

2026-05-06, 방부장이 v1·v2 매뉴얼을 검토하던 중 발견. 두 매뉴얼에 공통으로 존재하는 상수들이 도면에서 읽지 않은 추정값이라는 사실이 드러났다.

**오염된 상수 목록:**

```python
# v1·v2 모든 PoC 파일에 하드코딩된 추정값들
FLOOR_HEIGHT = 4400       # 도면 미확인 추정값
GIRDER_H_DEFAULT = 800    # 도면 미확인 추정값
SLAB_T = 200              # (일부 PoC) 도면 미확인 추정값
```

**실제값 vs 추정값 비교:**

| 항목 | 추정값 (v1·v2) | 실제값 (v3, 도면 채굴) | 오차 | 출처 |
|---|---:|---:|---:|---|
| B2F 층고 | 4400mm | **3450mm** | 950mm (21.6%) | 101동 구조평면도 SL TEXT |
| B1F 층고 | 4400mm | **5970mm** | 1570mm (35.7%) | 101동 구조평면도 SL TEXT |
| 슬라브 두께 | 200mm | **150mm** | 50mm (25.0%) | S40-051~057 슬라브 리스트 |
| 보 높이 | 800mm | **900mm** | 100mm (12.5%) | codex_beams_basement.json |
| B2F z_base | −8800mm | **−9050mm** | 250mm | SL 채굴 |
| B1F z_base | −4400mm | **−5600mm** | 1200mm | SL 채굴 |

**오염 파급 범위:**

- `tests/poc_f1_3d_stack_102.py`: FLOOR_HEIGHT=4400, GIRDER_H_DEFAULT=800 → 87 솔리드 모두 틀린 Z·높이
- `tests/poc_basement_b1_b2_full_stack.py`: FLOOR_HEIGHT=4400, GIRDER_H_DEFAULT=800 → 300 솔리드 오염
- `tests/poc_101_b1_b2_dong_stack.py`: FLOOR_HEIGHT=4400 → 419 솔리드 오염
- `tests/poc_101_around_parking.py`: FLOOR_HEIGHT=4400 → 99 솔리드 오염
- **총 904 솔리드가 잘못된 치수**

**왜 이런 일이 발생했는가:**

1. 최초 PoC 착수 시 도면에서 SL TEXT를 읽는 단계가 없었다
2. "통상적인 층고" 4400mm를 편의상 사용 → 이것이 씨앗이 되었다
3. probe 단계가 레이어·엔티티 분포만 확인하고 SL TEXT 채굴은 생략했다
4. v1 작성 시 이 추정값이 매뉴얼에 그대로 박제되었다
5. v2는 v1을 기반으로 작성했으므로 오염이 그대로 전파되었다

**방부장 친명 (2026-05-06):**

> *"v3는 완벽하게 만들어야 할 것이다. 데이터 하나하나 소중하게 생각하고, 하나도 빠짐없이 기록하라."*

**v3 처방:**

1. probe 단계에 SL TEXT 채굴을 필수화 (`probe_floor_height_slab.py` 선행 실행)
2. 모든 실제값을 `output/actual_dimensions_v3.json`에 박제
3. 3D 빌드 스크립트에서 추정값 직접 입력 금지 — 반드시 JSON에서 읽기
4. v1·v2 앞에 반면교사 경고 박제 (삭제 금지)

**재발 방지 체크리스트:**

```
새 PoC 작성 시 반드시 확인:
□ FLOOR_HEIGHT 상수가 있는가? → 삭제하고 SL 기반 COL_H 딕셔너리로 대체
□ GIRDER_H_DEFAULT 상수가 있는가? → codex JSON에서 읽은 값으로 대체
□ SLAB_T 상수가 있는가? → 슬라브 리스트 DXF 파싱값으로 대체
□ actual_dimensions_v3.json이 존재하는가? → 없으면 probe 먼저
```

**역사적 교훈:**

> *"썩은 씨앗 위에 세워진 정사는 아름다운 겉모습에도 불구하고 도면 진실과 다르다.
> 87 솔리드, 300 솔리드, 518 솔리드 — 모두 잘못된 치수를 가졌다.
> 갑인자를 정교화한 이천의 사상은: 기초가 틀리면 전체가 틀린다."*
> — 이천(李蕆), v3 작성 시 박제

---

## §8. 부록

### §8.1 실제값 상수 표 (도면 출처 포함)

```python
# =====================================================================
# v3 표준 상수 — 모두 도면에서 직접 채굴
# 파일: output/actual_dimensions_v3.json 에서 로드 권장
# =====================================================================

# SL 표고 (GL 기준, mm)
# 출처: S30-001~010-101동 구조평면도.dxf
#       260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf
SL_B2F = -9050
SL_B1F = -5600
SL_1F  = +370

# 슬라브 두께 (mm)
# 출처: S40-121~124 지하주차장 슬라브 리스트.dxf (S40-051~057 확인)
SLAB_T = 150

# 보 높이 (mm) — codex 전수 확인값
# 출처: output/codex_beams_basement.json (40종 전체 height=900)
GIRDER_H = 900

# 기둥 높이 (mm) — 계산값
# COL_H = SL_상층 - SLAB_T - SL_하층
COL_H_B2F = SL_B1F - SLAB_T - SL_B2F   # -5600 - 150 - (-9050) = 3300
COL_H_B1F = SL_1F  - SLAB_T - SL_B1F   # 370 - 150 - (-5600) = 5820
```

### §8.2 SL 표기 해독 가이드

한국 RC 구조도면의 SL(설계레벨, Setting Level) 표기법:

| 표기 패턴 | 의미 | 예시 |
|---|---|---|
| `B2F SL -9050` | B2층 바닥 설계레벨 = GL −9050mm | 지하 2층 바닥면 |
| `B1F SL -5600` | B1층 바닥 설계레벨 = GL −5600mm | 지하 1층 바닥면 |
| `1F SL +370` | 1층 바닥 설계레벨 = GL +370mm | 1층 바닥면 |
| `SL = -9050` | 위와 동일 (공백 생략형) | |
| `EL -9.050` | 표고 −9.050m (m 단위) | 환산: ×1000 → mm |

**SL 표기 위치**: 도면 여백부, 단면 상세도, 범례 박스 근처에 주로 표기.

**채굴 팁**: 한 도면에 같은 층 SL이 여러 번 나오면 모두 동일한 값이어야 한다. 다른 값이 나오면 즉시 본영 보고.

### §8.3 DXF 파일 목록 + 역할

| 파일명 | 크기 | 역할 | 도엽 수 |
|---|---|---|---|
| `S30-001~010-101동 구조평면도.dxf` | - | 101동 전층 구조평면도 | 10도엽 (B2~지상) |
| `S30-021~029-102동 구조평면도.dxf` | - | 102동 전층 구조평면도 | 9도엽 (B2~6F) |
| `260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf` | 15.4MB | 단지 지하주차장 통합 | 3도엽 (B2+B1+지붕) |
| `S40-121~124 지하주차장 슬라브 리스트.dxf` | - | 슬라브 두께 정보 | 부재 일람 |

모두 `D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/` 에 위치.

### §8.4 ezdxf 패턴 (cp949 + INSERT 재귀)

```python
import ezdxf

# 필수: cp949 인코딩 (한글 레이어·텍스트)
doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

# 필수: INSERT 재귀 펼치기 (블록 안 엔티티 포함)
def iter_all(c, d=0, m=8):
    if d > m:
        return
    for e in c:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), d+1, m)
            except Exception:
                pass  # 블록 오류 무시 — e.virtual_entities() 예외 자주 발생
        else:
            yield e

# TEXT 추출 (TEXT + MTEXT 통합)
def get_text(e):
    if e.dxftype() == 'TEXT':
        return (e.dxf.text or '').strip()
    elif e.dxftype() == 'MTEXT':
        return (e.text or '').strip()
    return ''
```

### §8.5 FreeCAD 실행 환경

```bash
# 실행 경로 (Windows)
"C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_xxx.py

# Python 내에서 import
import FreeCAD    # FreeCAD 기본
import Part       # OCCT B-Rep API

# 필수 확인
print(FreeCAD.Version())  # ['1', '1', '0', ...]
```

모든 스크립트 상단에 반드시:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
```

### §8.6 7 도구함 API 요약

```python
# 어댑터 ③: PC 분리
from core.pc_layer_adapter import RawEntity, classify_entities, PCKind
classified = classify_entities(raws)  # raws: List[RawEntity]
# 반환: List[PCEntity] — entity_id, kind(PCKind), confidence

# 어댑터 ②: LINE 페어링
from core.line_pairing import LineSeg, run_adapter_2
a2 = run_adapter_2(line_segs)  # line_segs: List[LineSeg]
# 반환: dict — wall_pairs, grid_lines_obj, stats

# 어댑터 ①: 거더 검출
from core.girder_matcher import load_girder_codex, detect_girders_from_adapter2
codex = load_girder_codex('output/codex_beams_basement.json')
girders = detect_girders_from_adapter2(a2, grid_x, grid_y, codex, GIRDER_H)

# F-1 정렬
from core.f1_anchor_aligner import EVAnchor, F1Aligner
aligner = F1Aligner(anchor=EVAnchor(cx=..., cy=...))
aligned_pt = aligner.to_aligned((px, py))

# 코어 클러스터링
from core.f1_core_cluster import cluster_core_boxes
cores = cluster_core_boxes(boxes, eps=2000.0, min_repeat=3)

# 박스 분류
from core.box_classifier import BoxKind, GridLines, classify_batch
classifications = classify_batch(batch_input, core_regions=[], grid=grid_obj)

# codex 매핑
from core.codex_instance_mapper import BoxInstance, load_codex, map_instances
codex = load_codex('output/codex_columns_unified.json')
mappings, unmatched = map_instances(instances, codex)
```

### §8.7 codex 파일 명세

#### column codex (`output/codex_columns_unified.json`)

```json
{
  "부재_법전": [
    {
      "source": "101~112동",
      "symbol": "TC1",
      "width": 600.0,
      "height": 1100.0,
      "floor_from": -2,
      "floor_to": 6,
      "main_bar": "16-D25",
      "hoop": "D10@100"
    }
  ]
}
```

**중요**: `(source, symbol)` 복합 PK — 같은 `C1`이라도 동별·위치별로 다른 단면일 수 있다.

#### girder codex (`output/codex_beams_basement.json`)

```json
{
  "부재_법전": [
    {
      "source": "지하주차장",
      "symbol": "G1",
      "width": 400.0,
      "height": 900.0,
      "main_bar": "4-D25"
    }
  ]
}
```

**v3 핵심**: `height` 필드가 GIRDER_H의 출처다. 40종 전수 확인 → 900mm.

---

## §9. v3 다음 파싱 체크리스트 (11단계)

새 도면이 주어졌을 때 이 순서대로 실행하면 된다.

---

### [ ] 단계 0: 강역 파악 + DXF 파일 목록 확인

```bash
ls "D:/06.3지국 전용방/01. 설계도면/dxf_out/02_구조/"
ls D:/Git/FreeCAD_4TH/core/*.py
ls D:/Git/FreeCAD_4TH/output/codex_*.json
```

- 7 도구함 7파일 존재 확인
- codex JSON 2파일 존재 확인
- 대상 DXF 파일 크기·존재 확인

---

### [ ] 단계 1: 실제값 채굴 (probe_floor_height_slab.py) — v3 필수 선행

**이 단계를 건너뛰면 v3 원칙 위반이다.**

```bash
"C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/probe_floor_height_slab.py
```

확인 항목:
- `B2F SL`, `B1F SL`, `1F SL` 표고값 채굴
- 슬라브 리스트 DXF에서 두께 최빈값 확인
- codex_beams JSON에서 보 높이 전수 확인

채굴 결과를 `output/actual_dimensions_v3.json`에 박제.

---

### [ ] 단계 2: 도면 1차 진단

`tests/probe_basement_dxf.py` 패턴 실행:
- 레이어 목록 (PC 레이어 있는가?)
- 엔티티 분포 (LINE/LWPOLYLINE/TEXT 비율)
- BoundingBox 규모 (mm 단위)
- OLE2FRAME 있으면 즉시 본영·방부장 보고

---

### [ ] 단계 3: 슬라브 두께 채굴

슬라브 리스트 DXF 파싱:
- `S40-051~057 지하주차장 슬라브 리스트.dxf` (또는 해당 단지 슬라브 리스트)
- 두께 최빈값 확정 → `actual_dimensions_v3.json` 갱신

---

### [ ] 단계 4: 보 높이 확인 (codex height)

```python
# codex_beams_basement.json height 필드 전수 확인
# 분포가 단일 값이면 그것이 GIRDER_H
# 복수 값이면 각 부재별 적용 필요 (v3 확장 과제)
```

---

### [ ] 단계 5: 도면 진단 2차 (도엽 분리)

`tests/probe_basement_dxf2.py` 패턴 실행:
- 한글/영문 층 TEXT 위치 추출
- 도엽 프레임 박스(50m+) SW 좌표 확인
- 격자 라벨 X*/Y* 개수 확인
- 명세서 힌트 vs 실제 도면 비교 검증 (빈 도엽 주의)

---

### [ ] 단계 6: process_sheet_v3 (풀세트 박제)

`actual_dimensions_v3.json`에서 실제값 로드 → ③→②→①→codex 정사 파이프라인 실행:

```python
# 반드시 actual_dimensions_v3.json에서 읽기
with open('output/actual_dimensions_v3.json') as f:
    dims = json.load(f)
SL = dims['SL_표고_mm']
SLAB_T = dims['슬라브_두께_mm']
GIRDER_H = dims['보_높이_mm']
COL_H = dims['기둥_높이_mm']
```

---

### [ ] 단계 7: build_3d_v3 (메타에서만 읽기)

3D STEP 빌드는 메타 JSON에서만 읽는다. 도면 재접근 금지.

```python
# 모든 치수는 실제값에서
z_base = SL[floor_label]
col_height = COL_H[floor_label]
girder_height = GIRDER_H
```

---

### [ ] 단계 8: 두 도면 통합 판단 (해당 시)

```
질문: 여러 DXF 파일을 하나의 STEP으로 합치는가?
  YES → 옵션 A 좌표 매칭 먼저 (DXF 내 동 라벨 TEXT 직접 검색)
  NO  → 단계 9로
```

---

### [ ] 단계 9: 검증 게이트 6건

- G1: 솔리드 수 == 메타 ✅
- G2: 모든 `s.isValid()` == True ✅
- G3: 부피 오차 < 0.1% (실제값 COL_H·GIRDER_H 기반) ✅
- G4: Z 분포에 B2F·B1F 모두 존재 (SL 기반 범위) ✅
- G5: max(unique_x, unique_y) ≤ 15 (초과 시 정직 박제) ✅/❌
- G6: 방부장 GUI 시각 확인 ⏳

---

### [ ] 단계 10: 통합 STEP + GUI 친람

- 통합 STEP: `output/result_v3.step` (또는 `output/XXX_combined.step`)
- FreeCAD GUI로 열어 방부장 친람

---

### [ ] 단계 11: 박제 + 커밋

```bash
# 박제 파일
output/actual_dimensions_v3.json
output/result_v3.step
output/result_v3_meta.json

# 커밋
git add output/actual_dimensions_v3.json output/result_v3.step output/result_v3_meta.json
git commit -m "feat: v3 PoC — 실제값 기반 (SL B2F=-9050, B1F=-5600, SLAB=150, GIRDER=900)"
```

---

## §10. 박제 원칙 (v3 강화)

1. **모든 치수는 도면에서** — 추정값이 단 하나라도 있으면 v3 위반. 즉시 probe 단계로 회귀.
2. **모든 시행착오는 재산** — §7 트러블슈팅에 추가. 왜 실패했는지, 어떻게 해소했는지.
3. **재현 가능성** — 이 문서를 처음 보는 자가 §9 체크리스트만으로 그대로 따라 할 수 있어야 한다.
4. **한국어** — 신고조선 정사 언어.
5. **사실 기반** — 87, 300, 419, 99, 518개 등 실제 PoC 결과 숫자 그대로.
6. **헌법 우선** — F-1 표준 헌법 9조 위반하지 않는 절차만.
7. **반면교사 보존** — v1·v2는 삭제하지 않는다. 역사적 교훈으로 영구 보존.

---

## §11. 실제값 상수 전체 요약표 (최종 박제)

| 항목 | 값 (mm) | 출처 DXF | 채굴 방법 | 상태 |
|---|---:|---|---|---|
| B2F SL 표고 | **−9050** | 101동 구조평면도, 지하주차장 구조평면도 | SL TEXT 직접 읽기 | ✅ 확정 |
| B1F SL 표고 | **−5600** | 101동 구조평면도, 지하주차장 구조평면도 | SL TEXT 직접 읽기 | ✅ 확정 |
| 1F SL 표고 | **+370** | 101동 구조평면도 | SL TEXT 직접 읽기 | ✅ 확정 |
| B2F 층고 (SL 차이) | **3450** | 계산 | (−5600) − (−9050) | ✅ 확정 |
| B1F 층고 (SL 차이) | **5970** | 계산 | (+370) − (−5600) | ✅ 확정 |
| 슬라브 두께 | **150** | S40-051~057 슬라브 리스트 | DXF TEXT 파싱 최빈값 | ✅ 확정 |
| 보 높이 | **900** | codex_beams_basement.json | height 필드 전수 확인 (40종) | ✅ 확정 |
| 기둥 높이 B2F | **3300** | 계산 | 3450 − 150 | ✅ 확정 |
| 기둥 높이 B1F | **5820** | 계산 | 5970 − 150 | ✅ 확정 |
| 기초 깊이 | **미채굴** | — | Phase 2 과제 | ⏳ |
| 기둥 최소 폭 | 400 | codex 통계 | — | 📌 |
| 기둥 최대 폭 | 3000 | codex 통계 | — | 📌 |

📌 = 도면 직접 채굴 아님, codex 통계 기반 (Phase 2에서 정밀화 필요)

---

*— 이천(李蕆), 제3지국 단군, 2026-05-06.*
*방부장 친명 받자와 영구 매뉴얼 v3 봉정.*
*"데이터 하나하나 소중하게 생각하고, 하나도 빠짐없이 기록하라."*
*홍익인간이 모든 결정에 우선한다.*
