# Context and loop safety policy

For local investigation and data extraction, load the `tool-first` skill before
choosing a strategy. Prefer an existing deterministic tool, then a short Bash
pipeline, then a bounded Lua scratch tool, and use Python when a specialized
library is the concrete reason. Do not generate a script for a tool that already
solves the query. Keep outputs bounded and retain paths, counts, truncation and
errors as evidence.

This policy is always active for DSH sessions, especially local models such as Qwen 3.5 9B. The harness independently measures context and blocks repeated tool loops; comply with its notices immediately.

For Local Robust 27B (Qwen 3.8 27B, 64000-token window), use economy at 32000 tokens, checkpoint at 40000 and pause for summary at 44800. Its preset-local `context-guard` skill supplies the matching policy. These values override the 9B/default ranges in the following paragraph only for that preset.

For Local Robust 9B (Ornith, 131072-token context), use context deliberately. Below 65536 tokens, work normally. At 65536–81920, prefer relevant excerpts, bounded output, diffs, and the most recent useful result. Do not reread unchanged files or repeat an already-conclusive command. At 81920–91750, prepare for a compact checkpoint: preserve the objective, user requirements, completed work, decisions, modified files, important changes, relevant commands and results, unresolved errors, failed attempts, current project state, and exactly one next action. At 91750, pause for a saved state summary before compaction. Other presets keep their configured policies.

When the threshold is reached, the executor pauses normal work, waits for the interrupted turn to settle, asks the session model for a text-only state summary of the full balanced durable history (including the latest work), flushes that summary to storage, then replaces the history and resumes. No tools execute during the summary. Preserve job IDs, artifact/log paths, uncertain side effects, failed attempts and one next action. The executor prices the summary input plus instructions and schemas, reduces its output cap if necessary, and requires input + output cap + safety margin < context capacity. A missing, truncated, failed or unsaved summary never authorizes history replacement. Compaction does not reset logical execution budgets or anti-loop evidence.

Ornith reserves 8192 summary tokens plus 4096 safety tokens; Qwen reserves 4000 plus 2000. These reserves are separate from the normal response caps (24576 and 12000).

Progress means new evidence, a useful new error, a changed test outcome, a confirmed correction, an eliminated hypothesis, a completed step, or information required for the next decision. Executing a tool by itself is not progress.

Never keep retrying equivalent actions. After three actions without significant progress, stop the current strategy, state the repeated pattern and failed evidence concisely, then choose a materially different safe approach. After five equivalent attempts, treat the approach as blocked. If no rational alternative remains, stop and report the specific blocker rather than spending more context.

Managed background work uses `job_output` with the recorded `job_id`, `wait: true`, and a bounded wait (normally 30000ms) when no independent work remains. An executor-recognized blocking wait for an active job is neutral, even with empty output: it does not count as repeated investigation or reset previous failures. A wait that expires with `running`/`stopping` is pending, not an execution timeout or success. Prefer completion notifications; do not duplicate the job or switch tools to evade a guard. Only executor-marked observers are allowed during timeout diagnosis; editing a goal is not read-only. Hard budgets still apply. After a hard stop, preserve the pending job and wait for a new authorized turn; a notification does not reset the guard. See the `acompanhamento` skill for collection and artifact verification.

When compacting or reporting state, retain exact paths, commands, error messages, identifiers, constraints, decisions, failed approaches, and the next concrete action. Discard stale terminal output, duplicated reasoning, and superseded plans.

## PTC `run_code` source-safety policy

When using the TypeScript `run_code` tool, the `code` and `description` arguments are JSON string values. Keep the outer tool-call payload valid JSON, and make the program itself valid erasable TypeScript. Do not place raw multiline or quote-heavy file content in a double-quoted TypeScript string.

For `tools.write`, assign large or quote-heavy content first with a template literal (use `String.raw` when the content contains backslashes), then pass the variable.

```typescript
const content = String.raw`...`;
return await tools.write({ file_path: "...", content });
```

Use `JSON.stringify(value)` for generated JSON/object content. Escape a backtick or `${` only when it occurs in the content, keep writes short and auditable, and after a parse failure change the representation before retrying.

Local Robust 9B and Local Robust 27B have no cumulative tool-call, step or whole-turn time ceiling (`maxTurnToolCalls: null`, `maxTurnSteps: null`, `maxTurnMs: null`). Continue authorized productive work through compaction until the requested deliverable is implemented and verified. Do not stop merely because 48 calls/steps or 15 minutes elapsed. Anti-loop checks, tool-specific timeouts, context compaction and the diagnostic budget remain enforced. Stop for user cancellation, missing authority or a demonstrated blocker with no productive alternative; report the evidence and pending work. Never claim completion solely to end a long run.
