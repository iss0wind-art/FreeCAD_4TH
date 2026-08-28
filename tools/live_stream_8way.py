"""8분할 live stream — 4 CLI × 2 instances.

claude / gemini / deepseek / qwen 각 2 인스턴스, 총 8 병렬.

안전 조치 (pipe buffer deadlock 영구 차단):
  1. asyncio.create_subprocess_exec (논블로킹)
  2. stderr=DEVNULL                  ← 핵심
  3. per-CLI timeout (asyncio.wait_for)
  4. gather(return_exceptions=True)  ← 한 놈 실패해도 7놈 계속
  5. stdout → 파일 직접 write (메모리 + 디스크 양쪽)

사용:
  python tools\\live_stream_8way.py "프롬프트 문장"
  python tools\\live_stream_8way.py            # 기본 프롬프트
"""

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ─── 8사관 정의 (label, executable, prompt_mode) ─────────────────────
# prompt_mode:
#   "flag_p"     → cli -p "prompt"
#   "positional" → cli "prompt"     (qwen-code 신규 방식, gemini fork 호환)
CLI_DEFS = [
    ("claude-1",   "claude",   "flag_p"),
    ("claude-2",   "claude",   "flag_p"),
    ("gemini-1",   "gemini",   "positional"),
    ("gemini-2",   "gemini",   "positional"),
    ("deepseek-1", "deepseek", "flag_p"),
    ("deepseek-2", "deepseek", "flag_p"),
    ("qwen-1",     "qwen",     "positional"),
    ("qwen-2",     "qwen",     "positional"),
]

OUT_DIR = Path(os.environ.get("STREAM_OUT", "./stream_out"))
TIMEOUT = int(os.environ.get("STREAM_TIMEOUT", "180"))  # per CLI, seconds


def resolve_cmd(name: str, prompt_mode: str, prompt: str) -> list[str] | None:
    """비대화 모드 argv 반환. Windows .cmd shim은 cmd.exe /c로 wrap."""
    import shutil
    suffixes = (".cmd", ".exe", "") if sys.platform == "win32" else ("",)
    full = None
    for suffix in suffixes:
        full = shutil.which(name + suffix)
        if full:
            break
    if not full:
        return None
    if prompt_mode == "flag_p":
        base = [full, "-p", prompt]
    elif prompt_mode == "positional":
        base = [full, prompt]
    else:
        base = [full, prompt]
    if sys.platform == "win32" and full.lower().endswith(".cmd"):
        return ["cmd.exe", "/c"] + base
    return base


async def run_one(label: str, exe: str, prompt_mode: str, prompt: str, out_dir: Path) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = uuid.uuid4().hex[:8]
    out_path = out_dir / f"{ts}_STREAM_{label}_{short}.txt"
    start = time.monotonic()

    cmd = resolve_cmd(exe, prompt_mode, prompt)
    if cmd is None:
        return {"label": label, "status": "cli_missing", "exe": exe}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,    # stdin 차단 (인자로 prompt 전달)
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,   # ← 핵심: stderr deadlock 차단
        )
    except (FileNotFoundError, PermissionError, NotImplementedError) as e:
        return {"label": label, "status": "spawn_failed", "error": str(e)}

    chunks: list[bytes] = []
    out_f = out_path.open("wb")
    try:
        async def stream_loop():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                chunks.append(line)
                out_f.write(line)
                out_f.flush()

        await asyncio.wait_for(stream_loop(), timeout=TIMEOUT)
        rc = await proc.wait()
        wall = time.monotonic() - start
        return {
            "label": label,
            "status": "ok" if rc == 0 else f"exit_{rc}",
            "wall_s": round(wall, 2),
            "bytes": sum(len(c) for c in chunks),
            "file": str(out_path),
        }
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        wall = time.monotonic() - start
        return {
            "label": label,
            "status": "timeout",
            "wall_s": round(wall, 2),
            "bytes": sum(len(c) for c in chunks),
            "file": str(out_path),
        }
    except Exception as e:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return {"label": label, "status": "error", "error": repr(e), "file": str(out_path)}
    finally:
        out_f.close()


async def main(prompt: str) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[8way] CLIs : {[c[0] for c in CLI_DEFS]}")
    print(f"[8way] timeout: {TIMEOUT}s per CLI")
    print(f"[8way] out_dir: {OUT_DIR.resolve()}")
    print(f"[8way] prompt : {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print("-" * 60)

    start = time.monotonic()
    tasks = [run_one(label, exe, mode, prompt, OUT_DIR) for label, exe, mode in CLI_DEFS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total = time.monotonic() - start

    print(f"\n[8way] total wall: {total:.1f}s")
    print("-" * 60)

    ok = 0
    for r in results:
        if isinstance(r, BaseException):
            print(f"  ✗  CRASH  {r!r}")
            continue
        sym = {
            "ok": "✓",
            "timeout": "⏱",
            "cli_missing": "?",
            "spawn_failed": "✗",
            "stdin_failed": "✗",
            "error": "✗",
        }.get(r["status"], "•")
        if r["status"] == "ok":
            ok += 1
        wall = r.get("wall_s", "-")
        bytes_ = r.get("bytes", "-")
        extra = ""
        if r["status"] in ("cli_missing", "spawn_failed", "stdin_failed", "error"):
            extra = f"  → {r.get('error') or r.get('candidates')}"
        print(f"  {sym}  {r['label']:11s}  {r['status']:14s}  {wall}s  {bytes_}B{extra}")

    print(f"\n[8way] success: {ok}/{len(CLI_DEFS)}")
    return 0 if ok == len(CLI_DEFS) else 1


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "한 문장으로 자기 모델명을 답해라. 다른 말은 하지 마라."
    rc = asyncio.run(main(prompt))
    sys.exit(rc)
