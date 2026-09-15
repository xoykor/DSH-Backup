# Local inference HTTP timeout

The LM Studio profile already allows 900000 ms for requests and idle streaming.
The underlying Node HTTP transport still defaults to a 300000 ms body/header
timeout. During a long prefill with no streamed data, the connection can end
with `terminated` before the configured DSH watchdog expires.

This adapter patch supplies pi-ai's supported `fetch` option for loopback
providers. It delegates to the existing Undici dispatcher, setting the request
header timeout from `timeoutMs` and the idle body timeout from
`streamIdleTimeoutMs`. The override applies only to the configured origin;
redirects elsewhere keep existing policy. Abort signals, TLS validation,
request content, shared pools and DSH watchdogs remain in effect. No global
dispatcher is changed. Both Qwen and Ornith use this LM Studio route.

Restore applies this hash-checked patch automatically. Existing runtime files
are backed up. Restart DSH to load the updated adapter. A previously failed
compaction requires resuming the session; this patch does not edit its history.

Tests: `node --test --test-isolation=none tests/transport.test.mjs`.
Set `DSH_RUNTIME_MODULES` to the installed runtime node_modules path if needed.
Tests use a local HTTP server with shortened deadlines to reproduce silent
prefill failure and verify successful completion, cancellation and scoping.
