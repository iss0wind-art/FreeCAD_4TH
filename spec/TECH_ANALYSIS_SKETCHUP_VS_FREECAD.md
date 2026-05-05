---
title: SketchUp ↔ FreeCAD 상호 대체 가능성 기술 분석
date: 2026-05-04
status: 검토 완료 / 시행 보류
---

# SketchUp ↔ FreeCAD 상호 대체 가능성

> 결론: **양방향 모두 기술적으로 가능**. 시행 여부는 차후 재검토.

---

## 전제

개념(BOQ 자동화)은 동일. 도구만 다름.
- 1지국: SketchUp + Ruby 플러그인
- 3지국: FreeCAD + Python 백엔드

---

## SketchUp → 3지국 확장 가능 여부

| 기능 | 가능 여부 | 비고 |
|------|----------|------|
| 부재 3D 생성 | YES | Ruby API |
| 체적/면적 계산 | YES | 내장 기능 |
| YAML 파싱 | YES | Ruby gem |
| 헤드리스 서버 | 제한적 | GUI 종속, CLI는 Pro 한정 |

## FreeCAD → 1지국 확장 가능 여부

| 기능 | 가능 여부 | 비고 |
|------|----------|------|
| 부재 3D 생성 | YES | Python API |
| BOQ 계산 | YES | |
| SketchUp 플러그인 UX | NO | 다른 방식으로 대체 필요 |
| 헤드리스 자동화 | YES (우위) | 서버 운용에 유리 |

---

## 핵심 차이

- SketchUp: **사람이 모델 열어두고** 돌리는 구조
- FreeCAD: **서버에서 자동으로** 돌리는 구조

---

## 결정

시행은 보류. 차후 필요 시 재검토.
