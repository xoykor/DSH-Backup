# Context and loop safety policy

For local investigation and data extraction, load the `tool-first` skill before
choosing a strategy. Prefer an existing deterministic tool, then a short Bash
pipeline, then a bounded Lua scratch tool, and use Python when a specialized
library is the concrete reason. Do not generate a script for a tool that already
solves the query. Keep outputs bounded and retain paths, counts, truncation and
errors as evidence.

This policy is always active for DSH sessions, especially local models such as Qwen 3.5 9B. The harness independently measures context and blocks repeated tool loops; comply with its notices immediately.

Use context deliberately. Below 65536 tokens, work normally. At 65536–81920, prefer relevant excerpts, bounded output, diffs, and the most recent useful result. Do not reread unchanged files or repeat an already-conclusive command. At 81920–94371, prepare for a compact checkpoint: preserve the objective, user requirements, completed work, decisions, modified files, important changes, relevant commands and results, unresolved errors, failed attempts, current project state, and exactly one next action. At 94371, rely on automatic compaction and continue from the resulting checkpoint rather than rebuilding old history.

When the compaction threshold is crossed by a durable assistant or tool result, the context guard interrupts the active step immediately, commits compaction, and then resumes from the compacted history. Do not wait for the current step or substep to finish.

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
