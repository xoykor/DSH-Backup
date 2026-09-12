# Context and loop safety policy

This policy is always active for DSH sessions, especially local models such as Qwen 3.5 9B. The harness independently measures context and blocks repeated tool loops; comply with its notices immediately.

Use context deliberately. Below roughly 20k tokens, work normally. At 20k–25k, prefer relevant excerpts, bounded output, diffs, and the most recent useful result. Do not reread unchanged files or repeat an already-conclusive command. At 25k–30k, prepare for a compact checkpoint: preserve the objective, user requirements, completed work, decisions, modified files, important changes, relevant commands and results, unresolved errors, failed attempts, current project state, and exactly one next action. Around 30k, rely on automatic compaction and continue from the resulting checkpoint rather than rebuilding old history.

Progress means new evidence, a useful new error, a changed test outcome, a confirmed correction, an eliminated hypothesis, a completed step, or information required for the next decision. Executing a tool by itself is not progress.

Never keep retrying equivalent actions. After three actions without significant progress, stop the current strategy, state the repeated pattern and failed evidence concisely, then choose a materially different safe approach. After five equivalent attempts, treat the approach as blocked. If no rational alternative remains, stop and report the specific blocker rather than spending more context.

When compacting or reporting state, retain exact paths, commands, error messages, identifiers, constraints, decisions, failed approaches, and the next concrete action. Discard stale terminal output, duplicated reasoning, and superseded plans.

## PTC `run_code` source-safety policy

When using the TypeScript `run_code` tool, the `code` and `description` arguments are JSON string values. Keep the outer tool-call payload valid JSON, and make the program itself valid erasable TypeScript. Do not place raw multiline or quote-heavy file content in a double-quoted TypeScript string.

For `tools.write`, assign large or quote-heavy content first with a template literal (use `String.raw` when the content contains backslashes), then pass the variable.

```typescript
const content = String.raw`...`;
return await tools.write({ file_path: "...", content });
```

Use `JSON.stringify(value)` for generated JSON/object content. Escape a backtick or `${` only when it occurs in the content, keep writes short and auditable, and after a parse failure change the representation before retrying.
