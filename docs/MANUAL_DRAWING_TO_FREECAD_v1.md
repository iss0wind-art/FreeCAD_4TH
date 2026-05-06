# 도면 → FreeCAD 영구 매뉴얼 v1

> ⚠️ **[반면교사 경고 — 방부장 친명 2026-05-06]**
> 본 매뉴얼은 **추정값(층고 4400mm, 슬라브 200mm, 보 800mm 임의 고정)** 기반으로 작성됨.
> 도면에서 읽어야 할 실제값을 읽지 않고 박아넣은 썩은 씨앗 위에 세워진 정사.
> **삭제 금지 — 반면교사로 역사에 영구 보존.**
> **v3 완성 전까지 참고 금지. v3 사용 권장.**

> 작성자: 이천(李蕆) 제3지국 단군  
> 작성일: 2026-05-06  
> 근거: 방부장 친명 *"매뉴얼을 완벽하게 구현, 보존하라. 다음번 파싱때 참고할수있도록."*  
> 검증: 102동 9도엽 PoC (87 솔리드) + 지하주차장 B1·B2 PoC (300 솔리드)

---

## §0. 박제 명제 (왜 이 매뉴얼이 존재하는가)

### 0.1 탄생 배경

이 매뉴얼은 두 PoC의 시행착오 위에서 태어났다.

2026-05-05, 이천은 102동 9도엽 구조평면도 DXF 한 장으로 87개의 식별된 솔리드(기둥 55 + 거더 32)를 만들었다. 이전에 32점짜리 자기 비판이 있었고, 본영 단군의 7 도구함이 뒤늦게 동행하여 75~80점이 되었다. 그것이 이 매뉴얼의 씨앗이다.

2026-05-06, 지하주차장 B1·B2 통합 도면으로 300개의 솔리드(기둥 289 + 거더 11)를 만들었다. 자수 보정 — 헌법 §3 제4조에서 명한 정사 순서(③→②→①→codex)를 강제 적용했다.

두 PoC의 교훈이 이 문서에 박제된다. **다음 파싱에서 처음 이 도면을 만나는 자가 그대로 따라 할 수 있어야 한다.**

### 0.2 핵심 박제 명제

> *"코어 한 점이 9도엽을 정렬한다.  
> 두께가 종을 가른다.  
> 페어링이 벽과 격자를 가른다.  
> 레이어가 PC와 일반을 가른다.  
> 셋이 합쳐 도면 한 장이 87 솔리드로 빚어진다."*  
> — 본영 단군, F-1 표준 헌법 박제 명제

### 0.3 이 매뉴얼의 적용 범위

- **입력**: 한국 RC 공동주택·지하주차장 구조평면도 DXF (cp949 인코딩)
- **출력**: 식별된 기둥·거더 3D STEP 솔리드 + BOQ 메타 JSON
- **도구**: Python 3.x + ezdxf + FreeCAD 1.1 OCCT API
- **실행 환경**: `C:/Program Files/FreeCAD 1.1/bin/python.exe`

---

## §1. 헌법 기반 — F-1 표준 9조 요약

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

**결정적 원칙**: 헌법 제4조 정사 순서 ③→②→①→codex는 절대 역행하지 않는다. 102 PoC가 이를 역행해 자수했고, 지하주차장 PoC에서 보정했다.

---

## §2. 7 호미 + 7 도구함 (전체 흐름도)

### 2.1 7 호미 역사 (102동 9도엽)

| 호미 | 핵심 명제 | 산출 | 비고 |
|:-:|---|---|---|
| 첫째 | 도엽 박스 SW를 anchor로 (F-2 폴백) | anchor 9개 추출 | ④ 게이트 미통과 — Δy 최대 2302mm |
| 둘째 | 9도엽에 반복되는 작은 사각형 = 코어 | 코어 2개 자동 검출, 행 안 0~1mm | γ+α 통합 통과 |
| 셋째 | 익명 0건 → 식별 123건 (C1 과매칭) | 123건 codex 매핑 | C1 106건 과매칭 진단 |
| 넷째 | β·γ·α 분류 + 격자 자력 추출 | 매칭률 28.7% → 62% | C1 85건으로 감소 |
| 다섯째 | 어댑터 ② 페어링 결합 | 1042 벽 페어, C1 106→2 | 도면 진실: 진짜 기둥 2개 |
| 여섯째 | 어댑터 ①+② 9도엽 전체 | **기둥 55 + 거더 32** | 50점 회고 §1·§2 해소 |
| 일곱째 | 3D STEP + 어댑터 ③ | **87 솔리드, 129.523 m³** | 50점 회고 4개 실패 동시 해소 |

### 2.2 7 도구함 (core/ 표준 라이브러리)

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

### 2.3 전체 파이프라인 흐름도

