#!/usr/bin/env python3
"""Collect bounded, redacted diagnostics without changing services."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import signal
import stat
import math
import sys
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from net_common import bounded_request, redact_text, safe_url

UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I)
ISO_TIME = re.compile(r"\b\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:?\d\d)?\b")
HEX = re.compile(r"\b0x[0-9a-f]+\b|\b[0-9a-f]{16,}\b", re.I)


class DiagnosticError(ValueError):
    pass


def redact(value):
    return redact_text(value)


def compact_signature(line: str) -> str:
    result = redact(line).strip()
    result = ISO_TIME.sub("<time>", result)
    result = UUID.sub("<uuid>", result)
    result = HEX.sub("<id>", result)
    result = re.sub(r"\b\d+(?:\.\d+)?\b", "<n>", result)
    result = re.sub(r"\s+", " ", result)
    return result[:300] or "<empty>"


def run_argv(argv: list[str], deadline: float, max_bytes: int = 12000) -> dict[str, Any]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return {"status": "timeout", "exit_code": None, "truncated": True}
    try:
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
            timed_out = False
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                timed_out = True
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait()
            streams = {}
            truncated = timed_out
            for name, f in (("stdout", out), ("stderr", err)):
                f.seek(0, 2)
                size = f.tell()
                f.seek(0)
                raw = f.read(max_bytes)
                streams[name] = "\n".join(redact(line) for line in raw.decode("utf-8","replace").splitlines())
                truncated = truncated or size > max_bytes
            return {"status": "timeout" if timed_out else "ok" if proc.returncode == 0 else "failed",
                    "exit_code": None if timed_out else proc.returncode, "truncated": truncated, **streams}
    except FileNotFoundError:
        return {"status": "unavailable", "exit_code": None, "stderr": "executable unavailable"}
    except PermissionError:
        return {"status": "permission_denied", "exit_code": None, "stderr": "permission denied"}


def signatures(text: str, max_groups: int = 50) -> tuple[list[dict[str, Any]], bool]:
    groups: OrderedDict[str, dict[str, Any]] = OrderedDict()
    truncated = False
    for number, line in enumerate(text.splitlines(), start=1):
        signature = compact_signature(line)
        if signature not in groups:
            if len(groups) >= max_groups:
                truncated = True
                continue
            groups[signature] = {"signature": signature, "count": 0, "first_line": number, "last_line": number, "sample": redact(line.strip())[:300]}
        group = groups[signature]
        group["count"] += 1
        group["last_line"] = number
    return list(groups.values()), truncated


def add_fact(report: dict[str, Any], kind: str, source: str, value: Any) -> None:
    report["facts"].append({"kind": kind, "source": redact(source), "value": redact(str(value)) if isinstance(value, str) else value})


def inspect_executable(report: dict[str, Any], name: str) -> str | None:
    path = shutil.which(name)
    add_fact(report, "executable", name, path or "unavailable")
    return path


def collect_file(path: Path, deadline: float, max_bytes: int) -> tuple[dict[str, Any], bool]:
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            return {"status": "not_regular_file", "path": str(path)}, False
        with path.open("rb") as stream:
            raw = stream.read(max_bytes + 1)
    except FileNotFoundError:
        return {"status": "not_found", "path": str(path)}, False
    except PermissionError:
        return {"status": "permission_denied", "path": str(path)}, False
    if time.monotonic() >= deadline:
        return {"status": "timeout", "path": str(path), "truncated": True}, True
    truncated = len(raw) > max_bytes
    text = raw[:max_bytes].decode("utf-8", "replace")
    grouped, grouping_truncated = signatures(text)
    return {"status": "ok", "path": str(path), "lines": len(text.splitlines()), "bytes": len(raw[:max_bytes]), "log_signatures": grouped, "truncated": truncated or grouping_truncated}, truncated or grouping_truncated


def collect_url(url: str, deadline: float, max_bytes: int) -> tuple[dict[str, Any], bool]:
    from urllib.parse import urlsplit
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("invalid URL")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        display = safe_url(url)
    except ValueError:
        return {"status": "invalid_url", "error": "HTTP(S) URL without embedded credentials required"}, False
    response = bounded_request(url, "GET", {"Accept": "application/json, text/plain, */*"}, None,
                               deadline-time.monotonic(), max_bytes)
    result = {"url": display, "host": parsed.hostname, "port": port}
    if "error" in response:
        result.update(status="timeout" if response["error"]=="total_timeout" else "transport_failed",
                      port_open=None, error=response["error"])
        return result, response["error"]=="total_timeout"
    raw = response["body"]
    result.update(status="ok" if response["status_code"]<400 else "http_error",
                  http_status=response["status_code"], port_open=True, body_bytes=len(raw),
                  body_preview=redact(raw.decode("utf-8","replace"))[:1000] if not response["truncated"] else "[truncated body omitted]",
                  truncated=response["truncated"])
    return result, response["truncated"]


def diagnose(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    started = time.monotonic()
    deadline = started + args.timeout
    report: dict[str, Any] = {"status": "ok", "facts": [], "hypotheses": [], "targets": [], "truncated": False}
    docker_path = inspect_executable(report, args.docker_bin) if (args.container or args.docker_info) else None
    systemctl_path = inspect_executable(report, args.systemctl_bin) if args.service else None
    if docker_path and (args.container or args.docker_info) and time.monotonic() < deadline:
        daemon = run_argv([docker_path, "info", "--format", "{{json .ServerVersion}}"], deadline, args.max_log_bytes)
        add_fact(report, "docker_daemon", "docker info", daemon.get("status"))
        if daemon.get("status") in {"permission_denied", "timeout", "failed", "unavailable"}:
            report["status"] = "incomplete"
    if args.container:
        for name in args.container:
            target = {"kind": "container", "name": redact(name), "observations": [], "exit_codes": {}}
            if not docker_path:
                target["observations"].append({"status": "runtime_unavailable", "runtime": "docker"})
                report["status"] = "incomplete"
            else:
                for operation in (("inspect", [docker_path, "inspect", "--format", "{{json .State}}", name]), ("port", [docker_path, "port", name]), ("logs", [docker_path, "logs", "--tail", str(args.max_log_lines), name])):
                    if time.monotonic() >= deadline:
                        target["observations"].append({"status": "timeout", "operation": operation[0]})
                        report["truncated"] = True
                        report["status"] = "incomplete"
                        break
                    result = run_argv(operation[1], deadline, args.max_log_bytes)
                    target["exit_codes"][operation[0]] = result.get("exit_code")
                    if operation[0] == "logs" and (result.get("stdout") or result.get("stderr")):
                        combined = "\n".join(v for v in (result.get("stdout"), result.get("stderr")) if v)
                        grouped, grouping_truncated = signatures(combined)
                        result["lines"] = len(combined.splitlines())
                        result["log_signatures"] = grouped
                        result["truncated"] = bool(result.get("truncated") or grouping_truncated)
                        result.pop("stdout", None)
                        result.pop("stderr", None)
                    target["observations"].append({"operation": operation[0], **result})
                    report["truncated"] = bool(report["truncated"] or result.get("truncated"))
                    if result.get("status") in {"unavailable", "permission_denied", "timeout", "failed"}:
                        report["status"] = "incomplete"
            report["targets"].append(target)
    for name in args.service:
        target = {"kind": "service", "name": redact(name), "observations": [], "exit_codes": {}}
        if not systemctl_path:
            target["observations"].append({"status": "runtime_unavailable", "runtime": "systemd"})
            report["status"] = "incomplete"
        else:
            for operation, argv in (("is-active", [systemctl_path, "is-active", name]), ("show", [systemctl_path, "show", "--no-pager", "--property=SubState,ActiveState,ExecMainStatus", name])):
                result = run_argv(argv, deadline, args.max_log_bytes)
                target["exit_codes"][operation] = result.get("exit_code")
                target["observations"].append({"operation": operation, **result})
                if result.get("status") in {"unavailable", "permission_denied", "timeout", "failed"}:
                    report["status"] = "incomplete"
        report["targets"].append(target)
    for url in args.url:
        observation, truncated = collect_url(url, deadline, args.max_log_bytes)
        report["targets"].append({"kind": "url", "name": safe_url(url) if observation.get("status") != "invalid_url" else "[invalid URL]", "observations": [observation], "exit_codes": {"http": observation.get("http_status")}})
        report["truncated"] = bool(report["truncated"] or truncated)
        if observation.get("status") in {"transport_failed", "invalid_url", "timeout"}:
            report["status"] = "incomplete"
    for raw_path in args.log_file:
        path = Path(raw_path).expanduser()
        observation, truncated = collect_file(path, deadline, args.max_log_bytes)
        report["targets"].append({"kind": "log_file", "name": redact(str(path)), "observations": [observation], "exit_codes": {}})
        report["truncated"] = bool(report["truncated"] or truncated)
        if observation.get("status") != "ok":
            report["status"] = "incomplete"
    for target in report["targets"]:
        for observation in target.get("observations", []):
            # A palavra "timeout" em um log é um fato do aplicativo; só uma
            # observação de coleta esgotada justifica esta hipótese operacional.
            if observation.get("status") == "timeout" or observation.get("transport") == "total_timeout":
                report["hypotheses"].append({"basis": f"{target['kind']}:{target['name']}", "text": "A coleta excedeu o tempo disponível; a causa do serviço ainda não foi estabelecida."})
                break
    report["duration_ms"] = round((time.monotonic() - started) * 1000)
    report["truncated"] = bool(report["truncated"] or time.monotonic() >= deadline)
    if report["truncated"] and report["status"] == "ok":
        report["status"] = "incomplete"
    return report, 0 if report["targets"] and report["status"] == "ok" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", action="append", default=[])
    parser.add_argument("--service", action="append", default=[])
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--log-file", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-log-bytes", type=int, default=12000)
    parser.add_argument("--max-log-lines", type=int, default=200)
    parser.add_argument("--docker-bin", default="docker")
    parser.add_argument("--systemctl-bin", default="systemctl")
    parser.add_argument("--docker-info", action="store_true", help="record Docker executable availability even without a container")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not (args.container or args.service or args.url or args.log_file):
        parser.error("informe ao menos um --container, --service, --url ou --log-file")
    if not math.isfinite(args.timeout) or not 0.1 <= args.timeout <= 600 or not 1 <= args.max_log_bytes <= 262144 or not 1 <= args.max_log_lines <= 2000:
        parser.error("timeout e limites devem ser positivos")
    try:
        if len(args.container)+len(args.service)+len(args.url)+len(args.log_file)>32:
            raise DiagnosticError("maximum 32 targets")
        if any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]*", n) for n in args.container+args.service):
            raise DiagnosticError("invalid container/service name")
        if args.output and (args.output.exists() or args.output.is_symlink()):
            raise DiagnosticError("output exists; choose a new report")
        report, code = diagnose(args)
    except (OSError, ValueError) as exc:
        report, code = {"status": "error", "error": redact(str(exc))}, 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as output: output.write(rendered)
        except OSError:
            print(json.dumps({"status":"report_not_written","report":report}))
            return 2
    sys.stdout.write(rendered)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
