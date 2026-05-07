# Master Plan — 좌표 통일 + 부재 정확 파싱 정밀화

> 확정: 2026-05-07 (제2판)
> 단군: 이천(李蕆), 신고조선 제3지국
> 방부장 명령: "좌표 통일 + 부재 정확 파싱 = 두 기본. Track 2는 그 다음"
> 이전 계획: docs/forge_brief.md (투트랙 전략)

---

## 핵심 진단 (탐사로 확정)

두 도면 모두 **시트/동이 동일 도면 안에 격자 라벨로 식별 가능**.

**PKG DXF**:
- 동일 `Y18` 라벨이 X = 317,083 / 947,083 / 1,577,083 — **간격 정확히 630,000mm**
- 또 다른 그룹 757,131 / 1,387,131 / 2,017,131 (PIT/B1F 시트)
- → 한 도면에 6개 시트 (3동 × 2층). 격자 라벨 X 클러스터링으로 자동 분리 가능

**DONG DXF**:
- 시트 BBox는 `f1_anchor_102_9sheets.json`에 9시트 단위로 추출됨
- 인접 시트 W=126,000mm, H=178,200mm 박스 격자 배치
- `DONG_B1F_DX = -126,000` (박제값) ↔ 시트 W와 정확히 일치 → 시트 SW 코너만 자동 검출하면 모든 층 오프셋 자동

---

## 8 Phase 구조

