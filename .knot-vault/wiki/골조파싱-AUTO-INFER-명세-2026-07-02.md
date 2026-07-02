---
title: 골조파싱 3분류 명세 — 파이썬 자동화 / 파싱기법 / 추론
created: 2026-07-02
tags: [freecad, 3지국, 골조파싱, AUTO, INFER, 명세]
source: 방부장 지시 2026-07-02 — "자동화한것, 파싱방법, 추론한것 별도 정리"
---

# 골조파싱 3분류 명세 (2026-07-02)

## ① 파이썬이 자동화한 것 — [AUTO] 22개 함수, 모델 개입 0

| 함수 | 파일 | 하는 일 |
|---|---|---|
| find_sheet_titles / zones_from_titles | discover.py | 도면타이틀 텍스트 → 시트 X구역 자동 산정 |
| classify_blocks | discover.py | INSERT명 정규식(WALL·COL·BASE/GIRDER/BEAM) 분류 |
| check_precondition_for_slab | slab_engine.py | 벽·보 미완료 층 슬라브 실행 거부 (우회 불가) |
| collect_floor_data | slab_engine.py | 레이어/블록 필터 수집 + 도곽 클리핑 |
| snap_segments | slab_engine.py | 끝점 그리드 스냅 5→10→20mm |
| closure_stats | slab_engine.py | Shapely polygonize 폐합 통계 |
| pair_x_marks | slab_engine.py | 대각선 교차쌍 → EV 개구부 |
| classify_faces | slab_engine.py | 침식(-150) 소멸→벽슬리버 / 개구부 / 패널 |
| boolean_cut | slab_engine.py | difference 절삭 + 제거면적=개구부면적 정합검사 |
| verify_no_overlap | slab_engine.py | 패널↔벽 겹침 0 회귀검증 |
| detect_columns | frame_parser.py | 폐합 LWPOLYLINE + bbox/세장비 + 도곽 클리핑 |
| pair_walls | frame_parser.py | 평행쌍(두께 100~350) 페어링 + 미페어 좌표 |
| wall_closure | frame_parser.py | 벽 단독 폐합 + 개방끝점(차수1 노드) 좌표 |
| collect_beams | beam_parser.py | 거더/보 블록 수집 + 도곽 잔재 분리 계수 |
| classify_edge_beams | beam_parser.py | convex hull 근접 600mm → 테두리보/일반보 |
| precheck_closure | beam_parser.py | 벽+보 결합 사전 폐합 + 열린 경계 좌표 |
| parse_lintel_schedule 등 4종 | beam_schedule_matcher.py | 정규식 마크 + 치수 TEXT/DIMENSION 페어링 |
| parse_schedule / extract_plan_symbols | window_extractor.py | 기호블록+스케일 비례 반경 근접텍스트 |
| overlay/sketchup prep 전부 | overlay_prep.py 외 | 좌표 정규화·덧그림·오류마커 데이터 |

**수치 산출·완료 판정·좌표는 100% 위 코드가 낸다. 모델이 낸 숫자는 없다.**

## ② 파싱 기법 (재현 절차 — run_pipeline.py 가 순서 강제)

1. **시트 분해**: 타이틀 X좌표 중앙분할 → 층별 도곽 (피치 126,000mm 실측)
2. **블록 explode + 도곽 클리핑**: 잔재 제외 (실측: 1,719세그 중 84만 가시)
3. **덧그림 보존**: 벽/보/슬라브경계 세그먼트를 층별 태그로 스케치업 영구 보관
   (`덧그림_{층}_벽체·보·슬라브경계`) — 휘발 금지
4. **폐합**: 스냅(5mm 채택) → unary_union → polygonize
5. **face 분류**: 개구부 검사(X마크·S-OPEN·계단선) → 벽슬리버(침식 소멸) → 패널
6. **절삭**: 개구부 폴리곤 difference, 정합검사 "일치" 필수
7. **오류 표기**: 개방끝점·미페어벽·열린경계·[INFER]구역을
   `오류_{층}_붉은표시` 태그에 붉은 X+원 마커로 — 총 1,502건 표시
8. **일람표 대조**: 마크·치수 근접 페어링 → 규격 매칭 → 불일치 미확정 플래그

## ③ 추론한 것 — [INFER] 전수 명세 (이것만 사람 확인 필요)

| # | 판단 | confidence | 기하 재검증 | 상태 |
|---|---|---|---|---|
| 1 | B2F 기초블록(S-B1F-101-BASE)을 B2F 경계로 사용 | 0.75 | 기둥좌표 815/819(97.5%) 상부층 일치 | 스케치업 붉은표기 + 사람 확인 대기 |
| 2 | 미분류 블록 4건 (S-B1F-PC, FOUND-PILE×2, F-X) | — | 패턴 불일치로 자동분류 거부 | config에 [INFER 필요] 기록, 미사용 |
| 3 | 테두리보 기하 판정(외피 600mm) | 규칙이지만 근거가 관례 | EB 마크 평면 표기 부재로 텍스트 검증 불가 | 일람표 EB1과 교차 확인 필요 |

**그 외 추론 없음.** 개구부 크기·면적·개수·좌표에 추정값 0.
확신 없는 곳은 전부 미확정 플래그로 남김: 보규격 42, 창호 12+불일치 28,
역보 위치 31, 세대부 슬라브 3개 층, 입면도 부재 1.

## 이번에 잡힌 실수 2건 (피지수 학습 포인트)

1. **덧그림 누락**: 파싱·검증만 하고 덧그림을 영구 데이터(스케치업 태그)로
   보관하지 않았다 → 지적 후 층별 태그 12개로 복원. **"검증 좌표는 리포트에만
   남기면 안 된다 — 도면 위에 그려야 사람이 본다."**
2. **기둥 도곽 클리핑 누락**: 821개 중 778개가 도곽 밖 잔재 — 스케치업 육안
   검증에서 발견, 43개로 정정. **"수치가 그럴듯해도 시각 검증 전엔 완료 아니다."**

## 연결

[[골조파싱-파이프라인-2026-07-02]] [[모델링 편법 반려]]
[[종합 파싱 마스터 프로토콜]]