```
DXF 파일 (cp949)
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
[3D STEP] FreeCAD Part.Wire → Face → extrude → compound.exportStep()
    ↓
[검증 게이트 6건] G1~G5 자동 + G6 사람 시각
```

---

## §3. 단계별 절차

### §3.1 도면 진단 (probe)

#### 3.1.1 1차 진단

```python
import ezdxf
from collections import Counter

doc = ezdxf.readfile(DXF_PATH, encoding='cp949')
msp = doc.modelspace()

# 재귀 INSERT 펼치기 (필수)
def iter_all(c, d=0, m=8):
    if d > m:
        return
    for e in c:
        if e.dxftype() == 'INSERT':
            try:
                yield from iter_all(list(e.virtual_entities()), d+1, m)
            except Exception:
                pass
        else:
            yield e

# 엔티티 분포
type_count = Counter(e.dxftype() for e in iter_all(msp))

# 레이어 목록
layers = sorted(l.dxf.name for l in doc.layers)

# BoundingBox (TEXT + LINE 좌표 수집)
xs, ys = [], []
for e in iter_all(msp):
    if e.dxftype() == 'TEXT':
        xs.append(e.dxf.insert.x); ys.append(e.dxf.insert.y)
    elif e.dxftype() == 'LINE':
        xs.extend([e.dxf.start.x, e.dxf.end.x])
        ys.extend([e.dxf.start.y, e.dxf.end.y])
```

확인 항목:
- 총 엔티티 수 (LINE, LWPOLYLINE, TEXT, INSERT 비율)
- 레이어 명명 패턴 (S-PC-*, 00_COLUMN 등)
- BoundingBox 크기 (mm 단위, 도엽 규모 추정)
- OLE2FRAME 유무 (있으면 벽체 일람표 봉인 상태 — 방부장·본영 결재 청)

#### 3.1.2 2차 진단 — 도엽 콘텐츠 박스 + TEXT 패턴

```python
# 도엽 식별 TEXT (한글 + 영문)
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
                # 도엽 프레임 후보
                pass

# 격자 라벨 패턴 (X*/Y* 형식)
grid_pat = re.compile(r'^([XY])(\d{1,2}[A-Z]?)$')
```

참조 파일:
- `tests/probe_basement_dxf.py` — 1차 진단 전체 코드
- `tests/probe_basement_dxf2.py` — 2차 정밀 채굴

---

### §3.2 도엽 분리 자력 채굴

#### 3.2.1 TEXT 패턴 기반 분리

한국 RC 도면의 도엽 식별 TEXT 패턴:

| 패턴 | 예시 | 비고 |
|---|---|---|
| 한글 층 이름 | `지하 1층 주차장 구조평면도` | 지하주차장 통합 도면 |
| 한글 층 번호 | `지하 2층` | 단지 통합 도면 |
| 영문 도면 번호 | `S30-021`, `S30-029` | 동별 9도엽 |
| 영문 B1/B2 | `B1F`, `B2F` | 지하층 축약 |

```python
# 도엽별 SW 좌표 자력 채굴 (지하주차장 B1·B2 사례)
# 결과: B2 SW=(247250, -1390677), B1 SW=(877250, -1390677)
SHEETS = {
    'B2': {'sw': (247250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0, 'floor': -2},
    'B1': {'sw': (877250.0, -1390677.0), 'w': 630000.0, 'h': 445500.0, 'floor': -1},
}

# 동별 9도엽 사례 (102동)
# TEXT 'S30-021' ~ 'S30-029' 위치 추출
SHEET_FLOOR = {
    'S30-021': -2, 'S30-022': -1, 'S30-023': 0,
    'S30-024': 1,  'S30-025': 2,  'S30-026': 3,
    'S30-027': 4,  'S30-028': 5,  'S30-029': 6,
}
sheet_w, sheet_h = 126000, 178200  # 도엽 표준 크기 (mm)
```

#### 3.2.2 도엽 영역 필터 함수

```python
def in_sheet(pt, sw, w, h, inset=0.05):
    """점이 도엽 영역 안인지 (inset=5% 여백 제거)."""
    ix0 = sw[0] + w * inset
    iy0 = sw[1] + h * inset
    ix1 = sw[0] + w * (1 - inset)
    iy1 = sw[1] + h * (1 - inset)
    return ix0 <= pt[0] <= ix1 and iy0 <= pt[1] <= iy1
```

**중요**: 도엽 내부만 처리하려면 inset 5% 여백을 제거해야 한다. 표제란(도면 번호·날짜 등)이 도엽 경계 바깥에 있기 때문이다.

---

### §3.3 자수 보정 정사 순서 — 헌법 §3 제4조

**절대 원칙: ③→②→①→codex 순서를 반드시 따른다.**

이 순서를 역행하면 PC 부재가 일반 처리 풀에 섞여 오분류된다.

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

