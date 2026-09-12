#!/usr/bin/env python3
"""Small tool-calling agent for an OpenAI-compatible LM Studio endpoint."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "qwen/qwen3.5-9b"
MAX_TOOL_OUTPUT = 24_000


def confined(workspace: Path, value: str) -> Path:
    candidate = (workspace / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if candidate != workspace and workspace not in candidate.parents:
        raise ValueError(f"path escapes workspace: {value}")
    return candidate


def compact(text: str, limit: int = MAX_TOOL_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n... output truncated ...\n" + text[-half:]


def execute_tool(workspace: Path, name: str, args: dict[str, Any]) -> str:
    try:
        if name == "list_files":
            root = confined(workspace, str(args.get("path", ".")))
            depth = max(1, min(int(args.get("max_depth", 3)), 6))
            if not root.exists():
                return "ERROR: path does not exist"
            base_depth = len(root.parts)
            items: list[str] = []
            for current, dirs, files in os.walk(root):
                current_path = Path(current)
                if len(current_path.parts) - base_depth >= depth:
                    dirs[:] = []
                dirs[:] = sorted(d for d in dirs if d not in {".git", "node_modules", "target", "dist", "build", "__pycache__"})
                for filename in sorted(files):
                    items.append(str((current_path / filename).relative_to(workspace)))
                    if len(items) >= 2000:
                        items.append("... file listing truncated ...")
                        return "\n".join(items)
            return "\n".join(items) or "(no files)"

        if name == "read_file":
            path = confined(workspace, str(args["path"]))
            start = max(1, int(args.get("start_line", 1)))
            end = max(start, min(int(args.get("end_line", start + 499)), start + 1999))
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return compact("\n".join(f"{i}: {lines[i - 1]}" for i in range(start, min(end, len(lines)) + 1)))

        if name == "write_file":
            path = confined(workspace, str(args["path"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            content = str(args["content"])
            path.write_text(content, encoding="utf-8")
            return f"WROTE {path.relative_to(workspace)} ({len(content)} chars)"

        if name == "run_command":
            argv = args.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
                return "ERROR: argv must be a non-empty string array"
            timeout = max(1, min(int(args.get("timeout_seconds", 120)), 600))
            completed = subprocess.run(
                argv,
                cwd=workspace,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                env={**os.environ, "GIT_PAGER": "cat", "PAGER": "cat"},
            )
            return compact(
                f"exit_code={completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        return f"ERROR: unknown tool {name}"
    except subprocess.TimeoutExpired as exc:
        return compact(f"ERROR: command timed out\nSTDOUT:\n{exc.stdout or ''}\nSTDERR:\n{exc.stderr or ''}")
    except Exception as exc:  # Report tool errors to the model so it can recover.
        return f"ERROR: {type(exc).__name__}: {exc}"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List source files under a workspace-relative path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "max_depth": {"type": "integer"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a bounded line range from a UTF-8 text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or replace a UTF-8 text file inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a non-interactive command in the workspace without a shell.",
            "parameters": {
                "type": "object",
                "properties": {
                    "argv": {"type": "array", "items": {"type": "string"}},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["argv"],
            },
        },
    },
]


def request(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LM Studio HTTP {exc.code}: {compact(body, 4000)}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Qwen as a local workspace subagent")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--url", default=os.getenv("LMSTUDIO_BASE_URL", DEFAULT_URL))
    parser.add_argument("--model", default=os.getenv("LMSTUDIO_MODEL", DEFAULT_MODEL))
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=600)
    options = parser.parse_args()

    workspace = Path(options.workspace).resolve()
    if not workspace.is_dir():
        parser.error(f"workspace is not a directory: {workspace}")

    system = f"""/no_think
You are a local coding subagent operating only in {workspace}.
Complete the bounded task using the provided tools. Inspect before editing. Preserve unrelated work.
Never access or modify paths outside the workspace. Do not publish, install system packages, or use network tools.
Run focused checks when available. At the end, report: outcome, changed files, checks run, and remaining issues.
"""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": options.task},
    ]

    for step in range(1, max(1, options.max_steps) + 1):
        response = request(
            options.url,
            {
                "model": options.model,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0.1,
                "max_tokens": options.max_tokens,
            },
            options.timeout,
        )
        choice = response["choices"][0]
        message = choice["message"]
        tool_calls = message.get("tool_calls") or []
        messages.append({k: v for k, v in message.items() if k in {"role", "content", "tool_calls"}})
        print(f"[qwen step {step}] finish={choice.get('finish_reason')} tools={len(tool_calls)}", file=sys.stderr)

        if not tool_calls:
            content = message.get("content") or ""
            if content:
                print(content)
                return 0
            print("Qwen returned neither content nor tool calls.", file=sys.stderr)
            return 2

        for call in tool_calls:
            function = call["function"]
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError as exc:
                result = f"ERROR: invalid tool arguments: {exc}"
            else:
                result = execute_tool(workspace, function["name"], arguments)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    print(f"Qwen exceeded the maximum of {options.max_steps} tool steps.", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
