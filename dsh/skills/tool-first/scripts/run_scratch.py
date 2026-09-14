#!/usr/bin/env python3
"""Run a bounded local scratch script inside a Bubblewrap sandbox."""

from __future__ import annotations

import argparse
import json
import os
import resource
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

MAX_RESULT_BYTES = 5500
DEFAULT_OUTPUT_LIMIT = 1024 * 1024

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("lua", "bash", "python"), required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--output-limit-bytes", type=int, default=DEFAULT_OUTPUT_LIMIT)
    parser.add_argument("--memory-limit-mib", type=int, default=256)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.args[:1] == ["--"]:
        args.args = args.args[1:]
    if not 100 <= args.timeout_ms <= 60000:
        parser.error("--timeout-ms must be between 100 and 60000")
    if not 1024 <= args.output_limit_bytes <= DEFAULT_OUTPUT_LIMIT:
        parser.error("--output-limit-bytes must be between 1024 and 1048576")
    if not 32 <= args.memory_limit_mib <= 512:
        parser.error("--memory-limit-mib must be between 32 and 512")
    return args

def validate_paths(script_arg: str, root_arg: str) -> tuple[Path, Path]:
    script = Path(script_arg).expanduser().resolve()
    root = Path(root_arg).expanduser().resolve()
    if not script.is_file():
        raise ValueError("script is not a regular file")
    if not root.is_dir():
        raise ValueError("root is not a directory")
    return script, root

def child_limits(memory_mib: int, timeout_ms: int) -> None:
    os.setsid()
    memory = memory_mib * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    cpu = max(1, (timeout_ms + 999) // 1000 + 1)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))

def sandbox_command(language: str, script: Path, root: Path, args: list[str]) -> list[str]:
    interpreter = {"lua": "/usr/bin/lua5.4", "bash": "/usr/bin/bash", "python": "/usr/bin/python3"}[language]
    return [
        "bwrap", "--die-with-parent", "--new-session", "--unshare-net", "--clearenv",
        "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/etc", "/etc", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--dir", "/run", "--dir", "/runner", "--dir", "/scratch",
        "--ro-bind", str(script), "/runner/script", "--ro-bind", str(root), "/input",
        "--setenv", "HOME", "/tmp", "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "LANG", "C.UTF-8", "--setenv", "LC_ALL", "C.UTF-8",
        "--chdir", "/input", "--", interpreter, "/runner/script", *args,
    ]

def compact(value: bytes, limit: int = 4096) -> str:
    text = value.decode("utf-8", errors="replace")
    if len(text.encode("utf-8")) <= limit:
        return text
    return text[: max(1, limit // 2)] + "\n[output truncated]\n" + text[-max(1, limit // 2):]

def output(status: str, started: float, stdout: bytes, stderr: bytes, totals: dict[str, int], truncated: bool, process: subprocess.Popen | None = None, error: str | None = None) -> dict:
    value = {"status": status, "exit_code": process.returncode if process and status == "completed" else None,
             "signal": -process.returncode if process and process.returncode and process.returncode < 0 else None,
             "elapsed_ms": round((time.monotonic() - started) * 1000), "stdout": compact(stdout), "stderr": compact(stderr),
             "stdout_bytes": totals["stdout"], "stderr_bytes": totals["stderr"], "output_truncated": truncated}
    if error:
        value["error"] = error
    return value

def run(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    try:
        script, root = validate_paths(args.script, args.root)
        process = subprocess.Popen(sandbox_command(args.language, script, root, args.args), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                                   preexec_fn=lambda: child_limits(args.memory_limit_mib, args.timeout_ms))
    except (OSError, ValueError) as exc:
        return output("failed", started, b"", b"", {"stdout": 0, "stderr": 0}, False, error=str(exc))

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    totals = {"stdout": 0, "stderr": 0}
    status = "completed"
    truncated = False
    deadline = started + args.timeout_ms / 1000
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                status = "timeout"
                os.killpg(process.pid, signal.SIGKILL)
                break
            for key, _ in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                name = key.data
                totals[name] += len(chunk)
                room = args.output_limit_bytes - len(buffers[name])
                if room > 0:
                    buffers[name].extend(chunk[:room])
                if totals["stdout"] + totals["stderr"] > args.output_limit_bytes:
                    status = "output_limit"
                    truncated = True
                    os.killpg(process.pid, signal.SIGKILL)
                    break
            if status != "completed":
                break
        process.wait(timeout=2)
    except (subprocess.TimeoutExpired, ProcessLookupError):
        status = "timeout"
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    finally:
        selector.close()
        for stream in (process.stdout, process.stderr):
            if stream and not stream.closed:
                stream.close()
    return output(status, started, bytes(buffers["stdout"]), bytes(buffers["stderr"]), totals, truncated, process)

def main() -> int:
    value = run(parse_args())
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_RESULT_BYTES:
        value["stdout"] = value["stdout"][:512]
        value["stderr"] = value["stderr"][:512]
        value["response_truncated"] = True
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    print(text)
    return 0

if __name__ == "__main__":
    sys.exit(main())