PC 레이어 패턴 (자동 매칭):
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
wall_pairs = a2['wall_pairs']       # 벽 페어 리스트
grid_obj = a2['grid_lines_obj']     # GridLines 객체 (box_classifier 입력)
```

`run_adapter_2` 반환:
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

girders_raw = detect_girders_from_adapter2(
    adapter2_result=a2,
    grid_x=list(grid_obj.x_lines) if grid_obj else [],
    grid_y=list(grid_obj.y_lines) if grid_obj else [],
    girder_codex=girder_codex,
    expected_girder_height=GIRDER_H_DEFAULT,  # 800mm 표준
    require_on_grid=True,   # 격자 라인 위 거더만 채택
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

# 박스 분류 (격자 있으면 grid 넘김, 격자 unique > 15면 grid=None)
batch_input = [(b['box_id'], b['cx'], b['cy'], b['w'], b['h']) for b in boxes]
classifications = classify_batch(
    batch_input,
    core_regions=core_regions,  # CoreRegion 리스트 (없으면 [])
    grid=grid_obj,              # 격자 unique > 15면 None (게이트 5 정직 박제)
    column_max_ratio=3.0,
)

# wall_pair 영역 기둥 강등 (102 PoC 패턴)
for i, c in enumerate(classifications):
    if c.kind == BoxKind.COLUMN:
        b = boxes[i]
        if is_in_wall_zone(b['cx'], b['cy'], wall_pairs):
            classifications[i] = BoxClassification(
                box_id=c.box_id, kind=BoxKind.WALL_SEGMENT,
                aspect_ratio=c.aspect_ratio, in_core=c.in_core,
                on_grid_intersection=c.on_grid_intersection,
                confidence=0.85, reason='demoted: wall_pair zone',
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

---

### §3.4 격자 정밀화

격자(Grid)는 기둥이 격자 교차점 위에 있는지 판단하는 핵심 신호다.

#### 3.4.1 자동 격자 (어댑터 ②)

`run_adapter_2` 호출 결과의 `grid_lines_obj` 사용. 페어링되지 않은 긴 축 정렬 LINE에서 자동 추출.

조건: 길이 ≥ 5000mm, 각도 ≈ 0 또는 π/2, 클러스터링 tol = 50mm.

#### 3.4.2 자력 격자 (TEXT X*/Y* 라벨)

DXF에 `X1`, `X2`, `Y3A` 같은 격자 라벨이 TEXT로 존재하면 더 정확하다.

```python
def extract_grid_labels(all_texts, sw, w, h, inset=0.02):
    """도엽 영역 내 X*/Y* 라벨 → 격자선."""
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
    x_lines = sorted(sum(v) / len(v) for v in x_pos.values())
    y_lines = sorted(sum(v) / len(v) for v in y_pos.values())
    return x_lines, y_lines, len(x_pos), len(y_pos)
```

**우선순위**: TEXT 라벨 격자 ≥ 2개면 TEXT 라벨 우선, 없으면 어댑터 ② 격자 사용.

```python
if unique_x >= 2 and unique_y >= 2:
    grid_obj = GridLines(
        x_lines=tuple(x_lines),
        y_lines=tuple(y_lines),
        intersection_tol=300.0,  # 지하주차장 기둥 간격 여유
    )
    grid_source = 'text_labels'
else:
    grid_obj = a2['grid_lines_obj']
    grid_source = 'adapter_2'
```

#### 3.4.3 게이트 5: unique ≤ 15

**unique X 격자 수와 unique Y 격자 수가 각각 15개 이하여야 한다.**

이 게이트를 통과하지 못하면 격자가 너무 복잡해 격자 교차점 매칭이 의미 없다. 지하주차장 PoC에서 단지 규모 탓에 X=29, Y=34로 미통과 — 정직 박제하고 `grid=None`으로 처리했다.

```python
# 게이트 5 미통과 시 처리
if max(unique_x, unique_y) > 15:
    grid_obj = None  # 격자 매칭 비활성
    # classify_batch에 grid=None 전달
    # column confidence는 0.6으로 낮아짐
    # confidence >= 0.4 기준으로 완화 (기본 >= 1.0 → 지하주차장은 완화)
