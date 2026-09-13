import test from 'node:test';
import assert from 'node:assert/strict';
import { apply } from '../lib/index.js';

function fixture(config = {}, options = {}) {
  const hooks = new Map();
  let guard;
  let agent = {
    session: { id: options.sessionId ?? 'synthetic' },
    status: 'running',
    cancelCalls: [],
    cancel(...args) { this.cancelCalls.push(args); },
  };
  const meterValues = options.meterValues ?? [];
  let meterIndex = 0;
  apply({
    tokenMeter: options.tokenMeter === false ? undefined : {
      measure() {
        const totalTokens = meterValues.length === 0
          ? 0
          : meterValues[Math.min(meterIndex++, meterValues.length - 1)];
        return { totalTokens };
      },
    },
    tools: { guard(fn) { guard = fn; } },
    on(name, fn) { hooks.set(name, fn); },
  }, config);
  const call = (name, argumentsValue = {}, metadata = {}) => ({
    name, arguments: argumentsValue, agent, ...metadata,
  });
  return {
    get agent() { return agent; },
    guard(exec) { return guard({ ...exec, agent }); },
    async post(exec, result) {
      return hooks.get('tools/post-execute')({ ...exec, agent }, result, async () => ({}));
    },
    async preStep(turn = 1, step = 1, messages = []) {
      return hooks.get('agent/pre-step')(
        { agent, signal: new AbortController().signal, turn, step, messages },
        async () => ({ kind: 'enter', messages: [] }),
      );
    },
    emitSession(event) { hooks.get('session/event')({ id: agent.session.id }, event); },
    disposeSession() { hooks.get('session/disposed')({ id: agent.session.id }); },
    replaceAgent(nextAgent) {
      hooks.get('agent/disposed')({ agent });
      agent = nextAgent;
    },
    call,
  };
}

const ok = (text, value) => ({
  ...(value === undefined ? {} : { value }),
  content: [{ type: 'text', text }],
});
const failure = (text, value) => ({
  isError: true,
  ...(value === undefined ? {} : { value }),
  content: [{ type: 'text', text }],
});

test('preserves significant spaces and excludes description from identity', async () => {
  const f = fixture({ noProgressLimit: 20, equivalentBlockLimit: 2 });
  const first = f.call('bash', { command: 'printf  a', description: 'one' });
  assert.equal(f.guard(first), undefined);
  await f.post(first, ok('same'));
  const second = f.call('bash', { command: 'printf  a', description: 'two' });
  assert.equal(f.guard(second), undefined);
  await f.post(second, ok('same'));
  const third = f.call('bash', { command: 'printf  a', description: 'three' });
  assert.equal(f.guard(third), undefined);
  await f.post(third, ok('same'));
  assert.match(f.guard(f.call('bash', { command: 'printf  a', description: 'four' })), /CONTEXT-GUARD/);

  const distinct = fixture({ noProgressLimit: 20, equivalentBlockLimit: 2 });
  const spaced = distinct.call('bash', { command: 'printf a' });
  assert.equal(distinct.guard(spaced), undefined);
  await distinct.post(spaced, ok('same'));
  assert.equal(distinct.guard(distinct.call('bash', { command: 'printf  a' })), undefined);
});

test('contains changing text from one parse failure family as no progress', async () => {
  const f = fixture({ noProgressLimit: 3, equivalentBlockLimit: 20 });
  for (let index = 0; index < 3; index += 1) {
    const exec = f.call('run_code', { code: `bad syntax ${index}`, description: `attempt ${index}` });
    assert.equal(f.guard(exec), undefined);
    await f.post(exec, failure(`type-strip parse failed at column ${index + 1}`));
  }
  assert.match(f.guard(f.call('run_code', { code: 'bad syntax 99' })), /parse family/);
});

