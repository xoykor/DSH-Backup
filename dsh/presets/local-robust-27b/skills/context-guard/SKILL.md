---
name: context-guard
description: Context-budget, checkpoint, and loop-safety policy for Local Robust 27B / Qwen 3.8 27B. Effective limits come from the active sliders/settings and are automatically reinforced by the harness; do not wait for a user invocation.
---

# Context Guard

This skill is automatically active with the DSH context guard. Follow its budget notices and deterministic tool blocks.

The first `ACTIVE CONTEXT POLICY` notice and the native context meter define the
effective values for this session. They come from the selected preset's sliders
and ratios. Use the active economy, checkpoint and compaction thresholds; do not
infer them from the model capacity, another preset, or this skill.

- Normal operation is below the active economy threshold.
- Economy mode runs from the active economy threshold to the active checkpoint threshold: use targeted reads, concise results, and diffs.
- Checkpoint preparation runs from the active checkpoint threshold to the active compaction threshold: preserve the live objective, constraints, work completed, decisions, changed files, relevant commands/results, unresolved errors, failed approaches, current state, and one next action.
- Pause → state summary → persistence → compaction begins at the active compaction threshold.

When the threshold is reached, the executor pauses normal work, waits for the interrupted turn to settle, asks the session model for a text-only state summary of the full balanced durable history (including the latest work), flushes that summary to storage, then replaces the history and resumes. No tools execute during the summary. Preserve job IDs, artifact/log paths, uncertain side effects, failed attempts and one next action. The executor prices the summary input plus instructions and schemas, reduces its output cap if necessary, and requires input + output cap + safety margin < context capacity. A missing, truncated, failed or unsaved summary never authorizes history replacement. Compaction does not reset logical execution budgets or anti-loop evidence. Summary output reserve: 4000 tokens (including model reasoning); safety reserve: 2000 tokens.

The executor measures progress from result fingerprints, successful workspace mutations, referenced files, and recent action sequences. Identical reads, repeated timeouts, and materially equivalent calls without new evidence do not reset the budget. Assistant prose is only a signal; it never counts as progress.

Local Robust 9B and 27B have no cumulative call, step or whole-turn time ceiling (`maxTurnToolCalls: null`, `maxTurnSteps: null`, `maxTurnMs: null`). Continue productive authorized work through compaction until delivery is implemented and verified. Anti-loop checks, tool-specific timeouts and the 2-minute diagnostic budget still apply. Additional execution-token limits apply only when explicitly configured; the active context window is not a cumulative token allowance. Compaction does not erase evidence of repeated failures or renew diagnostic allowances. Stop on user cancellation, missing authority or a demonstrated blocker with no productive alternative.

After a timeout, the existing managed process executor must settle the process tree and collect available output before the guard enters diagnostic mode. Diagnostic mode permits at most three executor-verified read-only calls and two minutes. A managed-job wait may expire with the job still running; this does not trigger diagnostic mode. The exact timed-out command is blocked until the executor observes a relevant code/configuration change or a changed execution strategy.

When the guard emits `PAUSE`, it cancels the active agent turn and denies subsequent tool calls at the executor boundary. A model-written explanation or a context notice cannot override that state. A repeated cycle such as read → grep → rerun → read is closed when the tool/file/result sequence repeats, even if the individual calls are not identical.

The guard consolidates the full balanced history using the active response,
summary, safety and retention settings. Retry counts and tool/diagnostic
timeouts do not scale with the context window; the whole-turn deadline is
disabled for this preset. All non-context skills remain available from the
shared roots.
