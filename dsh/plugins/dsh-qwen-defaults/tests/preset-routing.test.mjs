import test from 'node:test';
import assert from 'node:assert/strict';
import { apply } from '../lib/index.js';

function route() {
  let request;
  apply({
    get: () => ({ composedPreset: ctx => ctx.preset }),
    on: (_event, fn) => { request = fn; },
  });
  return (preset, config) => request({ agent: { ctx: { preset } } }, async () => config);
}

test('27B preset selects Qwen and caps output without changing 9B defaults', async () => {
  const request = route();
  const original = { provider: 'lmstudio', model: 'ornith-1.5-9b', maxTokens: 24576, reasoningEffort: 'high' };
  const big = await request('local-robust-27b', original);
  assert.equal(big.model, 'qwen3.8-27b-gsq-rco');
  assert.equal(big.maxTokens, 12000);
  assert.strictEqual(await request('local-robust-9b', original), original);
  assert.equal(original.model, 'ornith-1.5-9b');
});

test('explicit lower response caps and existing routes on unrelated presets are retained', async () => {
  const request = route();
  const small = await request('local-robust-27b', { maxTokens: 4000, reasoningEffort: 'off', temperature: 0.2 });
  assert.equal(small.maxTokens, 4000); assert.equal(small.reasoningEffort, 'off'); assert.equal(small.temperature, 0.2);
  const unrelated = { provider: 'other', model: 'other', maxTokens: 32000 };
  assert.strictEqual(await request('other-preset', unrelated), unrelated);
});
