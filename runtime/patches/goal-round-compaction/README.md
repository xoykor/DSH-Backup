# Resume goal rounds after context compaction

Patch for `@deepseek-ai/dsh-goal-round-driver@0.1.5-rc.2`.

The context guard deliberately rejects admission while a saved checkpoint and
compaction are settling. The stock goal-round driver treated that transient
rejection as a permanent `prompt-rejected` block, so a goal could stop before
its first round. This patch retries the drive request for the two explicit
context-guard compaction reasons, recognizes the durable pause created by that
same abort, and re-arms an active goal automatically after a session-start
boundary. Other prompt rejections still block the goal as before, and an
intentional user pause is never resumed automatically.

Apply with:

```sh
node apply-goal-round-compaction.mjs --target PACKAGE_DIRECTORY
```

Use `--check` for read-only verification. The applicator validates the approved
runtime hashes, creates a one-time backup, applies atomically, and refuses
unknown runtime contents. `restore-dsh.sh` applies and verifies this patch.

Restart DSH after applying it so the running process loads the patched module.
The runtime patch does not restart the process itself.
