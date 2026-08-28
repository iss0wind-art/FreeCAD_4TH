"""
tools/pipeline_worker.py — Ollama + Python 파서 통제 메인 커널
=================================================================
파이프라인 워커는 다음을 통제한다:
  1) DXF 도면 검사 (inspect_drawing.py 호출)
  2) Python 기반 파서 (core/dxf_parser/*)
  3) Ollama LLM 추론 (프롬프트 생성 → 결과 수집)
  4) BOQ/3D 스택 결과물 병합

사용법:
    python tools/pipeline_worker.py <DXF파일> [옵션]

옵션:
    --inspect       도면 검사 (inspect_drawing.py --all)
    --parse         풀 파싱 실행
    --llm           Ollama 추론 실행
    --boq           BOQ 산출
    --all           전체 파이프라인 실행
    --night         야간 백그라운드 워커 (input_drawings/*.dxf 일괄 처리)
    --model         Ollama 모델명 (기본: qwen2.5-coder:7b)

예시:
    python tools/pipeline_worker.py --night                           # 야간 워커 가동
    python tools/pipeline_worker.py input_drawings/101.dxf --all
    python tools/pipeline_worker.py input_drawings/101.dxf --inspect --llm --model gemma3:12b

디렉토리 구조:
    docs/popeyes/           # [최종] 4,000자 규격 프랙탈 마크다운 저장소
    input_drawings/         # [입력] DXF 도면 투입소
    tools/
        pipeline_worker.py  # 본 파일
        inspect_drawing.py  # DXF 검사 도구
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
import glob as _glob
from pathlib import Path
from typing import Any


PIPELINE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PIPELINE_ROOT))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_8B_MODEL = "qwen2.5:7b"


# ──────────────────────────────────────────────────────────
#  유틸
# ──────────────────────────────────────────────────────────

def _fmt(t: float) -> str:
    return f"{t:.1f}s"


def _run_py(args: list[str], cwd: str | None = None) -> dict[str, Any]:
    """Python 스크립트 실행 후 stdout에서 JSON 블록 추출."""
    cwd = cwd or str(PIPELINE_ROOT)
    result = subprocess.run(
        [sys.executable, *args],
        capture_output=True, text=True, cwd=cwd,
        encoding="utf-8", errors="replace",
    )
    out = result.stdout.strip()
    err = result.stderr.strip()
    if result.returncode != 0:
        print(f"  [오류] returncode={result.returncode}")
        if err:
            print(f"  [stderr] {err[:500]}")
        return {"ok": False, "stdout": out, "stderr": err}
    # 마지막 JSON 블록 파싱 시도
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"ok": True, "stdout": out, "stderr": err}


def _ollama_generate(model: str, prompt: str, system: str = "", temperature: float = 0.7) -> str | None:
    """Ollama API /api/generate 호출 (non-stream)."""
    import urllib.request
    import urllib.error

    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        body["system"] = system

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=data,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            resp_data = json.loads(resp.read().decode())
        return resp_data.get("response")
    except TimeoutError:
        print(f"  [Ollama 타임아웃] 300초 초과")
        return None
    except (urllib.error.URLError, ConnectionRefusedError) as e:
        print(f"  [Ollama 연결 실패] {e}")
        return None


# ──────────────────────────────────────────────────────────
#  야간 백그라운드 워커 [No.45] 1·2단계
# ──────────────────────────────────────────────────────────

def self_logging(msg: str) -> str:
    """타임스탬프 붙인 로그 메시지."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"[{ts}] {msg}"


