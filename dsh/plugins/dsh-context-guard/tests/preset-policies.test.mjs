import test from 'node:test';
import assert from 'node:assert/strict';
import { apply } from '../lib/index.js';

const base = { economyTokens: 65536, checkpointTokens: 81920, compactTokens: 94371 };
const overrides = { maxTurnMs: null, economyTokens: 32000, checkpointTokens: 40000, compactTokens: 46080, resultFingerprintChars: 3906 };
function harness(t) {
  const events = new Map(); const pressure = new Map(); const compactions = [];
  const service = { composedPreset: ctx => ctx.preset,
    serviceFor: agent => ({ compactNow: async () => { compactions.push(agent.ctx.preset); return {}; } }) };
  const ctx = { tools: { guard() {} }, get: () => service,
    tokenMeter: { measure: session => ({ totalTokens: pressure.get(session.id) ?? 0 }) },
    compaction: { compactNow: () => { throw Error('global compactor must not handle preset'); } },
    on: (event, cb) => events.set(event, cb) };
  apply(ctx, { ...base, presetPolicies: { 'local-robust-9b': { maxTurnMs: null }, 'local-robust-27b': overrides } });
  const agents = [];
  t.after(() => agents.forEach(agent => events.get('agent/disposed')({ agent })));
  function agent(preset) {
    const cancelled = []; const steered = [];
    const a = { id: preset, ctx: { preset }, session: { id: preset }, status: 'running',
      cancel: reason => cancelled.push(reason), steer: message => steered.push(message), cancelled, steered };
    agents.push(a); return a;
  }
  async function step(a, tokens, turn = 1) {
    pressure.set(a.id, tokens);
    return events.get('agent/pre-step')({ agent: a, turn, step: 1,
      messages: turn === 1 ? [{ source: { kind: 'user' } }] : [], signal: new AbortController().signal },
    async () => ({ messages: [] }));
  }
  return { agent, step, pressure, events, compactions };
}

test('9B and 27B in the same guard receive different economy/checkpoint thresholds', async t => {
  const h = harness(t); const small = h.agent('local-robust-9b'); const large = h.agent('local-robust-27b');
  assert.equal((await h.step(small, 32000)).messages.length, 0);
  assert.match((await h.step(large, 32000)).messages[0].source.summary, /economy/);
  assert.match((await h.step(large, 40000)).messages[0].source.summary, /checkpoint/);
  assert.equal((await h.step(small, 46080)).messages.length, 0);
  assert.match((await h.step(small, 65536)).messages[0].source.summary, /economy/);
  assert.match((await h.step(small, 81920)).messages[0].source.summary, /checkpoint/);
});

test('27B compacts at 46080 through its own compactor while 9B stays active', async t => {
  const h = harness(t); const small = h.agent('local-robust-9b'); const large = h.agent('local-robust-27b');
  await h.step(small, 46080); await h.step(large, 46080);
  for (const a of [small, large]) h.events.get('session/event')(a.session, { type: 'tool/result' });
  assert.equal(small.cancelled.length, 0);
  assert.equal(large.cancelled[0].kind, 'context-guard-compaction');
  large.status = 'idle'; h.events.get('agent/status')({ agent: large, status: 'idle' });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(h.compactions, ['local-robust-27b']);
  assert.equal(large.steered.length, 1);
  h.pressure.set(small.id, 94371); h.events.get('session/event')(small.session, { type: 'tool/result' });
  assert.equal(small.cancelled[0].kind, 'context-guard-compaction');
});

test('unknown presets preserve the prior default and malformed overrides fail closed', async t => {
  const h = harness(t); const other = h.agent('unrelated');
  assert.equal((await h.step(other, 40000)).messages.length, 0);
  assert.throws(() => apply({}, { ...base, presetPolicies: { bad: { compactTokens: 1 } } }), /economyTokens/);
  assert.throws(() => apply({}, { ...base, presetPolicies: { bad: { misspelled: 1 } } }), /unknown configuration/);
});


test('robust presets survive one hour; another preset retains the existing 15-minute deadline', async t => {
  t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now: 1000000 });
  const h = harness(t);
  const small = h.agent('local-robust-9b'); const large = h.agent('local-robust-27b'); const other = h.agent('other');
  for (const a of [small, large, other]) await h.step(a, 1000);
  t.mock.timers.tick(3600000);
  for (const a of [small, large]) {
    assert.equal(a.cancelled.length, 0);
    assert.notEqual((await h.step(a, 1000, 2)).kind, 'reject');
  }
  assert.match(other.cancelled[0].reason, /total time budget of 900000ms/);
  assert.equal((await h.step(other, 1000, 2)).kind, 'reject');
});

test('disabling the turn deadline does not disable the diagnostic timeout', async t => {
  t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now: 1000000 });
  const h = harness(t); const a = h.agent('local-robust-27b'); await h.step(a, 1000);
  await h.events.get('tools/post-execute')({ agent: a, name: 'bash', arguments: { command: 'slow' } },
    { isError: true, value: { timedOut: true, exitCode: 124 } }, async () => undefined);
  t.mock.timers.tick(120001);
  assert.match(a.cancelled[0].reason, /diagnostic mode exceeded its reduced time budget/);
});