test('classifies native Bash nonzero exits and sandbox denials as failures', async () => {
  const f = fixture({ noProgressLimit: 2, equivalentBlockLimit: 20 });
  for (let index = 0; index < 2; index += 1) {
    const exec = f.call('bash', { command: 'pytest' });
    assert.equal(f.guard(exec), undefined);
    await f.post(exec, ok(`failed ${index}`, {
      kind: 'foreground', exitCode: 1, signal: null, timedOut: false,
      stdout: { text: `failed ${index}`, truncated: false },
      stderr: { text: '', truncated: false },
    }));
  }
  assert.match(f.guard(f.call('bash', { command: 'pytest' })), /equivalent failures/);

  const denied = fixture({ noProgressLimit: 2, equivalentBlockLimit: 20 });
  for (let index = 0; index < 2; index += 1) {
    const exec = denied.call('bash', { command: 'cat secret' });
    assert.equal(denied.guard(exec), undefined);
    await denied.post(exec, ok(`sandbox denied ${index}`, {
      exitCode: 1, sandbox: 'denied',
    }));
  }
  assert.match(denied.guard(denied.call('bash', { command: 'cat secret' })), /equivalent failures/);
});

test('different successful observations remain progress', async () => {
  const f = fixture({ noProgressLimit: 2, equivalentBlockLimit: 20 });
  for (const text of ['test outcome 1', 'test outcome 2', 'test outcome 3']) {
    const exec = f.call('bash', { command: 'pytest' });
    assert.equal(f.guard(exec), undefined);
    await f.post(exec, ok(text));
  }
});

test('detects an A-B-A-B cycle when executor state is unchanged', async () => {
  const f = fixture({ noProgressLimit: 20, equivalentBlockLimit: 20 });
  for (const path of ['a.txt', 'b.txt', 'a.txt', 'b.txt']) {
    const exec = f.call('read', { path });
    assert.equal(f.guard(exec), undefined);
    await f.post(exec, ok(path));
  }
  assert.match(f.guard(f.call('read', { path: 'a.txt' })), /repeated investigation cycle/);
});

test('useful mutation clears stale failure budget and permits a retest', async () => {
  const f = fixture({ noProgressLimit: 2, equivalentBlockLimit: 20 });
  const failing = f.call('bash', { command: 'pytest' });
  assert.equal(f.guard(failing), undefined);
  await f.post(failing, failure('tests failed'));
  const edit = f.call('bash', { command: 'sed -i s/old/new/ app.py' });
  assert.equal(f.guard(edit), undefined);
  await f.post(edit, ok('changed', { changed: true }));
  const retest = f.call('bash', { command: 'pytest' });
  assert.equal(f.guard(retest), undefined);
});

test('automatic turns retain anti-loop state until a human authorization arrives', async () => {
  const f = fixture({ noProgressLimit: 2, equivalentBlockLimit: 20 });
  for (const turn of [1, 2]) {
    await f.preStep(turn, 1, []);
    const exec = f.call('bash', { command: 'pytest' });
    assert.equal(f.guard(exec), undefined);
    await f.post(exec, failure('tests failed'));
  }
  await f.preStep(3, 1, []);
  assert.match(f.guard(f.call('bash', { command: 'pytest' })), /already closed|equivalent failures/);

  // A real user message is the explicit authorization boundary for a fresh
  // logical execution, even if the driver reuses the same agent and session.
  await f.preStep(4, 1, [{ source: { kind: 'user' } }]);
  assert.equal(f.guard(f.call('bash', { command: 'pytest' })), undefined);
});

test('reconnect with the same durable session reuses guard state', async () => {
  const f = fixture({ noProgressLimit: 2, equivalentBlockLimit: 20 });
  const first = f.call('bash', { command: 'pytest' });
  assert.equal(f.guard(first), undefined);
  await f.post(first, failure('tests failed'));
  const replacement = {
    session: { id: 'synthetic' },
    status: 'running',
    cancelCalls: [],
    cancel(...args) { this.cancelCalls.push(args); },
  };
  f.replaceAgent(replacement);
  const second = f.call('bash', { command: 'pytest' });
  assert.equal(f.guard(second), undefined);
  await f.post(second, failure('tests failed'));
  assert.match(f.guard(f.call('bash', { command: 'pytest' })), /equivalent failures/);
});