| Phase | 내용 | Forge | 의존 |
|-------|------|-------|------|
| 0 | sheet_detector.py 신설 (PKG/DONG 시트 자동 검출) | — | 없음 |
| 1 | DONG 시트별 X·Y 오프셋 자동 계산 | #A | Phase 0 |
| 2 | PKG 동별 클립 + 좌표 매칭 (#A와 병렬) | #B | Phase 0 |
| 3 | coord_config v2 + 변환 통합 모듈 | #C | Phase 1+2 |
| 4 | WALL LINE 쌍 매칭 (line_pairing.py 활용) | #D | Phase 3 |
| 5 | BEAM·FND 단면 텍스트 자동 매핑 (#D와 병렬) | #E | Phase 3 |
| 6 | 잡선 필터 강화 | #F | Phase 4 |
| 7 | SLAB 다른 동 PKG 추출 + FND 단면 보강 | #G | Phase 2+5 |
| 8 | v14_full 통합 빌드 + 검증 | #H | Phase 1~7 |

---

## Phase 0 — sheet_detector.py 신설

| 항목 | 값 |
|------|-----|
| 파일 | `core/dxf_parser/sheet_detector.py` (신설) |
| 함수 | `scan_pkg_grid_clusters(dxf)`, `scan_dong_sheet_boxes(dxf)` |
| 완료 기준 | PKG 동 3개·시트 6개, DONG 시트 ≥ 8개 자동 검출 |
| 검증 | `python -c "from core.dxf_parser.sheet_detector import ..."` |

---

## Phase 1 — DONG 시트별 X·Y 오프셋 자동 계산 (Forge #A)

| 항목 | 값 |
|------|-----|
| 파일 | `sheet_detector.py::DongSheetDetector` |
| 함수 | `detect(doc) -> dict[sheet_id, SheetTransform]` |
| 완료 기준 | B1F `DX=-126,000` ± 5mm 자동 재생성, 격자 일치 ≤ 50mm |
| 검증 | `python tests/test_dong_sheet_offsets.py` |

알고리즘: `f1_anchor_102_9sheets.py` 시트 BBox 로직 재사용 → 기준 시트(B2F·S30-001) SW를 (0,0)으로 두고 나머지 시트 오프셋 사전 생성.

---

## Phase 2 — PKG 동별 클립 + 좌표 매칭 (Forge #B, Phase 1과 병렬)

| 항목 | 값 |
|------|-----|
| 파일 | `sheet_detector.py::PkgDongDetector`, `coord_unifier.py` 확장 |
| 함수 | `PkgDongDetector.detect(doc)`, `CoordUnifier.match_per_dong()` |
| 완료 기준 | 3개 동 클립 검출, 동별 매칭율 ≥ 95%, 오차 median ≤ 50mm |
| 검증 | `python tests/test_pkg_dong_offsets.py` |

알고리즘:
1. PKG 격자 라벨 X 클러스터 → 동 N개, 클립 박스 = X 중심 ± 80,000
2. 각 동 안의 `00_COLUMN` 추출 → DONG B2F 기둥과 brute-force 매칭
3. 결과: `{101: (TX, TY), 102: (TX, TY), 103: (TX, TY)}`

---

## Phase 3 — coord_config.json v2 + 변환 통합 (Forge #C)

| 항목 | 값 |
|------|-----|
| 파일 | `output/coord_config.json` v2, `core/pipeline/coord_apply.py` (신설) |
| 함수 | `CoordTransformer.from_config(path)`, `transform_member(m)` |
| 완료 기준 | TDD 단위 테스트 80%+, v1+v2 호환, 미지정 부재 폴백 |
| 검증 | `python -m pytest tests/unit/test_coord_apply.py` |

스키마:
```json
{
  "schema_version": 2,
  "dong_sheets": {
    "B2F": {"DX": 0,        "DY": 0, "TZ": -9050},
    "B1F": {"DX": -126000,  "DY": 0, "TZ": -5600},
    "1F":  {"DX": -252000,  "DY": 0, "TZ":   370}
  },
  "pkg_dongs": {
    "101": {"TX": -447970, "TY": 3621813, "clip": [...]},
    "102": {"TX":  182030, "TY": 3621813, "clip": [...]},
    "103": {"TX":  812030, "TY": 3621813, "clip": [...]}
  },
  "legacy": {"TX_PKG": -447970, "TY_PKG": 3621813}
}
```

`Member` dataclass에 `sheet_id`, `dong_id` 옵션 필드 추가.

---

## Phase 4 — WALL LINE 쌍 매칭 (Forge #D)

| 항목 | 값 |
|------|-----|
| 파일 | `stage2_member_classifier.py` 수정, `core/pipeline/wall_pair_resolver.py` 신설 |
| 함수 | `resolve_wall_pairs(wall_lines) -> list[Member]` |
| 완료 기준 | WALL 17,057 → 7,000~8,500개로 축소, 단일 두께 시각화 |
| 검증 | `python tests/test_wall_pair_count.py` |

설계:
- 동일 레이어·시트의 LINE을 모아 `pair_walls()` 호출
- 페어 거리 = 벽 두께, height = 층고
- `min_dist`/`max_dist` 레이어별: SHEAR 250-350, RC 150-250

---

## Phase 5 — BEAM·FND 단면 텍스트 자동 매핑 (Forge #E, #D와 병렬)

| 항목 | 값 |
|------|-----|
| 파일 | `core/pipeline/section_text_mapper.py` 신설 |
| 함수 | `map_beam_section(beam, texts)`, `map_fnd_section(...)` |
| 완료 기준 | BEAM 폴백 사용율 ≤ 5% (≤ 340/6,812), FND 4건 모두 단면 채움 |
| 검증 | `python tests/test_section_mapping.py` |

알고리즘:
- DXF TEXT/MTEXT에서 `\d+[xX×]\d+`, `W\d+`, `F\d+` 패턴 수집
- BEAM 중점에서 ≤ 1,500mm 반경 + 같은 시트 SectionLabel 매칭 (KD-tree)

---

## Phase 6 — 잡선 필터 강화 (Forge #F)

| 항목 | 값 |
|------|-----|
| 파일 | `stage1_structural_filter.py` (DROP 패턴), `core/pipeline/noise_filter.py` 신설 |
| 함수 | `filter_noise_members(coll) -> MemberCollection` |
| 완료 기준 | BEAM 길이 < 500mm 0건, WALL orphan ≤ 10%, 비구조 잔재 0건 |
| 검증 | `python tests/test_noise_filter.py` |

추가 DROP: `00_CENTER`, `S-Defpoints`, `XR*$0$A-CEN-1`, `XR*$0$AH-계단상부선`, `0-Pile`

---

## Phase 7 — SLAB 다른 동 + FND 단면 보강 (Forge #G)

| 항목 | 값 |
|------|-----|
| 파일 | `core/pipeline/slab_extractor.py` 신설, `tests/build_v9_clean.py` 수정 |
| 함수 | `extract_slabs_per_dong(doc, pkg_dongs) -> list[Member]` |
| 완료 기준 | SLAB ≥ 800건, FND 4/4 단면 채움 |
| 검증 | `python tests/test_slab_per_dong.py` |

---

## Phase 8 — v14_full 통합 빌드 + 검증 (Forge #H)

| 항목 | 값 |
|------|-----|
| 파일 | `tests/build_v14_full.py`, `tests/test_full_build_validation.py` |
| 함수 | `main()`, `validate_full_build(step) -> ValidationReport` |
| 완료 기준 | (a) BBox X ≤ 250m (1.4km → 정상), (b) 솔리드 16,000~18,000, (c) 잘못된 위치 0건, (d) 빌드 < 5분 |
| 검증 | `freecadcmd build_v14_full.py && python test_full_build_validation.py` |

검증 항목:
1. 동별 BBox 분리도 — 101동/102동/103동 X폭 ≤ 70m
2. WALL 두께 통계 — 200/300mm 둘 중 하나
3. BEAM 단면 폴백율 ≤ 5%
4. FND 4/4 솔리드

---

## 병렬 분배

```
Phase 0 (단독)
   │
   ├── Phase 1 (Forge #A) ── DONG 시트
   └── Phase 2 (Forge #B) ── PKG 동
        │
        Phase 3 (Forge #C) ── coord_config v2
            │
            ├── Phase 4 (Forge #D) ── WALL 페어링
            └── Phase 5 (Forge #E) ── 단면 매핑
                 │
                 ├── Phase 6 (Forge #F) ── 잡선 필터
                 └── Phase 7 (Forge #G) ── SLAB·FND
                      │
                      Phase 8 (Forge #H) ── 통합 검증
```

---

## TDD 의무 (testing.md 80% 최소 커버)

각 Phase RED → GREEN → REFACTOR. 신설 모듈 반드시 테스트 선행.

- `tests/unit/test_sheet_detector.py` — Phase 0·1·2
- `tests/unit/test_coord_apply.py` — Phase 3
- `tests/unit/test_wall_pair_resolver.py` — Phase 4
- `tests/unit/test_section_text_mapper.py` — Phase 5
- `tests/unit/test_noise_filter.py` — Phase 6
- `tests/unit/test_slab_extractor.py` — Phase 7
- `tests/test_full_build_validation.py` — Phase 8

---

## Track 2 (후순위)

방부장 지시 (2026-05-07): "트랙 2는 그 다음으로 미룬다"

본 정밀화 (Phase 0~8) 완료 후 시작:
- Track 2-A: 골조선 Step 4 연결 (방향<5° + gap<800mm)
- Track 2-B: 기둥-기둥 직선 수동 삽입
- Track 2-C: stage3 골조선→부재 추출
- Track 2-D: build_final_track2.py

---

## 절대 금지 (공통)

- 추측값 사용 금지
- 대충 일부만 처리 금지
- Z값 임의 지정 금지
- 기존 `core/` 모듈 무단 수정 금지 (확장만)

---

*홍익인간이 모든 결정에 우선한다.*