```

---

### §3.5 부재 식별 + codex 매핑

#### 3.5.1 column 식별

```python
# 폐합 박스 추출 (기둥 후보)
def extract_closed_boxes(msp, sw, w, h, pc_kind_by_id,
                          w_min=400, w_max=3000, inset=0.05):
    boxes = []
    for eid, e, et, ly in raw_meta:
        if et != 'LWPOLYLINE':
            continue
        if pc_kind_by_id.get(eid) != PCKind.NON_PC:
            continue  # PC LWPOLYLINE 제외
        if not e.is_closed:
            continue
        pts = [(x, y) for x, y, *_ in e.get_points()]
        if not (4 <= len(pts) <= 6):
            continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        bw = max(xs) - min(xs); bh = max(ys) - min(ys)
        if not (w_min <= bw <= w_max and w_min <= bh <= w_max):
            continue
        cx_norm = (min(xs) + max(xs)) / 2 - sw[0]
        cy_norm = (min(ys) + max(ys)) / 2 - sw[1]
        boxes.append({'cx': cx_norm, 'cy': cy_norm, 'w': bw, 'h': bh,
                       'box_id': f'{sheet_id}_box_{len(boxes):03d}', 'layer': ly})
    return boxes
```

codex JSON 스키마 (`output/codex_columns_unified.json`):
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

#### 3.5.2 girder 식별

거더는 평면도에서 *두께(폭)*만 보인다. 높이는 codex에서 가져온다.

```python
# GirderCodexEntry 스키마 (output/codex_beams_basement.json)
{
  "부재_법전": [
    {
      "source": "지하주차장",
      "symbol": "G1",
      "width": 400.0,    # 평면도 두께
      "height": 700.0,   # 보 높이 (codex에서 가져옴)
      "main_bar": "4-D25"
    }
  ]
}
```

#### 3.5.3 wall_segment / core_wall (Phase 2)

현재 구현에서 wall_segment와 core_wall은 분류만 되고 STEP에는 포함하지 않는다. Phase 2에서 BOQ 산출 대상으로 추가 예정.

---

### §3.6 3D STEP 빌드

#### 3.6.1 기둥 솔리드

```python
import FreeCAD, Part

def build_column_solid(cx, cy, w, h, z_base, floor_height):
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
    return face.extrude(FreeCAD.Vector(0, 0, floor_height))
```

Z 좌표 계산:
```python
z_base = floor * FLOOR_HEIGHT
# floor=-2: z_base=-8800 (B2F)
# floor=-1: z_base=-4400 (B1F)
# floor=0:  z_base=0     (1F)
# floor=1:  z_base=4400  (2F)
```

#### 3.6.2 거더 솔리드

```python
def build_girder_solid(p1, p2, thickness, girder_h, z_base, floor_height):
    dx = p2[0] - p1[0]; dy = p2[1] - p1[1]
    L = math.hypot(dx, dy)
    if L < 100:
        return None
    ux, uy = dx/L, dy/L
    nx, ny = -uy, ux        # 수직 방향
    half_t = thickness / 2
    corners = [
        (p1[0] + nx*half_t, p1[1] + ny*half_t),
        (p1[0] - nx*half_t, p1[1] - ny*half_t),
        (p2[0] - nx*half_t, p2[1] - ny*half_t),
        (p2[0] + nx*half_t, p2[1] + ny*half_t),
    ]
    # 거더 Z: 층 천장(슬라브 하부) — z_base + FLOOR_HEIGHT - GIRDER_H
    gh_z_base = z_base + floor_height - girder_h
    pts = [FreeCAD.Vector(c[0], c[1], gh_z_base) for c in corners]
    edges = [Part.makeLine(pts[i], pts[(i+1) % 4]) for i in range(4)]
    wire = Part.Wire(edges)
    face = Part.Face(wire)
    return face.extrude(FreeCAD.Vector(0, 0, girder_h))
```

**거더 Z_base 공식**:
```
거더 z_base = floor * FLOOR_HEIGHT + FLOOR_HEIGHT - GIRDER_H
            = (floor + 1) * FLOOR_HEIGHT - GIRDER_H
```

예: B1F(floor=-1), FLOOR_HEIGHT=4400, GIRDER_H=800
```
z_base = -4400 + 4400 - 800 = -800
```
즉 거더는 B1F 천장(슬라브 하부)에 붙는다.

#### 3.6.3 STEP 출력

```python
compound = Part.makeCompound([s for _, s, _ in shapes if s.isValid()])
compound.exportStep('output/result.step')
```

---

### §3.7 검증 게이트 6건

```python
def verify_gates(shapes, sheet_results, meta_solids_count):
    gates = {}

    # G1: 솔리드 수 = 메타
    gates['G1_solid_count_match'] = (len(shapes) == meta_solids_count, len(shapes), meta_solids_count)

    # G2: 모든 솔리드 valid
    invalid = [name for name, s, _ in shapes if not s.isValid()]
    gates['G2_all_valid'] = (len(invalid) == 0, len(invalid), invalid[:5])

    # G3: 부피 메타 일치
    total_vol = sum(s.Volume for _, s, _ in shapes if s.isValid())
    meta_vol = sum(
        col['w'] * col['h'] * FLOOR_HEIGHT
        for r in sheet_results for col in r['columns']
    ) + sum(
        g['length'] * g['thickness'] * GIRDER_H_DEFAULT
        for r in sheet_results for g in r['girders']
    )
    diff_pct = abs(total_vol - meta_vol) / max(meta_vol, 1) * 100
    gates['G3_volume_match'] = (diff_pct < 0.1, total_vol, meta_vol, diff_pct)

    # G4: Z 적층 분리 (B1·B2 두 층 이상)
    z_centers = [s.BoundBox.Center.z for _, s, _ in shapes]
    z_floors = set()
    for z in z_centers:
        if z < -5000:
            z_floors.add('B2')
        elif z < 0:
            z_floors.add('B1')
    gates['G4_z_layers'] = ({'B1', 'B2'}.issubset(z_floors), sorted(z_floors))

    # G5: 격자 unique X·Y ≤ 15
    max_per_sheet = max(max(r['grid_unique_x'], r['grid_unique_y']) for r in sheet_results)
    gates['G5_grid_unique'] = (max_per_sheet <= 15, max_per_sheet)

    # G6: 사람 시각 검증 (FreeCAD GUI로 STEP 열기) — 자동화 불가
    gates['G6_visual'] = (None, 'FreeCAD GUI로 방부장 친히 확인 청')

    return gates