test('disposed durable sessions release state before a later same-id session', async () => {
  const f = fixture({ noProgressLimit: 2, equivalentBlockLimit: 20 });
  const first = f.call('bash', { command: 'pytest' });
  assert.equal(f.guard(first), undefined);
  await f.post(first, failure('tests failed'));
  f.disposeSession();
  f.replaceAgent({
    session: { id: 'synthetic' }, status: 'running', cancelCalls: [],
    cancel(...args) { this.cancelCalls.push(args); },
  });
  const fresh = f.call('bash', { command: 'pytest' });
  assert.equal(f.guard(fresh), undefined);
});

test('rejects unknown configuration keys', () => {
  assert.throws(() => fixture({ maxTurnToolCallz: 2 }), /unknown configuration key/);
});

test('hard call limit is reserved synchronously across concurrent attempts', () => {
  const f = fixture({ maxTurnToolCalls: 2, diagnosticMaxCalls: 2 });
  const first = f.call('read', { path: 'a' });
  const second = f.call('read', { path: 'b' });
  assert.equal(f.guard(first), undefined);
  assert.equal(f.guard(second), undefined);
  // A completed member of the reserved batch must not cancel its still
  // in-flight sibling merely because the batch reached its limit.
  const postFirst = f.post(first, ok('a'));
  assert.equal(f.agent.cancelCalls.length, 0);
  assert.match(f.guard(f.call('read', { path: 'c' })), /tool-call budget/);
  assert.equal(f.agent.cancelCalls.length, 1);
  return postFirst;
});

test('reported per-request usage remains monotonic when current pressure drops', async () => {
  const f = fixture({ maxTurnTokens: 100 }, { meterValues: [80, 20, 20] });
  await f.preStep();
  f.emitSession({
    type: 'assistant/message',
    data: { turn: 1, message: { content: [] }, usage: { inputTokens: 60, outputTokens: 20, totalTokens: 80 } },
  });
  f.emitSession({
    type: 'assistant/message',
    data: { turn: 1, message: { content: [] }, usage: { inputTokens: 15, outputTokens: 15, totalTokens: 30 } },
  });
  assert.match(f.guard(f.call('read', { path: 'after-compaction' })), /token budget/);
});

test('explicit zero usage does not disable the pressure fallback', async () => {
  const f = fixture({ maxTurnTokens: 50 }, { meterValues: [0, 0, 100] });
  await f.preStep();
  f.emitSession({
    type: 'assistant/message',
    data: { turn: 1, message: { content: [] }, usage: { inputTokens: 0, outputTokens: 0, totalTokens: 0 } },
  });
  assert.match(f.guard(f.call('read', { path: 'fallback' })), /token budget/);
});

test('timeout diagnostic mode cannot dispatch a mutating command', async () => {
  const f = fixture({ diagnosticMaxCalls: 2, noProgressLimit: 20 });
  const timed = f.call('bash', { command: 'sleep 10' });
  assert.equal(f.guard(timed), undefined);
  await f.post(timed, failure('BASH_TIMEOUT', { timedOut: true, durationMs: 10 }));
  assert.match(f.guard(f.call('bash', { command: 'rm -f app.py' })), /diagnostic mode/);
});

test('diagnostic admission requires explicit read-only capability metadata', async () => {
  const f = fixture({ diagnosticMaxCalls: 2, noProgressLimit: 20 });
  const timed = f.call('bash', { command: 'sleep 10' });
  assert.equal(f.guard(timed), undefined);
  await f.post(timed, failure('BASH_TIMEOUT', { timedOut: true }));
  assert.match(f.guard(f.call('read', { path: 'app.py' })), /explicit.*read-only/);
  const read = f.call('anything', { operation: 'inspect' }, { readOnly: true });
  assert.equal(f.guard(read), undefined);
});
