# Context and loop safety policy

For local investigation and data extraction, load the `tool-first` skill before
choosing a strategy. Prefer an existing deterministic tool, then a short Bash
pipeline, then a bounded Lua scratch tool, and use Python when a specialized
library is the concrete reason. Do not generate a script for a tool that already
solves the query. Keep outputs bounded and retain paths, counts, truncation and
errors as evidence.

This policy is always active for DSH sessions, especially local models such as Qwen 3.5 9B. The harness independently measures context and blocks repeated tool loops; comply with its notices immediately.

Context limits and thresholds are runtime-configured per preset by the active
`context-guard` settings. Treat its explicit notices and the native context
meter as authoritative for the current session; do not infer a window or a
compaction threshold from static documentation in this file. Sliders may change
the effective values without changing this document.

When the threshold is reached, the executor pauses normal work, waits for the interrupted turn to settle, asks the session model for a text-only state summary of the full balanced durable history (including the latest work), flushes that summary to storage, then replaces the history and resumes. No tools execute during the summary. Preserve job IDs, artifact/log paths, uncertain side effects, failed attempts and one next action. The executor prices the summary input plus instructions and schemas, reduces its output cap if necessary, and requires input + output cap + safety margin < context capacity. A missing, truncated, failed or unsaved summary never authorizes history replacement. Compaction does not reset logical execution budgets or anti-loop evidence.

Ornith reserves 8192 summary tokens plus 4096 safety tokens; Qwen reserves 4000 plus 2000. These reserves are separate from the normal response caps (24576 and 12000).

Progress means new evidence, a useful new error, a changed test outcome, a confirmed correction, an eliminated hypothesis, a completed step, or information required for the next decision. Executing a tool by itself is not progress.

Never keep retrying equivalent actions. After three actions without significant progress, stop the current strategy, state the repeated pattern and failed evidence concisely, then choose a materially different safe approach. After five equivalent attempts, treat the approach as blocked. If no rational alternative remains, stop and report the specific blocker rather than spending more context.

Managed background work uses `job_output` with the recorded `job_id`, `wait: true`, and a bounded wait (normally 30000ms) when no independent work remains. An executor-recognized blocking wait for an active job is neutral, even with empty output: it does not count as repeated investigation or reset previous failures. A wait that expires with `running`/`stopping` is pending, not an execution timeout or success. Prefer completion notifications; do not duplicate the job or switch tools to evade a guard. Only executor-marked observers are allowed during timeout diagnosis; editing a goal is not read-only. Hard budgets still apply. After a hard stop, preserve the pending job and wait for a new authorized turn; a notification does not reset the guard. See the `acompanhamento` skill for collection and artifact verification.

When compacting or reporting state, retain exact paths, commands, error messages, identifiers, constraints, decisions, failed approaches, and the next concrete action. Discard stale terminal output, duplicated reasoning, and superseded plans.

## Durable memory

`dsh-memory` is the persistent cross-session memory layer for this environment.

Its injected memory policy is authoritative for memory tool usage. Use
`memory_search` when relevant prior-session information may matter and is not
already recalled, `memory_write` for newly learned durable facts likely to
matter in future sessions, and `memory_update` when an existing durable fact
changes.

Prefer canonical keys for facts that should have one current value. Do not store
transient task state, logs, secrets, intermediate results or information easily
recovered from the repository.

Do not create a separate ad-hoc memory system when `dsh-memory` can represent
the information. `memory_review` and `memory_stats` are maintenance and
diagnostic tools; do not call them routinely when the task does not require
memory curation.

## PTC `run_code` source-safety policy

When using the TypeScript `run_code` tool, the `code` and `description` arguments are JSON string values. Keep the outer tool-call payload valid JSON, and make the program itself valid erasable TypeScript. Do not place raw multiline or quote-heavy file content in a double-quoted TypeScript string.

For `tools.write`, assign large or quote-heavy content first with a template literal (use `String.raw` when the content contains backslashes), then pass the variable.

```typescript
const content = String.raw`...`;
return await tools.write({ file_path: "...", content });
```

Use `JSON.stringify(value)` for generated JSON/object content. Escape a backtick or `${` only when it occurs in the content, keep writes short and auditable, and after a parse failure change the representation before retrying.

