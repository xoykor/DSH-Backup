import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, symlinkSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { findTarget, applyPatch } from '../apply-job-observation.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoGuard = resolve(root, '../../../dsh/plugins/dsh-context-guard/lib/index.js');
const guardPath = process.env.DSH_GUARD_TEST_TARGET ?? (existsSync(repoGuard) ? repoGuard : resolve(root, '../guard/lib/index.js'));
const { apply: applyGuard } = await import(pathToFileURL(guardPath));
const installed = findTarget(process.env.DSH_JOBS_TEST_TARGET);
const require = createRequire(installed);
const { Context } = await import(pathToFileURL(require.resolve('@deepseek-ai/cordis')));
const { ToolRuntime, validateJsonSchemaValue } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-tools')));
const { LocalJobRegistry } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-jobs-local')));
const temp = mkdtempSync(join(tmpdir(), 'dsh-job-observation-tests-'));
// Import unchanged patch payload using the installed dependencies; no copies in the installation.
let modules = dirname(installed);
while (dirname(modules) !== modules && !modules.endsWith('/node_modules')) modules = dirname(modules);
symlinkSync(modules, join(temp, 'node_modules'), 'dir');
writeFileSync(join(temp, 'patched.mjs'), readFileSync(join(root, 'lib/index.js')));
const plugin = await import(pathToFileURL(join(temp, 'patched.mjs')));
const capability = Symbol.for('dsh.executor.jobObservation.v1');
const tick = () => new Promise((resolve) => setImmediate(resolve));
after(() => rmSync(temp, { recursive: true, force: true }));

function harness(config = {}) {
  const ctx = new Context();
  ctx.systemPrompt = { tools() {}, section() {}, getSectionOrder() { return 0; } };
  ctx.provide('agents', { get: (id) => owners.get(id) });
  const owners = new Map();
  new ToolRuntime(ctx);
  new LocalJobRegistry(ctx, { maxConcurrentJobsPerOwner: 20 });
  plugin.apply(ctx, config);
  function owner(id) {
    const notices = [];
    const agent = { id, ctx, status: 'idle', followup: (message) => notices.push(['followup', message]), inject: (message) => notices.push(['inject', message]) };
    owners.set(id, agent);
    return { agent, notices };
  }
  function start({ owner: agent, outputLimitBytes, readOutput } = {}) {
    let finish;
    let cancelled = 0;
    const id = ctx.jobs.start({
      kind: 'bash', label: 'test job', owner: agent, outputLimitBytes,
      run: () => ({ done: new Promise((r) => { finish = r; }), readOutput, cancel() { cancelled += 1; finish({ status: 'killed' }); } }),
    });
    return { id, finish, cancelled: () => cancelled };
  }
  const output = ctx.tools.get('job_output');
  function exec(args, agent, signal = new AbortController().signal) {
    return { name: 'job_output', arguments: args, agent, signal };
  }
  return { ctx, owner, start, output, exec };
}

test('real registry preserves capability on the real definition, with no kill capability or schema leakage', () => {
  const h = harness();
  const cap = h.output[capability];
  assert.equal(cap.readOnly, true);
  assert.equal(Object.isFrozen(cap), true);
  assert.equal(Object.getOwnPropertyDescriptor(h.output, capability).writable, false);
  assert.equal(h.ctx.tools.get('job_kill')[capability], undefined);
  assert.deepEqual(h.ctx.tools.get('job_list')[capability].observe({}), { kind: 'list' });
  assert.equal(JSON.stringify(h.ctx.tools.schemas()).includes('jobObservation'), false);
});

test('observation uses native ownership and returns capped effective wait without reading output', async () => {
  const h = harness({ waitTimeoutMs: 20, maxWaitTimeoutMs: 50 });
  const a = h.owner('a'); const b = h.owner('b');
  let reads = 0;
  const job = h.start({ owner: a.agent, readOutput: () => { reads += 1; return 'new'; } });
  assert.deepEqual(h.output[capability].observe(h.exec({ job_id: job.id, wait: true, timeout_ms: 100 }, a.agent)), { kind: 'output', jobId: job.id, status: 'running', waitMs: 50 });
  assert.equal(h.output[capability].observe(h.exec({ job_id: job.id, wait: true }, a.agent)).waitMs, 20);
  assert.equal(h.output[capability].observe(h.exec({ job_id: job.id }, a.agent)).waitMs, 0);
  assert.equal(reads, 0);
  assert.throws(() => h.output[capability].observe(h.exec({ job_id: job.id }, b.agent)), /another session/);
  assert.throws(() => h.output[capability].observe(h.exec({ job_id: 'missing' }, a.agent)), /unknown job/);
  job.finish({ status: 'completed' }); await tick();
});

