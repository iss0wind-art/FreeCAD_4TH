# 🧠 신고조선 제3지국 — 전두엽 (Frontal Lobe)

> 이천(李蕆) 지국 단군의 총괄 지휘 센터.
> 본영 단군(Opus 4.7, `D:\GIT\dream-fac\`)의 분담 아래 자율 운영.
> 7-Piece Kit #5 — 전임자(임시 관리자) 시점에서 이천 시점으로 갱신 (2026-04-26).

---

## 📌 현재 추진 상태 (Status) — 2026-05-06 야간 갱신

- **단계**: v9 빌드 완성. 부재별 개별 솔리드 + BOQ. 좌표 정합 70%.
- **방부장 기준 2026-05-06**: 골조(콘크리트 프레임)만. 부재 하나하나 개별 ID.
- **완성 모듈** (`core/dxf_parser/`):
  - `entity_scanner.py` — 전수 엔티티 스캔 (iter_all = 모델공간 좌표 반환 확인)
  - `ev_detector.py` — E/V 코어 기준점 ← **다음 세션 핵심**
  - `coord_unifier.py` — 다중 도면 좌표 통일
  - `structural_extractor.py` — S-GIRDER LINE + 기둥 추출
  - `grid_extractor.py` — 격자선·기준점
  - `pipeline.py` — 단일 진입점
- **단위 테스트**: 75건 전체 PASS
- **최신 3D 모델**: v9 — **7,411 솔리드, 15,464 m³, 부재별 ID**
- **BOQ**: `output/v9_boq.json` (기둥 C1/TC1, 보 400X800/500X600 등 도면 원래 이름)
- **미완성**: DONG↔PKG 정밀 정합 (E/V 코어로 교체 필요), 주차장 보, 슬라브

---

### 🔑 검증된 오프셋 (씨앗)
```
DONG_B1F_DX = -126000mm  (에이전트 160쌍 거리 0mm 확인)
PKG_B1F_DX  = -630000mm  (Y1 기준점 검증)
TX_PKG      = -448000mm  (미흡, E/V 코어로 교체 필요)
TY_PKG      = +3622000mm
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
| 정도전 1지국 | BOQ (SketchUp 기반 1,163 spec 자산) | 형제 지국 |
| 이순신 2지국 | POPEYES/H2OWIND (현장 운영) | 형제 지국 |
| 다중 트랙 병렬 시공 | **Forge `/orchestrate`** 에이전트 군 | Phase 1 시점 가동 |
| 코드 리뷰 / TDD / 보안 | Forge sub-agents (planner, code-reviewer, tdd-guide, security-reviewer) | 자동 라우팅 |

> 정도전 시절 가상팀 5인(개팀장·최태산·서지훈·권아영·강동진)은 Forge 에이전트 군과 본영 페르소나 군단으로 흡수되었다. 본 brain.md에서는 더 이상 호명하지 않는다.

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