def primitive_dxf_parse(dxf_path: str) -> list[dict[str, Any]] | None:
    """
    1단계: 기계적 노이즈 제거 + 좌표 정제 + TEXT 채굴

    ezdxf로 도면 내 LINE/LWPOLYLINE/MTEXT 등 기하+의미 요소를 읽고
    Z축을 0으로 투사한 후 layer/start/end + TEXT를 남긴다.
    """
    try:
        import ezdxf
    except ImportError:
        print(self_logging("ezdxf 미설치. pip install ezdxf"))
        return None

    try:
        doc = ezdxf.readfile(dxf_path, encoding='cp949')
        msp = doc.modelspace()

        extracted: list[dict[str, Any]] = []
        for entity in msp.query("LINE"):
            s = entity.dxf.start
            e = entity.dxf.end
            extracted.append({
                "layer": entity.dxf.layer,
                "start": [s.x, s.y],
                "end": [e.x, e.y],
            })
        # LWPOLYLINE 도 포함
        for entity in msp.query("LWPOLYLINE"):
            pts = list(entity.get_points())
            for i in range(len(pts) - 1):
                p1 = pts[i]
                p2 = pts[i + 1]
                extracted.append({
                    "layer": entity.dxf.layer,
                    "start": [p1[0], p1[1]],
                    "end": [p2[0], p2[1]],
                })

        # TEXT/MTEXT 의미 채굴 (SL, 층고, 단면, 부재 라벨)
        texts: list[dict[str, Any]] = []
        for entity in msp.query("TEXT MTEXT"):
            try:
                if entity.dxftype() == "TEXT":
                    txt = entity.dxf.text.strip()
                    x = entity.dxf.insert.x
                    y = entity.dxf.insert.y
                else:
                    txt = entity.text.strip()
                    x = entity.dxf.insert.x
                    y = entity.dxf.insert.y
                if txt and len(txt) < 200:
                    texts.append({"text": txt, "x": x, "y": y})
            except Exception:
                pass

        print(self_logging(f"  파싱 완료: 기하 {len(extracted)}개 + TEXT {len(texts)}개"))

        # SL/Z값, 단면, 부재 라벨 1차 분류
        sl_values = {}
        sections = []
        labels = []
        import re
        sl_pat = re.compile(
            r'(B[123]F|B\d+|PIT|1F|2F|3F|RF|지하\s*\d층|옥상)?'
            r'.*?SL'
            r'[^\d\-\+]*'
            r'([+\-]?\d[\d,\.]*)',
            re.IGNORECASE,
        )
        sec_pat = re.compile(r'(\d{2,4})\s*[xX\*]\s*(\d{2,4})')
        slab_t_pat = re.compile(r'(?:T=|t=|두께|THK)\s*(\d{2,3})', re.IGNORECASE)
        beam_h_pat = re.compile(r'(?:H=|h=|높이)\s*(\d{2,4})', re.IGNORECASE)
        col_pat = re.compile(r'(TC|C|EC|AC|PC)?\d+[A-Z]?', re.IGNORECASE)

        for t in texts:
            txt = t["text"]
            # SL 표고
            m = sl_pat.search(txt)
            if m:
                floor_label = m.group(1) or "UNKNOWN"
                val_str = m.group(2).replace(",", "")
                try:
                    sl_val = float(val_str)
                    key = floor_label.strip()
                    if key not in sl_values:
                        sl_values[key] = sl_val
                except ValueError:
                    pass
            # 단면 (WxH)
            m = sec_pat.search(txt)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                if 100 <= w <= 3000 and 100 <= h <= 3000:
                    sections.append({"w": w, "h": h, "text": txt})
            # 슬라브 두께
            m = slab_t_pat.search(txt)
            if m:
                val = int(m.group(1))
                if 100 <= val <= 400:
                    sections.append({"type": "SLAB_T", "value": val, "text": txt})
            # 보 높이
            m = beam_h_pat.search(txt)
            if m:
                val = int(m.group(1))
                if 200 <= val <= 2000:
                    sections.append({"type": "BEAM_H", "value": val, "text": txt})
            # 부재 라벨
            if col_pat.fullmatch(txt):
                labels.append({"label": txt, "x": t["x"], "y": t["y"]})

        print(self_logging(f"  SL 채굴: {len(sl_values)}개, 단면: {len(sections)}개, 라벨: {len(labels)}개"))
        if sl_values:
            print(self_logging(f"  SL값: {json.dumps(sl_values, ensure_ascii=False)}"))

        # 결과 구조: 기하 + 의미 메타 분리
        return {
            "geometry": extracted[:200],
            "texts_sample": texts[:100],
            "sl_values": sl_values,
            "sections": sections[:50],
            "labels": labels[:50],
            "stats": {
                "total_lines": len(extracted),
                "total_texts": len(texts),
                "sl_count": len(sl_values),
                "section_count": len(sections),
                "label_count": len(labels),
            },
        }
    except Exception as e:
        print(self_logging(f"  DXF 파싱 실패: {e}"))
        traceback.print_exc()
        return None


