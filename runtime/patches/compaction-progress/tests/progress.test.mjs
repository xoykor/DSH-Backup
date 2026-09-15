import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import vm from 'node:vm';
import { applyPatch } from '../apply-compaction-progress.mjs';

const source = readFileSync(new URL('../lib/client.js', import.meta.url), 'utf8');
function section(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a);
  assert.ok(a >= 0 && b > a);
  return source.slice(a, b);
}
const jsx = (tag, props) => ({ tag, props });
const ctx = vm.createContext({ react_jsx_runtime: { jsx, jsxs: jsx },
  chatNode: (_ctx, kind, seq, data) => ({ kind, seq, data }),
  compactSource: e => e.type === 'user/message' && e.data.source?.plugin === 'compaction' ? e.data.source : undefined
});
vm.runInContext([
  section('function CompactionProgress(', '\n\t\t/**'),
  section('function compactSummary(', '\n\t\tfunction fallbackState$4'),
  section('function updateCompactionState(', '\n\t\t/** Slash-command'),
  section('function fallbackState$3(', '\n\t\t/**\n\t\t* Register the automatic-compaction'),
  'globalThis.api = { CompactionProgress, updateCompactionState, compactionView, compactionDefinition };'
].join('\n'), ctx);
const api = ctx.api;
const start = { event: { seq: 1, time: 100, type: 'compaction/start', data: { compactionId: 'a' } } };
const summary = { event: { seq: 2, time: 200, type: 'compaction/summary', data: { compactionId: 'a', summary: [{ type: 'text', text: 'Saved work' }], shadowedSeqs: [0], shadowedTokenCount: 40000 } } };
const checkpoint = { event: { seq: 3, time: 300, type: 'user/message', data: { source: { plugin: 'compaction', compactionId: 'a' } } } };
const end = { event: { seq: 4, time: 400, type: 'compaction/end', data: { compactionId: 'a' } } };
function fold(events) { return events.reduce((state, match) => api.updateCompactionState(state, match), {}); }
function bars(node) { return api.CompactionProgress({ node }).props.children.slice(0, 2).map(row => row.props.children[1].props); }

test('start immediately displays reading, then saving, then the expandable checkpoint', () => {
  const def = api.compactionDefinition;
  let state = def.start({}, start);
  assert.equal(def.buildViewNode({ state }).data.progressPhase, 'reading');
  let b = bars(api.compactionView(state));
  assert.equal(Object.hasOwn(b[0], 'value'), false);
  assert.equal(b[1].value, 0);
  state = def.update({ state }, summary);
  b = bars(api.compactionView(state));
  assert.equal(b[0].value, 1);
  assert.equal(Object.hasOwn(b[1], 'value'), false);
  state = def.update({ state }, checkpoint);
  assert.equal(api.compactionView(state).progressPhase, 'saving');
  state = def.update({ state }, end);
  assert.equal(api.compactionView(state).progressPhase, undefined);
  assert.equal(api.compactionView(state).summary, 'Saved work');
});

test('cancellation and persistence failure stop both bars without claiming success', () => {
  for (const middle of [[], [summary], [summary, checkpoint]]) {
    const failed = { event: { ...end.event, data: { ...end.event.data, error: 'disk unavailable' } } };
    const node = api.compactionView(fold([start, ...middle, failed]));
    assert.equal(node.progressError, 'disk unavailable');
    assert.ok(bars(node).every(bar => Object.hasOwn(bar, 'value')));
  }
});

test('replay rebuilds active and failed states; historical checkpoints remain readable', () => {
  const def = api.compactionDefinition;
  assert.equal(def.buildViewNode({ matches: [start, summary] }).data.progressPhase, 'saving');
  assert.equal(def.buildViewNode({ matches: [start, summary, checkpoint, end] }).data.summary, 'Saved work');
  assert.equal(def.buildViewNode({ matches: [summary, checkpoint] }).data.summary, 'Saved work');
  assert.equal(def.match({ ...start.event, data: { ...start.event.data, sourceCommandId: 'manual' } }), null);
});

test('installer is idempotent on approved payload and refuses unknown runtime contents', () => {
  const tmp = mkdtempSync(join(tmpdir(), 'dsh-progress-test-'));
  try {
    const target = join(tmp, 'client.js');
    writeFileSync(target, source);
    assert.equal(applyPatch({ target, check: true }).status, 'patched');
    assert.equal(applyPatch({ target }).changed, false);
    writeFileSync(target, 'external modification');
    assert.throws(() => applyPatch({ target }), /Unsupported runtime content/);
  } finally { rmSync(tmp, { recursive: true, force: true }); }
});
