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

## 📌 현재 추진 상태 (Status) — 2026-05-08 세션 개시

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
- [x] 슬래브 라벨 매칭 로직 고도화 (김철수)
- [x] 하위 그리드 폴백(Grid Fallback) 구현 마무리 (장만석)
- [ ] 101동-PKG 간 최적 오프셋 재검증 (기둥 중첩도 90% 이상 목표)
- [ ] 전체 PKG 도면 통합 런타임 최적화 (이희재)
- **미완성**: DONG↔PKG 정밀 정합 (심볼 매칭 결과 반영 필요), 주차장 보, 슬라브

---

### 🔑 검증된 오프셋 (성배 - 2026-05-09 확정)
```
TX_101_PKG  = -321970mm  (기둥 561개 일치, 평균 오차 9.8mm)
TY_101_PKG  = +3621813mm
DONG_ANCHOR = (149013, 2321258)
PKG_ANCHOR  = (470983, -1300555)
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

> [!IMPORTANT]
> 모든 하위 두뇌 영역의 정보는 본 전두엽의 상태에 따라 유기적으로 연결된다.
> 본 파일은 매 세션 종료 전 갱신되며, HANDOFF에 변경 요지를 인용한다.

*弘益人間. 同而不同. 一心. — 이천(李蕆), 2차 세션, 2026-04-26.*