def ask_ollama_brain(prompt_context: str, model: str = DEFAULT_8B_MODEL) -> str:
    """
    Ollama 8B에게 3지국 특허 기준점 및 개구부 규칙 매핑 지시.
    temperature=0.1로 정밀 분류.
    """
    system_prompt = (
        "당신은 한국 RC 구조도면 완전 해체 엔진이다. "
        "도면에서 3D 모델링에 필요한 모든 것을 추출하라: "
        "골조선(기둥/보/벽체 중심선), 기준선(X/Y 격자), "
        "Z 값(SL/층고), 단면(가로x세로/두께/높이), 부재 라벨, "
        "엘리베이터 코어, 개구부, 단차 구간. "
        "확실/추론/보류 3단계 신뢰로 보고하라. 추정 금지. "
        "모든 응답은 반드시 한국어로만 출력하라. 한자 절대 금지."
    )
    # 1회 재시도
    for attempt in range(2):
        response = _ollama_generate(model, prompt_context, system_prompt, temperature=0.1)
        if response:
            return response
        print(self_logging(f"  Ollama 응답 없음 (시도 {attempt+1}/2)"))
    return "오류: Ollama 응답 실패"


def save_to_obsidian(filename: str, content: str) -> list[Path]:
    """
    4,000자 규격 프랙탈 침전: 옵시디언 마크다운으로 분할 적재.

    4,000자 단위로 파일을 분할하여 docs/popeyes/ 에 저장.
    """
    target_dir = PIPELINE_ROOT / "docs" / "popeyes"
    target_dir.mkdir(parents=True, exist_ok=True)

    limit = 4000
    chunks = [content[i:i + limit] for i in range(0, len(content), limit)]

    saved_paths: list[Path] = []
    for idx, chunk in enumerate(chunks):
        if len(chunks) == 1:
            out_path = target_dir / f"{filename}.md"
        else:
            out_path = target_dir / f"{filename}_p{idx + 1}.md"
        out_path.write_text(chunk, encoding="utf-8")
        saved_paths.append(out_path)

    for p in saved_paths:
        print(self_logging(f"  적재: {p.name}"))
    return saved_paths


