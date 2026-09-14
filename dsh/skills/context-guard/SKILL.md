---
name: context-guard
description: Persistent DSH context-budget, checkpoint, and loop-safety policy for local-model sessions. It is automatically reinforced by the harness; do not wait for a user invocation.
disable-model-invocation: false
user-invocable: false
---

# Context Guard

This skill is automatically active with the DSH context guard. Follow its budget notices and deterministic tool blocks.

- Normal operation below 65536 estimated tokens.
- Economy mode from 65536 to 81920: use targeted reads, concise results, and diffs.
- Checkpoint preparation from 81920 to 91750: preserve the live objective, constraints, work completed, decisions, changed files, relevant commands/results, unresolved errors, failed approaches, current state, and one next action.
- Pause → state summary → persistence → compaction begins at 91750 estimated tokens for the local robust policy (thresholdRatio 0.70 with a 131072-token window).

When the threshold is reached, the executor pauses normal work, waits for the interrupted turn to settle, asks the session model for a text-only state summary of the full balanced durable history (including the latest work), flushes that summary to storage, then replaces the history and resumes. No tools execute during the summary. Preserve job IDs, artifact/log paths, uncertain side effects, failed attempts and one next action. The executor prices the summary input plus instructions and schemas, reduces its output cap if necessary, and requires input + output cap + safety margin < context capacity. A missing, truncated, failed or unsaved summary never authorizes history replacement. Compaction does not reset logical execution budgets or anti-loop evidence. Summary output reserve: 8192 tokens (including model reasoning); safety reserve: 4096 tokens.

The executor measures progress from result fingerprints, successful workspace mutations, referenced files, and recent action sequences. Identical reads, repeated timeouts, and materially equivalent calls without new evidence do not reset the budget. Assistant prose is only a signal; it never counts as progress.

Every turn has hard executor budgets: 48 steps and 48 tool calls. Local Robust 9B and 27B have no whole-turn wall-clock deadline (`maxTurnMs: null`). Other presets retain their configured time budget. Execution-token caps apply only if explicitly configured; context capacity is not a cumulative usage cap. These counters include different tools in the same investigation and are reset only by a new user turn; follow executor notices for compaction and continuation.

After a timeout, the existing managed process executor must settle the process tree and collect available output before the guard enters diagnostic mode. Diagnostic mode permits at most three executor-verified read-only calls and two minutes. Managed-job wait expiry with a running job is not an execution timeout. The exact timed-out command is blocked until the executor observes a relevant code/configuration change or a changed execution strategy.

When the guard emits `PAUSE`, it cancels the active agent turn and denies subsequent tool calls at the executor boundary. A model-written explanation or a context notice cannot override that state. A repeated cycle such as read → grep → rerun → read is closed when the tool/file/result sequence repeats, even if the individual calls are not identical.
