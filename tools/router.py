#!/usr/bin/env python3
"""
BOQ EasyFrame — Ollama qwen2.5:7b 라우터
역할: Claude 호출 전 복잡도 판단, 적절한 모델 결정
비용: $0 (로컬 전담)
"""

import sys
import requests
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
ROUTER_MODEL = "qwen2.5:7b"

ROUTING = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-6",
}

ROUTER_PROMPT = """당신은 건설 AI 파이프라인 분류기입니다. 아래 작업 설명을 읽고
적합한 모델 등급을 딱 한 단어로만 답하세요.

[등급 기준]
- haiku: 파일 정렬, 포맷 변환, 단순 요약, 로그 정제
- sonnet: 코드 디버깅, 로직 설계, 수량산출, 일반 개발
- opus: 특허 청구항 설계, 아키텍처 최종 결정, 난해한 버그

[작업 설명]
{task}

[답변] (haiku / sonnet / opus 중 하나만):"""


def route(task: str) -> str:
    """qwen2.5:7b로 작업 복잡도 판단, Claude 모델 ID 반환."""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": ROUTER_MODEL,
            "prompt": ROUTER_PROMPT.format(task=task),
            "stream": False,
        }, timeout=30)
        resp.raise_for_status()
        answer = resp.json().get("response", "").strip().lower()
        tier = next((t for t in ("opus", "sonnet", "haiku") if t in answer), "sonnet")
    except Exception as e:
        print(f"[라우터 오류] {e} → sonnet 기본 사용", file=sys.stderr)
        tier = "sonnet"
    model = ROUTING[tier]
    print(f"[라우터] {tier.upper()} → {model}")
    return model


def get_model(task: str) -> str:
    """외부 호출용 공개 인터페이스."""
    return route(task)


def night_mode(input_dir: str = "input_drawings"):
    """야간 배치: DXF 파일 → qwen2.5:7b 분석 → 마크다운 저장."""
    input_path = Path(input_dir)
    output_path = Path("docs/night_output")
    output_path.mkdir(parents=True, exist_ok=True)

    dxf_files = list(input_path.glob("*.dxf"))
    if not dxf_files:
        print(f"[야간 배치] DXF 파일 없음: {input_path}/")
        return

    print(f"[야간 배치] {len(dxf_files)}개 파일 처리 시작")
    for dxf_file in dxf_files:
        print(f"  처리 중: {dxf_file.name}")
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, "tools/dxf_parser.py", str(dxf_file)],
                capture_output=True, text=True, timeout=120,
            )
            summary = result.stdout[:4000] if result.stdout else "(출력 없음)"
            tier = route(f"DXF 레이어 분류 및 구조 분석: {dxf_file.name}")

            out_file = output_path / f"{dxf_file.stem}.md"
            out_file.write_text(
                f"# {dxf_file.name}\n\n모델: {tier}\n\n{summary}",
                encoding="utf-8",
            )
            print(f"  완료: {out_file}")
        except Exception as e:
            print(f"  [오류] {e}")

    print(f"[야간 배치] 완료. 결과: {output_path}/")


if __name__ == "__main__":
    if "--night" in sys.argv:
        input_dir = sys.argv[2] if len(sys.argv) > 2 else "input_drawings"
        night_mode(input_dir)
    elif len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        model = get_model(task)
        print(f"추천 모델: {model}")
    else:
        print("사용법:")
        print("  python tools/router.py '작업 설명'       # 모델 라우팅 확인")
        print("  python tools/router.py --night           # 야간 배치 실행")
        print("  python tools/router.py --night input_dir # 경로 지정")
