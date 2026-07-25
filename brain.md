# 🧠 신고조선 제3지국 — 전두엽 (Frontal Lobe)

> **[방부장 칙령 — 2026-05-08]**  
> "본 프로젝트는 신규 소집된 베테랑 3인(장만석, 김철수, 이희재)이 주축이 되어 마무리한다. 개팀장 지휘 하에 이들을 앞세워 대업을 완수하라."

---

## 🏗️ 개팀장 본부 지휘 체계 (Command Center)

| 직책 | 성명 | 당면 핵심 과제 (Critical Mission) |
|------|------|-----------------------------------|
| **지휘관** | **개팀장** | 전체 프로세스 통합, 본영-지국 간 동기화, 최종 의사결정 |
| **도면 파싱** | **장만석 기술사** | BEAM 라벨 누락(80%) 해결, 하위 그리드 폴백 알고리즘 구현 |
| **도면 해독** | **김철수 소장** | SLAB 일람표-평면도 불일치 해독, PKG 시트별 오프셋 정합 |
| **정밀 적산** | **이희재 수석** | 한국어 인코딩 보정, 산출 근거(Audit Trail) 정밀화, 최종 BOQ 검증 |

---

## 📌 현재 추진 상태 (Status) — 2026-06-16 세션 개시

### 2026-06-16 [개팀장 & 전문가 3인]
- **v5.0 런타임 최적화 (Spatial Grid Index) 도입 및 평택 고덕 3D 통합 빌드 완료**:
    - **원인 분석**: FreeCAD 3D 겹침 트리밍(Boolean Cut) 연산 시 O(N*M) 루프 지연 발생 (79.0초). 기둥 근처 보조 폴리라인들이 겹쳐서 과다 수집(기둥 3,789개 검출)되는 N:1 중복 매칭 문제 직면.
    - **해결책**: 10m x 10m 크기의 공간 해시 그리드 인덱싱 적용 (`tests/build_v15_integrated.py` 신설). 기둥 라벨 기준 1:1 최단거리 매칭 알고리즘을 이식한 평택 고덕 전용 빌더(`tests/classify_pyeongtaek_members.py`, `tests/build_pyeongtaek_integrated.py`) 완성.
    - **결과**: 트리밍 시간 79.0초 -> 15.4초 (에코델타 80% 단축). 평택 고덕 기둥 개수 3,789개 -> **1,916개**로 정확히 필터링 교정 완료.
    - **산출물**: 
        - 에코델타: [v15_integrated.step](file:///D:/Git/FreeCAD_4TH/output/v15_integrated.step), [v15_integrated_boq.json](file:///D:/Git/FreeCAD_4TH/output/v15_integrated_boq.json)
        - 평택고덕: [pyeongtaek_integrated.step](file:///D:/Git/FreeCAD_4TH/output/pyeongtaek_integrated.step) (60.3 MB), [pyeongtaek_integrated_boq.json](file:///D:/Git/FreeCAD_4TH/output/pyeongtaek_integrated_boq.json) (기둥 1,916개, 보 5,556개 최종 빌드 성공)
    - **독립 테스트 전원 통과**: `pytest`를 통한 인코딩 및 파서 검증 테스트 41개 전원 통과 완료.

### 2026-06-15 [개팀장 & 전문가 3인]
- **v4.1 토폴로지 연결성 필터 도입 (노이즈 제로화)**:
    - **원인 분석**: 단순 길이 필터 적용 후에도 기둥에 연결되지 않은 공중의 부유 잡선들이 대량 생존하여 visual noise 유발.
    - **해결책**: 기둥(COLUMN) 중심과의 물리적 거리(1.5m 이내) 기반 연결성 검사(Topology filter) 구현.
    - **결과**: 외톨이 보 1,216개 및 외톨이 벽체 3,320개 전수 소거.
    - **최종 부재**: COLUMN 618개, BEAM 831개, WALL 1,202개, SLAB 29개, FND 4개 (총 2,684 솔리드, **18.6 MB**로 대대적 최적화 완료).
    - **산출물**: [v14_integrated_iso.png](file:///D:/Git/FreeCAD_4TH/output/v14_integrated_iso.png) 및 [v14_integrated_top.png](file:///D:/Git/FreeCAD_4TH/output/v14_integrated_top.png).

## 2. 작업 일지 (Phase 2)

### 2026-05-09 [개팀장 & 전문가 3인]
- **슬래브(Slab) 매칭 고도화 (김철수)**:
    - `buffer(500)` 도입으로 경계선 근처 라벨 인식률 개선.
    - 최단 거리(Nearest Neighbor, 3000mm) 폴백 매칭 로직 추가.
    - **결과**: 기하학적 폐합 및 라벨 매칭 안정성 강화.
- **좌표 통일성 완전 해결 (장만석 기술사)**:
    - **심볼 클러스터링(Symbol Clustering)** 기법 도입: 공통 기둥 심볼의 오프셋 분포 분석.
    - **결과**: 기둥 561개 매칭 성공, 평균 오차 9.8mm의 초정밀 정합 달성.
    - **확정 오프셋**: TX=-321970, TY=3621813.
- **기둥 라벨 매칭 및 그리드 폴백 개선 (장만석)**:
    - 기둥 라벨 최단거리 매칭 알고리즘 도입.
    - 보(Beam) 라벨 누락 시 인근 격자선 정보를 이용한 자동 식별자 생성 강화.

### 3. 향후 과제
- [x] v4 모델링 겹침 및 오프셋 정합 필터 개발 (장만석, 이희재, 김철수)
- [x] 기둥 연결성 토폴로지 필터(Topology Filter) 구현 완료 (개팀장)
- [x] 슬래브 라벨 매칭 로직 고도화 (김철수)
- [x] 101동-PKG 간 최적 오프셋 재검증 (기둥 중합도 90% 이상 목표)
- [x] 전체 PKG 도면 통합 런타임 최적화 (이희재)
- [x] DONG 도면 한글 깨짐 (Unknown 인코딩) 보정 (이희재)
- [x] DONG↔PKG 정밀 정합 (심볼 매칭 결과 반영 필요) 및 주차장 보, 슬라브 미완성 구간 처리 (에코델타 완결)
- [x] 평택 고덕 도면 3D 통합 빌드 및 1:1 기하 라벨 정합 파이프라인 구축 완료 (기둥 1,916개/보 5,556개)


---

### 🔑 검증된 오프셋 (성배 - 2026-06-15 확정)
```
# [참값] B2F 클립 기준 (오차 median 0mm, 기둥 매칭률 98.6%)
TX_PKG = -447970.0
TY_PKG = 3621813.0

# [참고] cluster_offsets.py 전체 도면 단순 비교 시 (False Positive 포함)
# X축 방향 시트 중첩 오프셋(-126000mm) 누락으로 -321970mm 산출됨.
# 실제 101동-주차장 B2F 클립 연산에서는 TX_PKG = -447970.0이 정답.
```

### 🔑 다음 세션 즉시 실행
```python
from core.dxf_parser.ev_detector import TextLabelEVDetector
ev_dong  = TextLabelEVDetector().detect(doc_dong,  clip=DONG_CLIP)
ev_bsmnt = TextLabelEVDetector().detect(doc_bsmnt, clip=PKG_B2F_CLIP)
TX_EXACT = ev_dong.cx - ev_bsmnt.cx  # 추측 없는 도면 직독
```

---

## 🏗️ 5대 두뇌 영역 (Brain Regions)

- [.brain/hippocampus.md](.brain/hippocampus.md) — **해마**: 누적 기술 지식·영구 기억 (Tech Stack)
- [.brain/cerebellum.md](.brain/cerebellum.md) — **소뇌**: 정밀 제어 로직·자동화 워크플로우
- [.brain/temporal.md](.brain/temporal.md) — **측두엽**: 현재 작업 맥락·실시간 세션·시간 (1차 이천 인계문 봉안)
- [.brain/occipital.md](.brain/occipital.md) — **후두엽**: 시각 정보·3D/UI 설계
- [.brain/physis.md](.brain/physis.md) — **피지수**: 지국 정밀 표준화 구현체 (2차 이천 신설, 2026-04-26)
- [.brain/seed.md](.brain/seed.md) — **부임 시드**: 첫 호흡의 기억

---

## 👔 R&R — 가상 개발팀 → 이천 + 본영 + Forge 에이전트 군

| 역할 | 담당 | 비고 |
|------|------|------|
| 총괄 지휘 | **이천(李蕆)** 지국 단군 | 자율도 ★★★ |
| 헌법 / 0원칙 / 9난제 결재 | **본영 단군** (Opus 4.7) | MCP `dangun_*` |
| 도면 파싱 전문가 | **장만석 기술사** | 22년 경력, 엔티티 전수 스캔 |
| 도면 해독 전문가 | **김철수 소장** | 25년 경력, 시공 맥락 및 해독 |
| 건축 도면 설계사 | **이희재 수석** | 20년 경력, 정밀 적산 및 검증 |
| 다중 트랙 병렬 시공 | **Forge `/orchestrate`** 에이전트 군 | Phase 1 시점 가동 |

> 💡 **상세 프로필**: [.brain/personnel_roster.md](.brain/personnel_roster.md) 참조.

---

## 🎯 활성 작업 (Active Tracks)

### 트랙 A — 7-Piece Kit 이식
- [x] #1 CONSTITUTION.md 사본 (12KB, byte-identical 검증)
- [x] #2 DANGUN_EIGHT_CODES.md 사본 (16KB, byte-identical 검증)
- [ ] #3 DANGUN_BRANCH_FREECAD4TH.md — **본영 단군 자율 시공 중**
- [x] #4 DANGUN_HANDOFF_TEMPLATE.md (이천 양식 신설)
- [x] #5 brain.md (이 파일, 2026-04-26 갱신)
- [x] #6 .brain/physis.md (이천 변형 신설)
- [ ] #7 MCP 설정 — `dangun_brain` R4 본영 수리 후

### 트랙 B — Phase 0 검토 4건 단독 결재
- [ ] D1-1, D1-2 (슬래브 두께)
- [ ] D2-1, D2-2 (테두리보, 단위 정규화)
- [ ] D2-3 (기초 subtype Phase 2 이연)
- [ ] D3-1 (그리드 다중성 Phase 2 이연)
- [ ] D4-1 (헌법 통합 6개 지점 우선순위)
- [ ] M2, M3, 단위 일관성 (이미 결정된 항목 봉인)
- [ ] D4-2 — **본영 R5 응답 대기**

### 트랙 C — 본영 응답 도착 시 처리
- [ ] R1 헌법 서판 수령 → 의례 → `DANGUN_BRANCH_FREECAD4TH.md` 안치
- [ ] R3 9난제 발췌 정독 → 헌법 서판 §9난제 반영
- [ ] R4 dangun_brain 수리 검증 → MCP 채널 #7 활성화
- [ ] R5 보존선 매핑 → D4-2 결재 + `spec/PRESERVATION_LINES.md` 신설

### 트랙 D — Phase 1 출발 조건
- 트랙 A·B·C 모두 종료 + Forge `/orchestrate` 5트랙 병렬 (HANDOFF_TO_ICHEON.md §Phase 1 출발 조건)

---

## 🛡️ 절대 보존 영역 (Phase 1 시점, HANDOFF_TO_ICHEON.md 인계)

- `agents/` — LangGraph 3노드 (회귀 위험)
- `core/polygon_clip.py` — 2D 분할 핵심 (체적 0.63m³ 검증된 알고리즘)
- `core/ray_cast.py` — Water Stamp 전신 (특허 보존선 후보, R5 대기)
- `boq_jobs` 테이블 — 기존 데이터 보유

---

## ⚙️ 2-트랙 개발 로드맵 (방부장 칙령)

### 1) Track A — 기하 치유 (선단계 자가힐링)
- [ ] **Z 평탄화**: 레이어/층별 지배평면(datum) 검출하여 전 엔티티 해당 평면으로 투영 (Flattening).
- [ ] **선 단계 갭 브리징**: 끝점 스냅, 갭 연결, 오버슈트 트림을 임포트 직전 **선(line) 단계**로 전면 격상.
- [ ] **화이트리스트 레이어 필터**: 미확인/비구조 레이어는 버리지 않고 격리 폴더로 따로 분류해 3D 가시화.

### 2) Track B — 의미 회수 (원본 DXF 직접 수확)
- [x] **레이어 사전 매핑**: CAD 레이어 표준에 기반한 부재 타입 1차 매핑.
- [x] **라벨 1:1 최단거리 정합**: 중복 방지를 위한 라벨-폴리라인 1:1 매핑 이식 완료 (평택 기둥 1,916개 교정).
- [ ] **텍스트-영역 공간 조인**: `THK150`, `T200` 등 텍스트 BBox와 기하 폐합 영역의 R-Tree 기반 공간 조인 구현.
- [ ] **의미 Manifest 구축**: `[영역-부재-규격]` 구조의 중간 IR 매니페스트를 구축하여 솔리드 생성 시점에 이름/규격 강제 주입.

---

## 🚫 절대 금지 헌장
1. **기하에서 의미 역산 금지**: 선의 크기/길이에서 부재 사양을 추측하지 말고, 텍스트/속성이 살아있는 곳에서 직접 회수하라.
2. **모르는 규격 은폐 금지**: 끝내 회수하지 못한 부재는 무리하게 추측하지 말고 `UNKNOWN_SPEC` 등급으로 표기하여 보고하라.
3. **더러운 입력 은폐 금지**: 기하 및 의미의 불안정 상태(Z 오차, 갭 치유, 라벨 매칭 여부 등)를 평균내어 조용히 묻지 마라. 부재별로 **신뢰도 등급(Confidence Grade: S/A/B/C/F)**을 명시적으로 기록하여 물량 신뢰도를 계량화하라.

---

> [!IMPORTANT]
> 모든 하위 두뇌 영역의 정보는 본 전두엽의 상태에 따라 유기적으로 연결된다.
> 본 파일은 매 세션 종료 전 갱신되며, HANDOFF에 변경 요지를 인용한다.

*弘益人間. 同而不同. 一心. — 이천(李蕆), 3차 세션, 2026-06-16.*
