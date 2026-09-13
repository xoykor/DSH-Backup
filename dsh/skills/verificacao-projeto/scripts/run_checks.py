#!/usr/bin/env python3
"""Run declared project checks and emit machine-readable evidence."""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MAX_OUTPUT = 4000


def discover(root: Path) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    package = root / "package.json"
    if package.is_file():
        try:
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
        except (OSError, json.JSONDecodeError):
            scripts = {}
        for name in ("test", "lint", "typecheck", "build", "check"):
            if name in scripts and isinstance(scripts[name], str):
                checks.append({"name": f"npm:{name}", "command": f"npm run {name}"})
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if "[tool.pytest" in text or re.search(r"pytest", text, re.I):
            checks.append({"name": "python:pytest", "command": "python3 -m pytest"})
    cargo = root / "Cargo.toml"
    if cargo.is_file():
        checks.append({"name": "cargo:test", "command": "cargo test --all-targets"})
    makefile = next((root / name for name in ("Makefile", "makefile") if (root / name).is_file()), None)
    if makefile:
        try:
            body = makefile.read_text(encoding="utf-8")
        except OSError:
            body = ""
        targets = {match.group(1) for match in re.finditer(r"^([A-Za-z][A-Za-z0-9_.-]*):", body, re.M)}
        for name in ("test", "check", "lint", "build"):
            if name in targets:
                checks.append({"name": f"make:{name}", "command": f"make {name}"})
    return checks


def classify_failure(command: str, returncode: int, output: str, timed_out: bool) -> str:
    if timed_out:
        return "failed_infrastructure"
    try:
        parts = shlex.split(command)
    except ValueError:
        return "failed_infrastructure"
    first = parts[0] if parts else ""
    if first and shutil.which(first) is None:
        return "failed_infrastructure"
    if re.search(r"No module named|command not found|not recognized|cannot find the path", output, re.I):
        return "failed_infrastructure"
    return "failed_project" if returncode else "passed"


def run_check(check: dict[str, str], root: Path, timeout: int) -> dict[str, object]:
    command = check["command"]
    started = time.monotonic()
    stdout_path = stderr_path = None
    try:
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            return {**check, "status": "failed_infrastructure", "reason": f"invalid_shell_syntax:{exc}", "duration_ms": 0}
        first = parts[0] if parts else ""
        if first and shutil.which(first) is None:
            return {**check, "status": "skipped", "reason": f"executor_unavailable:{first}", "duration_ms": 0}
        with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as stdout, tempfile.NamedTemporaryFile(mode="w+b", delete=False) as stderr:
            stdout_path, stderr_path = stdout.name, stderr.name
            proc = subprocess.Popen(command, shell=True, cwd=root, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                output = tail(stdout_path) + "\n" + tail(stderr_path)
                return {**check, "status": "failed_infrastructure", "reason": f"timeout:{timeout}s", "duration_ms": round((time.monotonic() - started) * 1000), "output": output[-MAX_OUTPUT:]}
        stderr_text = tail(stderr_path)
        output = tail(stdout_path) + (("\n" + stderr_text) if stderr_text else "")
        return {**check, "status": classify_failure(command, proc.returncode, output, False), "exit_code": proc.returncode, "duration_ms": round((time.monotonic() - started) * 1000), "output": output[-MAX_OUTPUT:]}
    except OSError as exc:
        return {**check, "status": "failed_infrastructure", "reason": str(exc), "duration_ms": round((time.monotonic() - started) * 1000)}
    finally:
        for path in (stdout_path, stderr_path):
            if path:
                try:
                    Path(path).unlink()
                except OSError:
                    pass


def tail(path: str, limit: int = MAX_OUTPUT) -> str:
    with open(path, "rb") as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - limit))
        return stream.read().decode("utf-8", errors="replace").strip()


def git_state(root: Path) -> dict[str, object] | None:
    try:
        commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        if commit.returncode:
            return None
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, timeout=5)
        return {"commit": commit.stdout.strip(), "dirty": bool(dirty.stdout.strip())}
    except (OSError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--command", action="append", default=[], metavar="NAME=COMMAND")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--run-discovered", action="store_true", help="execute every discovered check")
    args = ap.parse_args()
    if not args.root.is_dir():
        print(json.dumps({"status": "error", "error": "root_not_found"}), file=sys.stderr)
        return 2
    checks = []
    if args.command:
        for item in args.command:
            if "=" not in item or not item.split("=", 1)[1].strip():
                print(json.dumps({"status": "error", "error": f"invalid_command:{item}"}), file=sys.stderr)
                return 2
            name, command = item.split("=", 1)
            checks.append({"name": name, "command": command})
    else:
        checks = discover(args.root)
    if not args.command and not args.run_discovered:
        report = {"status": "discovered" if checks else "no_checks_discovered", "root": str(args.root.resolve()), "revision": git_state(args.root), "checks": checks, "counts": {"discovered": len(checks)}}
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0 if checks else 1
    results = [run_check(check, args.root, args.timeout) for check in checks]
    statuses = [str(item["status"]) for item in results]
    overall = "no_checks_discovered" if not results else ("failed" if any(status.startswith("failed") for status in statuses) else ("incomplete" if "skipped" in statuses else "passed"))
    report = {"status": overall, "root": str(args.root.resolve()), "revision": git_state(args.root), "checks": results, "counts": {status: statuses.count(status) for status in sorted(set(statuses))}}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if overall in {"failed", "incomplete", "no_checks_discovered"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
