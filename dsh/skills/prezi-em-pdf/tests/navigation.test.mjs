import test from 'node:test';
import assert from 'node:assert/strict';
import { captureFrames } from '../scripts/navigation.mjs';

async function run(sequence, overrides = {}) {
  let time = 0, position = 0;
  const saved = [];
  const result = await captureFrames({
    first: Buffer.from('first'), maxPages: 30, deadlineMs: 100, noChangeStreak: 5,
    now: () => time,
    next: async () => { time += 10; const frame = sequence[position++]; return frame == null ? null : Buffer.from(frame); },
    isBlank: frame => frame.toString() === 'blank',
    save: async (index, frame) => saved.push([index, frame.toString()]),
    ...overrides,
  });
  return { result, saved };
}

test('stable repeated terminal view after navigation completes and preserves frame order', async () => {
  const { result, saved } = await run(['second', 'last', 'last', 'last', 'last', 'last', 'last']);
  assert.equal(result.completed, true);
  assert.equal(result.stopReason, 'stable-viewer-terminal');
  assert.equal(result.completionEvidence, 'five-identical-frames-after-navigation');
  assert.deepEqual(saved, [[0, 'first'], [1, 'second'], [2, 'last']]);
});
test('unchanged initial viewer does not falsely complete', async () => {
  const { result } = await run(['first', 'first', 'first'], { noChangeStreak: 3 });
  assert.equal(result.completed, false);
  assert.equal(result.stopReason, 'no-navigation');
});
test('overview can recur during a Prezi path without terminating capture', async () => {
  const { result, saved } = await run(['overview-2', 'cluster-a', 'overview-3', 'cluster-b'], { maxPages: 5 });
  assert.equal(result.completed, false);
  assert.equal(result.stopReason, 'max-pages');
  assert.equal(saved.length, 5);
});
test('deadline preserves partial frames and reports incomplete', async () => {
  const { result, saved } = await run(['second', 'third', 'fourth'], { deadlineMs: 20 });
  assert.equal(result.completed, false);
  assert.equal(result.stopReason, 'deadline');
  assert.equal(saved.length, 3);
});
test('page cap is not a successful end', async () => {
  const { result } = await run(['second', 'third'], { maxPages: 2 });
  assert.equal(result.stopReason, 'max-pages');
  assert.equal(result.completed, false);
});
test('blank frames reset consecutive freeze evidence', async () => {
  const { result } = await run(['second', 'second', 'second', 'blank', 'second', null]);
  assert.equal(result.stopReason, 'empty-frame');
  assert.equal(result.completed, false);
});
test('return to overview is not sufficient evidence that navigation ended', async () => {
  const { result, saved } = await run(['second', 'first']);
  assert.equal(result.completed, false);
  assert.equal(result.stopReason, 'returned-to-start');
  assert.equal(saved.length, 2);
});
test('near-identical return to the first view is omitted while navigation continues', async () => {
  const saved = [];
  const result = await captureFrames({
    first: Buffer.from('cover'), maxPages: 10, deadlineMs: 100, noChangeStreak: 3,
    next: async index => index === 1
      ? { frame: Buffer.from('slide') }
      : index === 2
        ? { frame: Buffer.from('cover-near') }
        : { frame: Buffer.from('restart'), terminal: true },
    isDuplicate: async (frame, seen) => frame.toString() === 'cover-near'
      ? seen.findIndex(item => item.toString() === 'cover')
      : seen.findIndex(item => Buffer.compare(item, frame) === 0),
    isBlank: () => false,
    save: async (index, frame) => saved.push(frame.toString()),
  });
  assert.equal(result.completed, true);
  assert.equal(result.stopReason, 'viewer-restart');
  assert.deepEqual(saved, ['cover', 'slide']);
});
test('only an explicit disabled-next signal confirms completion', async () => {
  let terminal = false;
  const saved = [];
  const result = await captureFrames({
    first: Buffer.from('first'), maxPages: 10, deadlineMs: 100, noChangeStreak: 3,
    isTerminal: async () => terminal,
    next: async index => Buffer.from(`slide-${index}`), isBlank: () => false,
    save: async (index, frame) => { saved.push(frame.toString()); if (index === 1) terminal = true; },
  });
  assert.equal(result.completed, true);
  assert.equal(result.stopReason, 'viewer-end');
  assert.equal(result.frameCount, 2);
});
test('visible viewer restart control ends capture without saving its UI frame', async () => {
  const saved = [];
  const result = await captureFrames({
    first: Buffer.from('first'), maxPages: 10, deadlineMs: 100, noChangeStreak: 3,
    next: async index => index === 1
      ? { frame: Buffer.from('last-content'), terminal: false }
      : { frame: Buffer.from('restart-overlay'), terminal: true },
    isBlank: () => false,
    save: async (index, frame) => saved.push(frame.toString()),
  });
  assert.equal(result.completed, true);
  assert.equal(result.stopReason, 'viewer-restart');
  assert.equal(result.completionEvidence, 'viewer-restart-visible');
  assert.deepEqual(saved, ['first', 'last-content']);
});
test('browser failure propagates after previously captured frames were saved', async () => {
  const saved = [];
  await assert.rejects(captureFrames({
    first: Buffer.from('first'), maxPages: 20, deadlineMs: 100, noChangeStreak: 3,
    now: () => 0, isBlank: () => false,
    next: async () => { throw new Error('browser disconnected'); },
    save: async (index, data) => saved.push(data.toString()),
  }), /browser disconnected/);
  assert.deepEqual(saved, ['first']);
});