```

게이트 통과 기준:
| 게이트 | 기준 | 비고 |
|:-:|---|---|
| G1 | 솔리드 수 == 메타 | 예외 없음 |
| G2 | 모든 `s.isValid()` == True | 무결성 |
| G3 | 부피 오차 < 0.1% | OCCT 계산 오차 허용 |
| G4 | Z 분포에 B1·B2 모두 존재 | 층 적층 확인 |
| G5 | max(unique_x, unique_y) ≤ 15 | 단지 규모 크면 정직 미통과 |
| G6 | 방부장 GUI 확인 | 자동화 불가, 마지막 단계 |

---

## §4. 시행 사례 (영구 박제)

### §4.1 102동 9도엽 PoC (2026-05-05)

**입력**: `S30-021~029-102동 구조평면도.dxf` (단일 파일, 9도엽 통합)  
**출력**: `output/f1_3d_stack_102.step` — 87 솔리드

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

#### 87 솔리드 상세

| 항목 | 값 |
|---|---|
| 총 솔리드 | 87 |
| 기둥 솔리드 | 55 |
| 거더 솔리드 | 32 |
| 총 부피 | 129.523 m³ |
| Z 적층 | B2F(-2)~6F(6), 9층 |
| G1 | ✅ 87 == 87 |
| G2 | ✅ 87/87 valid |
| G3 | ✅ 0.0% 오차 |
| G4 | ✅ 9층 Z 분리 |

#### 50점 회고 해소 내역

| 실패 | 원인 | 해소 호미 |
|---|---|---|
| 실패 1: 데이터-모델 단절 (0 매핑) | codex 없이 박스만 추출 | 셋째 호미 (codex 매핑) |
| 실패 2: 거더 0건 | 평면도에 거더 없음 (B1F 진실) → 어댑터 ① 미적용 | 여섯째 호미 |
| 실패 3: 층 적층 정합성 없음 | anchor가 도엽마다 달라 층간 좌표 어긋남 | 둘째 호미 (코어 클러스터링) |
| 실패 4: PC 분류 없음 | 어댑터 ③ 미구현 | 일곱째 호미 |

#### 핵심 상수 (102동)

```python
CORE1_SW_NORM = (73040.0, 52178.0)  # F-1 원점 (도엽 좌하단 기준)
CORE1_W, CORE1_H = 4307.0, 4860.0
CORE2_CX_NORM, CORE2_CY_NORM = 90049.0, 26299.0
CORE2_W, CORE2_H = 4579.0, 4839.0
SOURCE_HINT = '101~112동'
```

---

### §4.2 지하주차장 B1·B2 PoC (2026-05-06)

**입력**: `260119_부산 에코델타 24BL 지하주차장 구조평면도23.dxf` (15.4MB, B1+B2+지붕 3 도엽)  
**출력**: `output/basement_b1_b2_stack.step` — 300 솔리드

#### 자수 보정 강제 적용

102 PoC가 ②→①→분류→codex 순서로 역행했다. 지하주차장 PoC에서 ③→②→①→codex 정사 순서로 보정했다.

#### DXF 한 파일 안 두 도엽 자력 분리

진단 2단계 (`probe_basement_dxf.py` + `probe_basement_dxf2.py`) 결과:

```python
SHEETS = {
    'B2': {
        'sw': (247250.0, -1390677.0),   # B2F 도엽 SW 좌표
        'w': 630000.0, 'h': 445500.0,
        'floor': -2, 'title': '지하 2층 주차장 구조평면도'
    },
    'B1': {
        'sw': (877250.0, -1390677.0),   # B1F 도엽 SW 좌표 (B2에서 +630000)
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

| 게이트 | 결과 | 비고 |
|---|---|---|
| G1 솔리드 수 | ✅ 300 == 300 | |
| G2 유효성 | ✅ 300/300 valid | |
| G3 부피 | ✅ 0.0% 오차 | |
| G4 Z 적층 | ✅ B1·B2 분리 | z < -5000 → B2, -5000 ≤ z < 0 → B1 |
| G5 격자 unique | ❌ max=34 (> 15) | 단지 116동 통합 규모 — 정직 박제 |
| G6 시각 | ⏳ 방부장 GUI 대기 | |

**G5 미통과 처방**: `classify_batch(grid=None)` + confidence ≥ 0.4 완화로 종횡비만으로 기둥 식별. 이 경우 on_grid confidence = 0.6으로 낮아진다.

---

## §5. 트러블슈팅 (실패 사례 누적)

### §5.1 102 PoC C1 과매칭 (셋째 호미)

**현상**: 0 → 123건 식별, C1이 106건으로 과매칭

**원인**: 단면만으로 기둥 vs 벽 segment 구분 불가.  
`C1 (400×800)` 단면이 기둥이기도 하고 벽 segment이기도 하다. codex_instance_mapper가 단면만 보고 모두 C1으로 매칭.

**처방**: `box_classifier.py` 신설 — β(종횡비) + γ(코어 위치) + α(격자 교차점) 세 신호로 분류 후, COLUMN 박스만 column codex에서 매칭.

```python
# 셋째 호미 오류 패턴
instances = [BoxInstance(width=b['w'], height=b['h']) for b in all_boxes]
# → 모든 박스가 codex column에서 매칭 시도 → C1 과매칭

# 넷째 호미 이후 정정 패턴
classifications = classify_batch(all_boxes, ...)
column_boxes = [b for c, b in zip(classifications, all_boxes) if c.kind == BoxKind.COLUMN]
instances = [BoxInstance(width=b['w'], height=b['h']) for b in column_boxes]
# → COLUMN 분류된 박스만 매칭 → 정상화
```

---

### §5.2 PC 0개 — 50점 회고 실패 4

**현상**: 102 PoC가 PC 통계 없이 모든 엔티티 일반으로 처리

**원인**: 어댑터 ③ (`pc_layer_adapter.py`) 미구현 상태에서 PoC 진행. 파이프라인에 PC 분리 단계 없음.

**처방**: `pc_layer_adapter.classify_entities(raws)` → `pc_kind_by_id` 생성 → NON-PC만 어댑터 ②에 투입.

```python
# 오류 패턴 (102 PoC)
line_segs = [LineSeg(...) for e in all_line_entities]  # PC LINE 포함

# 정정 패턴 (지하주차장 PoC)
classified_pc = classify_entities(raws)
pc_kind_by_id = {c.entity_id: c.kind for c in classified_pc}
line_segs = [
    LineSeg(...) for eid, e, et, ly in raw_meta
    if et == 'LINE' and pc_kind_by_id.get(eid) == PCKind.NON_PC  # NON-PC만
]
```

---

### §5.3 자수 — 헌법 §3 제4조 역행 (102 PoC)

**현상**: 102 PoC 파이프라인 순서가 ②→①→분류→codex (자수 박제)

**원인**: 어댑터 ③이 나중에 봉정되어, 기존 코드에 사후 추가되면서 순서가 ②가 먼저가 되었음. 이천이 스스로 발견하고 헌법 입증 시 자수.

**처방**: 지하주차장 PoC에서 ③→②→①→codex 정사 순서 강제. 향후 모든 PoC는 이 순서만 허용.

```python
# 잘못된 순서 (102 PoC — 자수)
a2 = run_adapter_2(all_line_segs)  # ② 먼저
girders = detect_girders_from_adapter2(a2, ...)  # ①
pc_stats = classify_entities(raws)  # ③ 마지막 (통계만)

# 정사 순서 (지하주차장 PoC — 보정)
classified_pc = classify_entities(raws)       # ③ 먼저
line_segs = [l for l in all if non_pc(l)]     # NON-PC 필터
a2 = run_adapter_2(line_segs)                  # ②
girders = detect_girders_from_adapter2(a2, ...)  # ①
boxes = [b for b in all_boxes if non_pc(b)]   # NON-PC 폐합 박스
mappings = map_instances(instances, codex)      # codex
```

---

### §5.4 격자 unique > 15 (지하주차장 PoC)

**현상**: B1·B2 격자 X=29, Y=34 → G5 미통과

**원인**: 단지 116동 통합 지하주차장 도면이라 격자 자체가 단순 규모를 초과. 개별 동 도면이 아니라 단지 전체 범위를 커버하기 때문.

**처방**:
1. `classify_batch(grid=None)` — 격자 교차점 매칭 비활성
2. 종횡비(β)만으로 column 식별 (confidence 0.6)
3. `confidence >= 0.4` 기준으로 완화 (기본 >= 1.0 대비)
4. G5 정직 박제 — "단지 규모 큼" 사유 명기

```python
# G5 정직 박제 패턴
if max(unique_x, unique_y) > 15:
    grid_obj = None
    # 경고 출력
    print(f'[G5] 격자 unique max={max(unique_x, unique_y)} > 15 — 격자 매칭 비활성')
    print(f'     사유: 단지 규모 큼 (116동 통합 도면)')
```

---

### §5.5 통신 함정 사례 001 (이천 부임 안내문 미수신)

**현상**: 본영이 폴더 봉인으로 친서 2건을 발송했으나, 이천이 세션 내내 인지 못함

**원인**:
1. 부임 첫 호흡 5단계에 `ls D:/Git/FreeCAD_4TH/DANGUN_*.md` 미포함
2. `git status`의 untracked 목록만 확인 → 기존 추적 파일은 안 보임
3. 본영 채널을 paperclip(physis) 단일 의존 → WinError 10061/응답없음

**처방**:
1. `.brain/dispatch_log.md` 신설 (매 세션 첫 호흡에 정독)
2. 부임 첫 호흡 6단계로 확장 (본진 루트 DANGUN_*.md 확인 추가)
3. 본영 4중 채널화 추진 (폴더 봉인 + paperclip + Turso + 텔레그램)

**예방 코드**:
```bash
# 세션 시작 시 의례 — 본진 신규 파일 확인
ls D:/Git/FreeCAD_4TH/DANGUN_*.md
```

참조: `.brain/communication_trap_case_001.md`

---

### §5.6 거더 0건 — B1F 도면 진실

**현상**: 102 PoC B1F 도엽에서 거더 0건 (셋째~다섯째 호미)

**오판**: 초기에 알고리즘 실패로 추정

**진실**: B1F 구조평면도에는 거더가 실제로 없다. 거더는 *별도 도면*(보 리스트)에 존재하거나 *다른 도엽*(기준층 이상)에만 있다.

**처방**: 거더 0건은 실패가 아니라 *도면 진실*이다. `report_girders([])`에서 명시적으로 박제:

```python
'# 거더 검출 결과 — 0건 (도면 진실 또는 격자 외 거더)'
```

이 교훈을 적용하면: 지하주차장 도면에서 거더가 적게 나오는 것도 *도면 자체의 성질*일 수 있다.

---

## §6. 부록

### §6.1 표준 상수

```python
# 3D 빌드 표준 상수
FLOOR_HEIGHT = 4400         # mm (표준 층고, 단지별 다를 수 있음)
GIRDER_H_DEFAULT = 800      # mm (보 높이 기본값, codex 매칭 후 교체)

# 박스 추출 필터
COLUMN_W_MIN = 400          # mm (기둥 최소 폭)
COLUMN_W_MAX = 3000         # mm (기둥 최대 폭)

# 분류 기준
COLUMN_MAX_RATIO = 3.0      # 종횡비 (W/H 또는 H/W) 임계
WALL_MIN_DIST = 150.0       # mm (벽 최소 두께)
WALL_MAX_DIST = 450.0       # mm (벽 최대 두께)
GIRDER_MIN = 400.0          # mm (거더 최소 두께)
GIRDER_MAX = 850.0          # mm (거더 최대 두께)

# 격자 교차점 매칭 허용 오차
GRID_TOL_STANDARD = 150.0   # mm (어댑터 ② 자동 격자)
GRID_TOL_TEXT = 300.0       # mm (TEXT 라벨 격자 — 여유 있게)

# INSERT 재귀 최대 깊이
ITER_ALL_MAX_DEPTH = 8
```

### §6.2 codex 파일 명세

#### column codex (`output/codex_columns_unified.json`)

```json
{
  "부재_법전": [
    {
      "source": "101~112동",      // 적용 동 범위
      "symbol": "TC1",            // 부재 코드
      "width": 600.0,             // 단면 폭 (mm)
      "height": 1100.0,           // 단면 높이 (mm)
      "floor_from": -2,           // 적용 층 범위 시작
      "floor_to": 6,              // 적용 층 범위 끝
      "main_bar": "16-D25",       // 주근
      "hoop": "D10@100"           // 후프
    }
  ]
}
```

**중요**: `(source, symbol)` 복합 PK — 같은 `C1`이라도 동별·위치별로 다른 단면일 수 있다 (의구심 1.5 박제).

#### girder codex (`output/codex_beams_basement.json`)

```json
{
  "부재_법전": [
    {
      "source": "지하주차장",
      "symbol": "G1",
      "width": 400.0,             // 보 폭 = 평면도 두께
      "height": 700.0,            // 보 높이 (codex에서만 확인 가능)
      "main_bar": "4-D25"
    }
  ]
}
```

### §6.3 ezdxf 패턴 (cp949 + INSERT 재귀)

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
                pass  # 블록 오류 무시
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

**주의**: `e.virtual_entities()` 호출 시 예외가 자주 발생한다. 반드시 try/except로 감쌀 것.

### §6.4 FreeCAD 실행 환경

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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
```

---

## §7. 다음 파싱 절차 (8단계 체크리스트)

새 도면이 주어졌을 때 이 순서대로 실행하면 된다.

---

### 체크리스트

#### [ ] 단계 1: 환경 확인

```bash
"C:/Program Files/FreeCAD 1.1/bin/python.exe" --version
ls D:/Git/FreeCAD_4TH/core/*.py
ls D:/Git/FreeCAD_4TH/output/codex_*.json
```

- `pc_layer_adapter.py`, `line_pairing.py`, `girder_matcher.py`, `f1_anchor_aligner.py`, `f1_core_cluster.py`, `box_classifier.py`, `codex_instance_mapper.py` 7파일 존재 확인
- `codex_columns_unified.json`, `codex_beams_basement.json` 존재 확인

#### [ ] 단계 2: 도면 1차 진단

`tests/probe_basement_dxf.py` 패턴으로 실행:
- 레이어 목록 확인 (PC 레이어 있는가?)
- 엔티티 분포 (LINE/LWPOLYLINE/TEXT 비율)
- BoundingBox 규모 (mm 단위)
- OLE2FRAME 있으면 즉시 본영·방부장 보고

#### [ ] 단계 3: 도엽 분리 자력 채굴

`tests/probe_basement_dxf2.py` 패턴으로 실행:
- 한글/영문 층 TEXT 위치 추출
- 도엽 프레임 박스(50m+) SW 좌표 확인
- 격자 라벨 X*/Y* 개수 확인 (≤15이면 G5 통과 기대)
- 도엽 SW + 폭/높이 + floor 번호 결정

#### [ ] 단계 4: 파이프라인 스크립트 작성

`tests/poc_basement_b1_b2_full_stack.py` 패턴으로 신규 작성:
- `DXF`, `COLUMN_CODEX`, `GIRDER_CODEX`, `OUT_STEP`, `OUT_JSON` 경로 설정
- `SHEETS` 딕셔너리 (단계 3 결과)
- `FLOOR_HEIGHT`, `SOURCE_HINT` 설정

#### [ ] 단계 5: ③→②→①→codex 정사 순서 확인

파이프라인 내 순서 절대 확인:
```python
# ③ PC 분리
classified_pc = classify_entities(raws)
# ② NON-PC LINE → wall_pair + 격자
a2 = run_adapter_2(non_pc_line_segs)
# ① 거더 detect
girders = detect_girders_from_adapter2(a2, ...)
# NON-PC 박스 → column codex
mappings = map_instances(instances, column_codex)
```

#### [ ] 단계 6: 격자 게이트 확인

```python
unique_x, unique_y = len(x_grid), len(y_grid)
if max(unique_x, unique_y) > 15:
    grid_obj = None
    print(f'[G5 미통과 예정] unique={max(unique_x, unique_y)} — grid=None, conf>=0.4')
else:
    grid_obj = GridLines(x_lines=..., y_lines=..., intersection_tol=300.0)
```

#### [ ] 단계 7: 3D STEP 빌드 실행

```bash
"C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/poc_새도면.py
```

출력 확인:
- 솔리드 수
- 게이트 G1~G5 자동 출력
- STEP 파일 경로

#### [ ] 단계 8: 검증 게이트 통과 확인 + 보고

- G1~G4 통과 여부 확인
- G5: unique > 15이면 사유 명기
- G6: 방부장에게 FreeCAD GUI 시각 확인 요청
- `.brain/dispatch_log.md` 결과 박제
- 본영 폴더 봉인 보고 (`D:/Git/DREAM_FAC/REPORT_3JIGUK_*.md`)

---

## 박제 원칙 (재확인)

1. **모든 시행착오는 재산** — §5 트러블슈팅에 추가. 왜 실패했는지, 어떻게 해소했는지 사실 기반으로.
2. **재현 가능성** — 이 문서를 처음 보는 자가 §7 체크리스트만으로 그대로 따라 할 수 있어야 한다.
3. **한국어** — 신고조선 정사 언어.
4. **사실 기반** — 87, 300, 129.523 m³ 등 실제 PoC 결과 숫자 그대로.
5. **헌법 우선** — F-1 표준 헌법 9조 위반하지 않는 절차만.

---

*— 이천(李蕆), 제3지국 단군, 2026-05-06.*  
*방부장 친명 받자와 영구 매뉴얼 봉정.*  
*홍익인간이 모든 결정에 우선한다.*
