---
name: qwen
description: Delegate bounded coding, file-analysis, and implementation work to the local Qwen 3.5 9B model in LM Studio while Codex plans, reviews, and monitors the result. Use when the user asks to use Qwen locally, reduce hosted-model token use, or invoke a Qwen subagent.
---

# Qwen Local Subagent

Use the bundled `scripts/qwen_agent.py` as the executor. Codex remains responsible for architecture, task decomposition, review, and the final answer.

## Preconditions

Confirm that `http://127.0.0.1:1234/v1/models` is reachable and includes `qwen/qwen3.5-9b`. The user must start the LM Studio local server when it is unavailable.

## Delegation

Give Qwen a bounded task with concrete acceptance criteria and the absolute workspace path:

```bash
python3 __CODEX_HOME__/skills/qwen/scripts/qwen_agent.py \
  --workspace /absolute/project/path \
  --task "<implementation task and acceptance criteria>"
```

Qwen can inspect and edit files inside the selected workspace and run non-interactive commands there. Do not delegate secret handling, external publishing, destructive operations, or decisions that materially expand the user's request.

Prefer one substantial delegation over many small calls. After it finishes, inspect the reported changed files, run or inspect the relevant tests, and review the actual diff. Send a follow-up task only for a specific defect or unmet criterion. Do not forward full logs to hosted models when a compact failure excerpt or diff is sufficient.

## Monitoring and completion

Treat Qwen's final message as a report, not proof. Codex decides whether the task is complete from workspace state, diffs, and deterministic checks. Tell the user when work was delegated to the local model and distinguish Qwen's claims from verified results.