def run_night_pipeline(
    model: str = DEFAULT_8B_MODEL,
    input_dir: str = "input_drawings",
) -> None:
    """
    야간 백그라운드 웜엔진.

    input_drawings/ 내 모든 DXF를 순회하며:
      1단계 — ezdxf 기계적 파싱 (좌표 정제)
      2단계 — Ollama 8B 기준점 정합 + 벽체선 정리
      결과 — docs/popeyes/ 에 4,000자 마크다운 분할 적재
    """
    print(self_logging("[EasyFrame] 야간 백그라운드 웜엔진 가동..."))

    dxf_dir = PIPELINE_ROOT / input_dir
    dxf_dir.mkdir(parents=True, exist_ok=True)
    dxf_files = list(dxf_dir.glob("*.dxf"))

    if not dxf_files:
        print(self_logging(f"  ⚠ {input_dir}/ 에 DXF 파일 없음"))
        print(self_logging("  도면을 투입한 후 다시 실행하라."))
        return

    print(self_logging(f"  투입 대상: {len(dxf_files)}개 도면"))
    print()

    total_ok = 0
    total_fail = 0

    popeyes_dir = PIPELINE_ROOT / "docs" / "popeyes"
    existing_files_before = set(p.name for p in popeyes_dir.glob("*_cleaned*.md"))
    force_reanalysis = "--force" in sys.argv

    for dxf_path in dxf_files:
        base_name = dxf_path.stem

        # 중복 스킵: 이미 처리된 파일 확인 (--force 시 재분석)
        if not force_reanalysis:
            existing = list(popeyes_dir.glob(f"{base_name}_cleaned*.md"))
            if existing:
                print(self_logging(f"  ⊘ [{base_name}] 이미 처리됨 — 스킵"))
                total_ok += 1
                continue

        print(f'┌─{"─" * 50}')
        print(f"│ [{base_name}] 1단계: 기계적 파싱 시작...")
        print(f'└─{"─" * 50}')

        parse_result = primitive_dxf_parse(str(dxf_path))
        if not parse_result:
            print(self_logging(f"  ❌ [{base_name}] 파싱 실패 — 스킵"))
            total_fail += 1
            continue

        stats = parse_result.get("stats", {})
        sl_vals = parse_result.get("sl_values", {})
        sections = parse_result.get("sections", [])
        labels = parse_result.get("labels", [])
        geom_sample = parse_result.get("geometry", [])[:100]
        texts_sample = parse_result.get("texts_sample", [])[:80]

        prompt = (
            "너는 BOQ EasyFrame 버전3 파이프라인의 핵심인 "
            "1단계(기준점 정합) 및 2단계(벽체선 정리)를 담당하는 "
            "로컬 인공지능 커널이다.\n"
            "아래 4단계 순서에 따라 기계적으로 연산하고, "
            "추정치(임의 판단)를 절대 배제한 정제된 마크다운 결과물만 출력하라.\n\n"
            f"[파일명] {dxf_path.name}\n"
            f"[도면 통계]\n"
            f"- 기하 요소(선/폴리라인): {stats.get('total_lines', 0)}개\n"
            f"- 텍스트: {stats.get('total_texts', 0)}개\n"
            f"- 에스엘 표고: {stats.get('sl_count', 0)}개\n"
            f"- 단면 정보: {stats.get('section_count', 0)}개\n"
            f"- 부재 라벨: {stats.get('label_count', 0)}개\n\n"
        )
        if sl_vals:
            prompt += f"[에스엘 표고(Z값)]\n```\n{json.dumps(sl_vals, ensure_ascii=False, indent=2)}\n```\n\n"
        if sections:
            prompt += f"[단면 정보(가로x세로/두께/높이)]\n```\n{json.dumps(sections[:40], ensure_ascii=False, indent=2)}\n```\n\n"
        if labels:
            prompt += f"[부재 라벨(기둥/보 식별자)]\n```\n{json.dumps(labels[:40], ensure_ascii=False, indent=2)}\n```\n\n"
        if geom_sample:
            prompt += f"[기하 데이터 샘플]\n```\n{json.dumps(geom_sample, ensure_ascii=False, indent=2)}\n```\n\n"
        if texts_sample:
            prompt += f"[텍스트 샘플]\n```\n{json.dumps(texts_sample, ensure_ascii=False, indent=2)}\n```\n\n"

        prompt += (
            "============================================================\n"
            "■ 1단계. 전역 좌표 정합\n"
            "============================================================\n"
            "- 입력된 정제 데이터에서 엘리베이터 코어 끝점 3개 더하기 1개를 식별하라.\n"
            "- 3개 끝점을 기준으로 전역 가로/세로 좌표계를 고정하라.\n"
            "- 4번째 검증용 끝점이 제자리에 안 떨어질 경우, "
            "해당 구간에 즉시 [좌표_불일치] 로그를 남기고 빨간 표시하라.\n\n"
            "============================================================\n"
            "■ 2단계. 버전3 정사 순서 가동(분류 흐름)\n"
            "============================================================\n"
            "- 다음 절대 역행 금지 순서에 따라 부재를 식별하고 라벨링하라:\n"
            "  3번 피씨 분리(레이어 분류) → 2번 페어링(선 잇기) → 1번 거더 매칭\n"
            "- 위 순서가 꼬이거나 레이어가 섞인 경우 연산을 중단하고 오류 로그를 출력하라.\n\n"
            "============================================================\n"
            "■ 3단계. 개구부 99퍼센트 갭 규칙 적용(선 정리)\n"
            "============================================================\n"
            "- 끊겨 있는 벽체선 중 평행, 대향(마주봄), 직각 세 가지 기하학적 조건이 "
            "100퍼센트 충족되는 구간을 찾아라.\n"
            "- 조건 충족 시: 양 끝을 안쪽으로 90도 꺾어 마주 잇고 "
            "[검은 실선] 속성(콘크리트 없음 태그)을 부여하라.\n"
            "- 조건 불일치 시(한쪽만 끊김 등): 두 끝점의 정확한 중간 좌표를 계산하여 "
            "[작은 빨간 원] 태그를 마킹하라.\n\n"
            "============================================================\n"
            "■ 4단계. 출력 형식\n"
            "============================================================\n"
            "- 모든 좌표 데이터와 추론 로그는 4000자 내외의 덩어리 단위로 쪼개어 "
            "가독성 높은 마크다운 표와 텍스트로 구성하라.\n"
            "- 애매한 판단 지점(빨간 원, 빨간 실선)마다 인간 검수자가 즉시 식별할 수 있도록 "
            "상단에 배정 사유 로그 자리를 명확히 확보하라.\n\n"
            "============================================================\n"
            "[추정값 제로 원칙 절대 사수]\n"
            "============================================================\n"
            "너는 임의의 층고나 수치를 예측하지 않는다. "
            "모르는 좌표나 불명확한 간극은 무조건 [작은 빨간 원]으로 마킹하여 "
            "인간 검수자에게 넘겨라. "
            "자신 있게 마음대로 선을 그리는 환각(가짜)은 도면 위조다. "
            "너의 핵심 임무는 모름을 모름으로 솔직하게 표시하는 것이다.\n\n"
            "[추가 분석 항목]\n"
            "- 골조선(기둥/보/벽체 중심선)을 어떻게 뽑을지 서술하라.\n"
            "- 끊긴 선을 어떻게 이을지: 갭 크기, 연장 방향, 교차점 검출 방법.\n"
            "- 완벽한 골조선 = (중심선 + 두께/폭 + 시작/종료점).\n"
            "- 기준선(수평/수직 격자) 교차점 좌표를 모두 나열하라.\n"
            "- 개구부(출입구, 창호, 피트)의 위치와 크기.\n"
            "- 단차 구간(층내 바닥 높이 차이) 구역.\n"
            "- 부재 카탈로그: [종류] [기호] [단면] [수량] [위치] [층] 표로 정리.\n"
            "- 누락 정보는 미확인 표기. 추정 절대 금지.\n"
            "- 신뢰도: 확실 / 추론 / 보류 3단계 명시.\n"
            "- 모든 출력은 한국어만 사용. 한자 금지.\n"
        )

        print(self_logging(f"  [{base_name}] 2단계: Ollama 8B 두뇌 추론 가동..."))
        t0 = time.time()
        result_md = ask_ollama_brain(prompt, model)
        elapsed = time.time() - t0

        if result_md.startswith("오류:"):
            print(self_logging(f"  ❌ [{base_name}] Ollama 실패 {_fmt(elapsed)} — 스킵"))
            total_fail += 1
            print()
            continue

        print(self_logging(f"  [{base_name}] 추론 완료 {_fmt(elapsed)}"))

        # 옵시디언 적재
        saved = save_to_obsidian(f"{base_name}_cleaned", result_md)
        print(self_logging(f"  ✅ [{base_name}] 프랙탈 적재 완료 → {saved[0].name}"))
        total_ok += 1
        print()

    print(f'{"─" * 60}')
    print(self_logging(f"웜엔진 완료: 성공 {total_ok} / 실패 {total_fail}"))
    print(f'{"─" * 60}')


