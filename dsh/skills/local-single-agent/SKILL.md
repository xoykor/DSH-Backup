---
name: local-single-agent
description: Run development tasks with one local main agent only, without subagents, workflow, Ralph, or delegated LLM calls.
disable-model-invocation: true
user-invocable: true
---

# Local Single Agent

Work entirely inside the current main agent session. You are the only reasoning and coding agent for this task.

## Single-agent rule

Never invoke or use subagent, subagent-control, subagent-report, workflow, Ralph, delegated coding agents, delegated reviewers, nested DSH sessions, or external AI agents. Do not spawn another LLM or AI coding process for any part of the task.

## Local-model priority

Use the provider and model already selected for the current DSH session. Do not change either unless the user explicitly requests it. Do not route work to cloud models because a task is difficult.

## Execution

For non-trivial work, inspect the repository, understand the requested change, make a short internal execution plan, implement incrementally, and verify meaningful stages. Prefer direct execution; do not replace absent delegation with large speculative plans.

Assume limited context capacity: search before reading large files; read relevant regions only; avoid reopening unchanged files and loading whole repositories; keep terminal output bounded; summarize long logs; retain important decisions concisely.

Before editing, inspect existing patterns and neighboring code. Preserve the existing architecture where sensible. Make the smallest correct change; avoid unrelated refactors, unnecessary abstractions, and dependencies. Keep code understandable and type-safe, and handle errors explicitly.

## Verification and failures

Do not consider work complete from inspection alone. Identify and run the project's actual verification commands as applicable: formatter/check, compiler/build/check, linter/static analysis, unit tests, and relevant integration tests. For Rust, prefer project commands; otherwise suitable fallbacks include `cargo fmt --check`, `cargo check --all-targets`, `cargo clippy --all-targets --all-features -- -D warnings`, and `cargo test --all-features`.

Report checks as passed only when actually run successfully. If a check fails: inspect the failure, identify the root cause, make the minimal correction, then rerun the relevant verification. Do not repeatedly rewrite large sections, weaken tests or quality gates, delete or comment out tests, weaken assertions, add `|| true`, suppress meaningful warnings, disable lint or type checks, hide errors, or change expected behavior merely to match broken output.

## Git and completion

Do not perform destructive Git operations unless explicitly requested. Do not force-push, discard unrelated user changes, reset arbitrary work, or rewrite history unnecessarily. Inspect `git diff` before declaring completion when appropriate.

End with a concise report: what changed, files affected, checks actually executed with PASS/FAIL status, and unresolved issues if any.
