---
name: context-guard
description: Persistent DSH context-budget, checkpoint, and loop-safety policy for local-model sessions. It is automatically reinforced by the harness; do not wait for a user invocation.
disable-model-invocation: false
user-invocable: false
---

# Context Guard

This skill is automatically active with the DSH context guard. Follow its budget notices and deterministic tool blocks.

- Normal operation below 131072 estimated tokens.
- Economy mode from 131072 to 163840: use targeted reads, concise results, and diffs.
- Checkpoint preparation from 163840 to 188743: preserve the live objective, constraints, work completed, decisions, changed files, relevant commands/results, unresolved errors, failed approaches, current state, and one next action.
- Automatic compacting begins at 188743 estimated tokens for the local robust policy (thresholdRatio 0.72 with a 262144-token window).

The executor measures progress from result fingerprints, successful workspace mutations, referenced files, and recent action sequences. Identical reads, repeated timeouts, and materially equivalent calls without new evidence do not reset the budget. Assistant prose is only a signal; it never counts as progress.

Every turn has hard executor budgets: 48 steps, 48 tool calls, 15 minutes, and 240,000 high-water tokens by default. These counters include different tools in the same investigation and are reset only by a new user turn; compaction cannot renew them.

After a timeout, the existing managed process executor must settle the process tree and collect available output before the guard enters diagnostic mode. Diagnostic mode permits at most three bounded inspection/test-diagnosis calls, two minutes, and 24,000 tokens. The exact timed-out command is blocked until the executor observes a relevant code/configuration change or a changed execution strategy.

When the guard emits `PAUSE`, it cancels the active agent turn and denies subsequent tool calls at the executor boundary. A model-written explanation or a context notice cannot override that state. A repeated cycle such as read → grep → rerun → read is closed when the tool/file/result sequence repeats, even if the individual calls are not identical.