# ──────────────────────────────────────────────────────────
#  파이프라인 스테이지
# ──────────────────────────────────────────────────────────

def stage_inspect(dxf_path: str) -> dict[str, Any]:
    """inspect_drawing.py --all 호출."""
    print("\n[1/4] DXF 도면 검사 ── inspect_drawing.py --all")
    t0 = time.time()
    result = _run_py(["tools/inspect_drawing.py", dxf_path, "--all"])
    elapsed = time.time() - t0
    ok = result.get("ok", True) and result.get("returncode") is None
    print(f"  [완료] {_fmt(elapsed)}")
    return {"ok": ok, "elapsed": elapsed}


def stage_parse(dxf_path: str) -> dict[str, Any]:
    """Python 파서 실행 (core.pipeline)."""
    print("\n[2/4] 도면 파싱 ── core.pipeline")
    t0 = time.time()
    try:
        from core.pipeline.orchestrator import run_pipeline  # type: ignore
        result = run_pipeline(dxf_path)
        elapsed = time.time() - t0
        print(f"  [완료] {_fmt(elapsed)}")
        return {"ok": True, "elapsed": elapsed}
    except Exception as e:
        print(f"  [오류] {e}")
        return {"ok": False, "error": str(e), "elapsed": time.time() - t0}


def stage_llm(dxf_path: str, model: str) -> dict[str, Any]:
    """Ollama LLM 추론 — 도면 분석 보고서 생성."""
    print(f"\n[3/4] Ollama LLM 추론 ── model={model}")
    t0 = time.time()

    stem = Path(dxf_path).stem
    size_kb = os.path.getsize(dxf_path) / 1024
    print(f"  대상 도면: {stem} ({size_kb:.0f} KB)")

    prompt = (
        f"다음 DXF 도면 정보를 분석해:\n"
        f"- 파일명: {stem}\n"
        f"- 크기: {size_kb:.0f} KB\n"
        f"\n"
        f"1) 이 도면에서 예상되는 구조 부재 종류 (기둥, 보, 슬라브, 벽체 등)\n"
        f"2) 주의해야 할 특이사항 (단차, E/V, 피트 등)\n"
        f"3) 파싱 전략 제안"
    )
    system_prompt = (
        "당신은 건축/토목 구조 도면 해석 전문가입니다. "
        "DXF 도면의 구조 부재를 식별하고 파싱 전략을 제안합니다."
    )

    print("  LLM 추론 중... (최대 120초)")
    response = _ollama_generate(model, prompt, system_prompt)
    elapsed = time.time() - t0

    if response:
        print(f"  [완료] {_fmt(elapsed)}")
        print(f"\n  LLM 분석 결과:\n{response[:600]}...\n")

        # 결과 저장
        out_dir = PIPELINE_ROOT / "output"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"llm_analysis_{stem}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "model": model,
                    "dxf": dxf_path,
                    "prompt": prompt,
                    "response": response,
                    "elapsed": elapsed,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"  저장: {out_path}")
        return {"ok": True, "model": model, "elapsed": elapsed}
    else:
        print(f"  [오류] LLM 응답 없음 {_fmt(elapsed)}")
        return {"ok": False, "elapsed": elapsed}