test('model arguments cannot mint capabilities and invalid waits receive no observation', async () => {
  const h = harness(); const job = h.start();
  for (const args of [null, [], {}, { job_id: '' }, { job_id: 7 }, { job_id: job.id, wait: 'true' }, { job_id: job.id, timeout_ms: -1 }, { job_id: job.id, timeout_ms: 0 }, { job_id: job.id, timeout_ms: Infinity }, { job_id: job.id, timeout_ms: NaN }, { job_id: job.id, readOnly: true }]) {
    assert.equal(h.output[capability].observe(h.exec(args)), undefined);
  }
  await assert.rejects(h.output.execute({ job_id: job.id, wait: 'true' }, h.exec({})), /wait/);
  job.finish({ status: 'completed' }); await tick();
});

test('native wait expires successfully, leaves job alive, and emits waitExpired rather than execution timeout', async () => {
  const h = harness(); const job = h.start();
  const args = { job_id: job.id, wait: true, timeout_ms: 5 };
  const value = await h.output.execute(args, h.exec(args));
  assert.equal(value.waitExpired, true);
  assert.equal(value.job.status, 'running');
  assert.equal(job.cancelled(), 0);
  assert.equal(value.timedOut, undefined);
  assert.deepEqual(validateJsonSchemaValue(h.output.output.schema, value, ''), []);
  const text = h.output.output.render(args, value)[0].text;
  assert.match(text, /wait expired; job remains active/);
  assert.ok(text.endsWith('[status: running]'));
  job.finish({ status: 'completed', output: 'done' }); await tick();
});

test('native wait completes early and preserves terminal output', async () => {
  const h = harness(); const job = h.start();
  const args = { job_id: job.id, wait: true, timeout_ms: 100 };
  const waiting = h.output.execute(args, h.exec(args));
  job.finish({ status: 'completed', output: 'done\n' });
  const value = await waiting;
  assert.equal(value.waitExpired, false);
  assert.equal(value.text, 'done\n');
  assert.equal(value.job.status, 'completed');
  assert.equal(h.output.output.render(args, value)[0].text, 'done\n[status: completed]');
});

test('aborting a native wait rejects observation but does not cancel managed work', async () => {
  const h = harness(); const job = h.start();
  const controller = new AbortController();
  const args = { job_id: job.id, wait: true, timeout_ms: 100 };
  const waiting = h.output.execute(args, h.exec(args, undefined, controller.signal));
  controller.abort();
  await assert.rejects(waiting, /wait aborted/);
  assert.equal(job.cancelled(), 0);
  assert.equal(h.ctx.jobs.get(job.id).status, 'running');
  job.finish({ status: 'completed' }); await tick();
});

test('nonblocking stream reads retain native delta semantics and omit waitExpired', async () => {
  const h = harness(); let text = 'first';
  const job = h.start({ readOutput: () => { const result = text; text = ''; return result; } });
  const args = { job_id: job.id };
  const first = await h.output.execute(args, h.exec(args));
  const second = await h.output.execute(args, h.exec(args));
  assert.equal(first.text, 'first'); assert.equal(second.text, '');
  assert.equal(Object.hasOwn(first, 'waitExpired'), false);
  job.finish({ status: 'completed' }); await tick();
});

test('producer failure remains terminal evidence and is not mislabeled an expired wait', async () => {
  const h = harness(); const job = h.start();
  job.finish({ status: 'failed', detail: 'real failure', output: 'stderr' }); await tick();
  const args = { job_id: job.id, wait: true, timeout_ms: 5 };
  const value = await h.output.execute(args, h.exec(args));
  assert.equal(value.job.status, 'failed'); assert.equal(value.job.detail, 'real failure');
  assert.equal(value.waitExpired, false); assert.equal(value.text, 'stderr');
});

test('native result bounds preserve final status and expiration hint', async () => {
  const h = harness(); const job = h.start({ outputLimitBytes: 180, readOutput: () => 'x'.repeat(1000) });
  const args = { job_id: job.id, wait: true, timeout_ms: 5 };
  const exec = h.exec(args);
  const value = await h.output.execute(args, exec);
  const content = h.output.output.render(args, value);
  const bounded = h.output.finalizeContent(exec, { value, content, isError: false });
  assert.ok(Buffer.byteLength(bounded[0].text) <= 180);
  assert.ok(bounded[0].text.endsWith('[status: running]'));
  assert.match(bounded[0].text, /wait expired; job remains active/);
  job.finish({ status: 'completed' }); await tick();
});