Local Robust 9B and Local Robust 27B have no cumulative tool-call, step or whole-turn time ceiling (`maxTurnToolCalls: null`, `maxTurnSteps: null`, `maxTurnMs: null`). Continue authorized productive work through compaction until the requested deliverable is implemented and verified. Do not stop merely because 48 calls/steps or 15 minutes elapsed. Anti-loop checks, tool-specific timeouts, context compaction and the diagnostic budget remain enforced. Stop for user cancellation, missing authority or a demonstrated blocker with no productive alternative; report the evidence and pending work. Never claim completion solely to end a long run.

## Skill catalog and locations

The live catalog is rooted at `__DSH_HOME__/skills`. Load a matching skill by
name with the DSH `skill` tool before acting, then follow its complete
`SKILL.md`. Do not load every skill preemptively. Paths below are relative to
`__DSH_HOME__`; the versioned source uses the same layout under `dsh/skills/`.

For `prism-modpack`, loading `SKILL.md` is not the end of discovery: before the
first Goal, web search or shell command of an operational task, read
`skills/prism-modpack/references/operations.md` completely. `status` and
`configure-wrapper` are subcommands of `scripts/modpack.py`, never `.sh` files.

| Skill | Use when | Instruction file |
|---|---|---|
| `acompanhamento` | Waiting for managed long-running work and verifying its real completion. | `skills/acompanhamento/SKILL.md` |
| `apresentacoes-template` | Filling an existing PPTX template and checking rendered slides. | `skills/apresentacoes-template/SKILL.md` |
| `compressao-midia` | Compressing local images, audio or video with measured limits. | `skills/compressao-midia/SKILL.md` |
| `configuracoes-estruturadas` | Editing explicit paths and values in JSON, YAML or TOML. | `skills/configuracoes-estruturadas/SKILL.md` |
| `context-guard` | Applying the persistent context, checkpoint and loop policy; normally activated by the harness. | `skills/context-guard/SKILL.md` |
| `dados-tabulares` | Transforming or reconciling local CSV, TSV or JSON tables. | `skills/dados-tabulares/SKILL.md` |
| `diagnostico-servicos-logs` | Diagnosing local services, containers, URLs or log files without changing them. | `skills/diagnostico-servicos-logs/SKILL.md` |
| `documentos-template` | Filling an existing DOCX template and validating its package and fields. | `skills/documentos-template/SKILL.md` |
| `graficos-locais` | Generating PNG, SVG or PDF charts from validated local tables. | `skills/graficos-locais/SKILL.md` |
| `imagens-lote` | Resizing, cropping, converting or thumbnailing local images in batches. | `skills/imagens-lote/SKILL.md` |
| `jornadas-navegador` | Running short explicit browser journeys with checks and failure captures. | `skills/jornadas-navegador/SKILL.md` |
| `local-single-agent` | Running development work with one local main agent and no delegated model calls. | `skills/local-single-agent/SKILL.md` |
| `midia-local` | Inspecting, cutting, extracting or converting local audio and video with FFmpeg. | `skills/midia-local/SKILL.md` |
| `organizacao-arquivos` | Planning and applying explicit batch copies or renames with collision checks. | `skills/organizacao-arquivos/SKILL.md` |
| `paginas-estaticas` | Creating or adjusting a small local HTML/CSS page from a template. | `skills/paginas-estaticas/SKILL.md` |
| `pdf-utilidades` | Inspecting or transforming PDFs, extracting text or running OCR. | `skills/pdf-utilidades/SKILL.md` |
| `pesquisa-fontes` | Answering bounded external questions with consulted sources and separated inference. | `skills/pesquisa-fontes/SKILL.md` |
| `planilhas-locais` | Creating or editing explicit cells, ranges, sheets or tables in local XLSX files. | `skills/planilhas-locais/SKILL.md` |
| `prism-modpack` | Building complete Prism Launcher modpacks and correcting startup crashes from logs. | `skills/prism-modpack/SKILL.md` |
| `quebra-de-loop` | Detecting and breaking redundant investigation loops. | `skills/quebra-de-loop/SKILL.md` |
| `sqlite-local` | Inspecting schemas and querying local SQLite databases read-only. | `skills/sqlite-local/SKILL.md` |
| `testes-api` | Checking authorized HTTP endpoints from a bounded JSON specification. | `skills/testes-api/SKILL.md` |
| `tool-first` | Investigating local files, repositories and data with deterministic tools first. | `skills/tool-first/SKILL.md` |
| `verificacao-projeto` | Discovering and running checks that already exist in a local project. | `skills/verificacao-projeto/SKILL.md` |

Supporting `scripts/`, `references/`, `assets/`, `fixtures/` and `tests/` live
inside the same skill directory. Resolve relative links from that skill's
`SKILL.md`; do not guess paths in another skill.
