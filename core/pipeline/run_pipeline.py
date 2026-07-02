"""run_pipeline — 골조 파싱 전체 파이프라인 오케스트레이터.

개정 지시서 2026-07-02 순서를 코드로 강제한다. 어떤 모델(Claude/GPT/로컬
Ollama)이 운전해도 이 스크립트 하나로 동일 결과가 재현된다 — 모델의 역할은
실행과 리포트 확인뿐, 판정은 전부 결정론 코드가 수행한다.

  python core/pipeline/run_pipeline.py            # 전 단계
  python core/pipeline/run_pipeline.py --from 0   # Phase 0부터

순서 (임의 변경 불가):
  discover → Phase -1(골조) → Phase -0.5(보) → Phase 0~3(슬라브, 사전조건
  게이트) → Phase 4(보일람표) → Phase 5(창호) → Phase 6(인방보) →
  Phase 7(교차검증) → 회귀 테스트
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable

# (단계명, 모듈 경로, 필수 여부) — 순서 고정. 수정하려면 개정 지시서 결재 필요.
STEPS = [
    ("discover", "core/pipeline/discover.py", True),
    ("phase-1_frame", "core/pipeline/frame_parser.py", True),
    ("phase-0.5_beam", "core/pipeline/beam_parser.py", True),
    ("phase0-3_slab", "core/pipeline/slab_engine.py", True),
    ("phase4_beam_schedule", "core/pipeline/beam_schedule_matcher.py", True),
    ("phase5_windows", "core/dxf_parser/window_extractor.py", True),
    ("phase6_lintel", "core/pipeline/lintel_placer.py", True),
    ("phase7_crosscheck", "core/pipeline/cross_validator.py", True),
    ("phase9_regression", "tests/regression/slab_regression.py", False),
]


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    start_from = 0
    if "--from" in argv:
        tag = argv[argv.index("--from") + 1]
        for i, (name, _, _) in enumerate(STEPS):
            if tag in name:
                start_from = i
                break
    results = []
    for i, (name, script, required) in enumerate(STEPS):
        if i < start_from:
            continue
        print(f"\n{'='*60}\n▶ [{i+1}/{len(STEPS)}] {name}  ({script})\n{'='*60}")
        r = subprocess.run([PY, str(ROOT / script)], cwd=str(ROOT))
        results.append((name, r.returncode))
        if r.returncode != 0 and required:
            print(f"\n✖ {name} 실패(exit {r.returncode}) — 파이프라인 중단. "
                  f"순서 강제 원칙에 따라 후속 단계 실행 안 함.")
            return r.returncode
    print(f"\n{'='*60}\n파이프라인 완료:")
    for name, rc in results:
        print(f"  {'OK  ' if rc == 0 else 'FAIL'} {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