def stage_boq(dxf_path: str) -> dict[str, Any]:
    """BOQ 산출물 생성."""
    print("\n[4/4] BOQ 산출 ── core.pipeline.boq")
    t0 = time.time()
    try:
        from core.pipeline.boq import compute_boq  # type: ignore
        result = compute_boq(dxf_path)
        elapsed = time.time() - t0
        total = result.get("total", {})
        if total:
            print(f"  콘크리트: {total.get('concrete_m3', 0):.1f} m3")
            print(f"  거푸집: {total.get('form_m2', 0):.1f} m2")
            print(f"  철근: {total.get('rebar_kg', 0):.1f} kg")
        print(f"  [완료] {_fmt(elapsed)}")
        return {"ok": True, "elapsed": elapsed}
    except Exception as e:
        print(f"  [오류] {e}")
        return {"ok": False, "error": str(e), "elapsed": time.time() - t0}


# ──────────────────────────────────────────────────────────
#  메인
# ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ollama + Python 파서 통제 파이프라인 워커",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("dxf", nargs="?", default=None, help="DXF 도면 파일 경로")
    parser.add_argument("--inspect", action="store_true", help="도면 검사")
    parser.add_argument("--parse", action="store_true", help="풀 파싱")
    parser.add_argument("--llm", action="store_true", help="Ollama 추론")
    parser.add_argument("--boq", action="store_true", help="BOQ 산출")
    parser.add_argument("--all", action="store_true", help="전체 파이프라인 실행")
    parser.add_argument("--model", default=DEFAULT_8B_MODEL, help="Ollama 모델명")
    parser.add_argument(
        "--night",
        action="store_true",
        help="야간 백그라운드 워커 (input_drawings/*.dxf 일괄 처리)",
    )
    args = parser.parse_args()

    # 야간 백그라운드 워커 (단독 실행)
    if args.night:
        run_night_pipeline(model=args.model)
        return

    dxf_path = args.dxf
    if not dxf_path:
        parser.error("dxf 파일 경로 필요 (--night 또는 파일 지정)")
    if not os.path.isfile(dxf_path):
        print(f"[오류] 파일 없음: {dxf_path}")
        sys.exit(1)

    _b_top = "\u2550"
    print(f"\u2554{_b_top * 58}\u2557")
    print(f"\u2551  FreeCAD_4TH Pipeline Worker")
    print(f"\u2551  \ub3c4\uba74: {Path(dxf_path).name}")
    print(f"\u255a{_b_top * 58}\u255d")

    do_all = args.all
    stages = []
    results: dict[str, dict[str, Any]] = {}

    if do_all or args.inspect:
        r = stage_inspect(dxf_path)
        results["inspect"] = r
        stages.append("inspect")

    if do_all or args.parse:
        r = stage_parse(dxf_path)
        results["parse"] = r
        stages.append("parse")

    if do_all or args.llm:
        r = stage_llm(dxf_path, args.model)
        results["llm"] = r
        stages.append("llm")

    if do_all or args.boq:
        r = stage_boq(dxf_path)
        results["boq"] = r
        stages.append("boq")

    # 요약
    _bar = "\u2500"
    ok_count = sum(1 for s in stages if results.get(s, {}).get("ok"))
    print(f"\n{_bar * 60}")
    _msg = "\ud30c\uc774\ud504\ub77c\uc778 \uc644\ub8cc:"
    _ok = "\uc2a4\ud14c\uc774\uc9c0 \uc131\uacf5"
    print(f"{_msg} {ok_count}/{len(stages)} {_ok}")
    for s in stages:
        r = results.get(s, {})
        status = "\u2705" if r.get("ok") else "\u274c"
        elapsed = r.get("elapsed", 0)
        print(f"  {status} {s}: {_fmt(elapsed)}")
    print(f"{_bar * 60}")


if __name__ == "__main__":
    main()