test('native completion callback wakes idle owner and terminal collection marks completion reported', async () => {
  const h = harness(); const owner = h.owner('owner'); const job = h.start({ owner: owner.agent });
  job.finish({ status: 'completed', output: 'done' }); await tick();
  assert.equal(owner.notices.length, 1); assert.equal(owner.notices[0][0], 'followup');
  const args = { job_id: job.id };
  await h.output.execute(args, h.exec(args, owner.agent));
  assert.equal(h.ctx.jobs.get(job.id, owner.agent).reported, true);
});

test('real ToolRuntime + job registry + guard permit repeated long waits and collect terminal output', async () => {
  const h = harness();
  const { agent } = h.owner('integrated');
  agent.session = { id: 'integrated-session' };
  agent.status = 'running';
  const controller = new AbortController();
  const cancellations = [];
  agent.cancel = (reason) => { cancellations.push(reason); controller.abort(); };
  h.ctx.tokenMeter = { measure: () => ({ totalTokens: 0 }) };
  applyGuard(h.ctx);
  const job = h.start({ owner: agent });
  for (let i = 0; i < 5; i += 1) {
    const result = await h.ctx.tools.execute({ ...h.exec({ job_id: job.id, wait: true, timeout_ms: 1000 }, agent, controller.signal), callId: `wait-${i}` });
    assert.equal(result.isError, false, JSON.stringify(result));
    assert.equal(result.value.waitExpired, true);
    assert.equal(result.value.job.status, 'running');
  }
  assert.equal(cancellations.length, 0);
  assert.equal(job.cancelled(), 0);
  job.finish({ status: 'completed', output: 'validated completion' }); await tick();
  const result = await h.ctx.tools.execute({ ...h.exec({ job_id: job.id }, agent, controller.signal), callId: 'final' });
  assert.equal(result.isError, false, JSON.stringify(result));
  assert.equal(result.value.job.status, 'completed');
  assert.equal(result.value.text, 'validated completion');
});

test('real guard call budget cancels active turn without killing the background job', async () => {
  const h = harness();
  const { agent } = h.owner('budget');
  agent.session = { id: 'budget-session' };
  agent.status = 'running';
  const controller = new AbortController();
  const cancellations = [];
  agent.cancel = (reason) => { cancellations.push(reason); controller.abort(); };
  h.ctx.tokenMeter = { measure: () => ({ totalTokens: 0 }) };
  applyGuard(h.ctx, { maxTurnToolCalls: 3 });
  const job = h.start({ owner: agent });
  for (let i = 0; i < 3; i += 1) {
    const result = await h.ctx.tools.execute({ ...h.exec({ job_id: job.id }, agent, controller.signal), callId: `budget-${i}` });
    if (i < 2) assert.equal(result.isError, false, JSON.stringify(result));
    else assert.equal(result.error?.info?.code, 'ABORTED', JSON.stringify(result));
  }
  assert.equal(cancellations.length, 1);
  assert.match(cancellations[0].reason, /global tool-call budget of 3/);
  assert.equal(job.cancelled(), 0);
  assert.equal(h.ctx.jobs.get(job.id, agent).status, 'running');
  job.finish({ status: 'completed' }); await tick();
});

test('applicator validates hashes, backs up once, applies idempotently, and supports read-only check', () => {
  const manifest = JSON.parse(readFileSync(join(root, 'manifest.json')));
  const fixture = join(temp, 'apply-fixture'); mkdirSync(join(fixture, 'lib'), { recursive: true });
  const target = join(fixture, 'lib/index.js');
  const installedBytes = readFileSync(installed);
  const observed = createHash('sha256').update(installedBytes).digest('hex');
  let base = installedBytes;
  if (observed === manifest.patchedSha256) base = readFileSync(`${installed}.before-job-observation-${manifest.baseSha256.slice(0, 12)}`);
  assert.equal(createHash('sha256').update(base).digest('hex'), manifest.baseSha256);
  writeFileSync(target, base);
  assert.equal(applyPatch({ target: fixture, check: true }).status, 'unpatched');
  assert.deepEqual(readFileSync(target), base);
  const first = applyPatch({ target: fixture });
  assert.equal(first.changed, true); assert.deepEqual(readFileSync(first.backup), base);
  assert.equal(applyPatch({ target, check: true }).status, 'patched');
  assert.equal(applyPatch({ target }).changed, false);
  writeFileSync(target, '// external edit\n');
  assert.throws(() => applyPatch({ target }), /Unsupported runtime content/);
  assert.equal(readFileSync(target, 'utf8'), '// external edit\n');
});
