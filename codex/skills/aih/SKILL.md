---
name: aih
description: Run software-development tasks through the external AI Clean Harness (AIH), which independently orchestrates coding, deterministic quality gates, retries, review, and final regression testing. Invoke explicitly with $aih.
---

# AI Clean Harness

Use the external `aih` executable as the authority for implementing and verifying the user's requested software-development task.

## Critical rule

When this skill is explicitly invoked, DO NOT implement the requested feature directly in this Codex session.

This Codex session is only the operator of AIH.

AIH is responsible for:

- creating an isolated Git worktree;
- invoking the coding agent;
- running deterministic quality gates;
- retrying failed implementations;
- invoking an independent reviewer;
- running final regression tests;
- deciding whether the task is ACCEPTED or FAILED.

Never substitute your own judgment for an AIH quality gate.

Never claim a task succeeded merely because another agent says its tests passed.

## Preconditions

Before invoking AIH:

1. Confirm `aih` exists and is executable.
2. Confirm the current directory belongs to a Git repository.
3. Confirm `harness.yaml` exists.
4. Inspect `git status`.
5. Do not silently change `harness.yaml`.
6. Do not manually implement the requested feature.

If AIH has not been initialized in the repository, explain that `aih init` is required rather than silently inventing configuration.

## Execution

Interpret everything the user writes after `$aih` as the task to be given to the harness.

Run from the current project root:

`aih solve "<user task>"`

Preserve the user's task and requirements accurately.

Allow AIH to complete its own pipeline.

Do not edit project source files outside AIH while the solve operation is running.

## Result

After AIH finishes, inspect its actual result.

Report concisely:

- task ID;
- final state;
- attempts used;
- gates that passed or failed;
- reviewer result;
- generated branch;
- ACCEPTED or FAILED.

For additional information, use AIH commands when appropriate:

`aih status`

`aih log`

`aih diff`

Do not merge automatically.

Do not cherry-pick automatically.

Do not run `aih accept` or `aih reject` unless explicitly requested by the user.

## Failure behavior

If AIH reports FAILED:

- report the actual failed gate/reviewer result;
- do not bypass the failed gate;
- do not manually implement a workaround;
- do not alter tests merely to obtain PASS;
- do not disable lint, build, test, review, or regression checks.

## Recursion protection

AIH itself can invoke Codex as its coder and reviewer.

If this Codex process was launched by AIH as part of an AIH task, NEVER invoke `aih` recursively.

In an AIH-managed coder/reviewer session, perform only the role requested by the harness.

The explicit `$aih` invocation belongs to the outer user-controlled Codex session.

## Authority

The trust hierarchy is:

User
→ AIH orchestrator
→ deterministic gates
→ coding/review agents

The agent does not decide whether the gates matter.

The harness decides.
