---
name: context-guard
description: Persistent DSH context-budget, checkpoint, and loop-safety policy for local-model sessions. It is automatically reinforced by the harness; do not wait for a user invocation.
disable-model-invocation: false
user-invocable: false
---

# Context Guard

This skill is automatically active with the DSH context guard. Follow its budget notices and deterministic tool blocks.

- Normal operation below 20k estimated tokens.
- Economy mode from 20k to 25k: use targeted reads, concise results, and diffs.
- Checkpoint preparation from 25k to 30k: preserve the live objective, constraints, work completed, decisions, changed files, relevant commands/results, unresolved errors, failed approaches, current state, and one next action.
- Automatic compacting begins at about 30k tokens for `lmstudio/qwen/qwen3.5-9b`.

Treat identical commands, identical file reads, and materially equivalent tool calls without changed evidence as non-progress. After three no-progress actions, re-evaluate instead of continuing; after five equivalent attempts, abandon that approach. If no safe alternative exists, report the blocker.
