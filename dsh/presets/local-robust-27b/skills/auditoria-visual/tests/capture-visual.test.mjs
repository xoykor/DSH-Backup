import test from 'node:test';
import assert from 'node:assert/strict';

import {
  inspectImageBuffer,
  main,
  parseArgs,
  scopeForTarget,
  selectBackend,
} from '../scripts/capture-visual.mjs';

test('maps each request to its real capture scope', () => {
  assert.equal(scopeForTarget('active-window'), 'window');
  assert.equal(scopeForTarget('under-cursor'), 'window');
  assert.equal(scopeForTarget('current-monitor'), 'monitor');
  assert.equal(scopeForTarget('screen'), 'screen');
  assert.equal(scopeForTarget('unknown'), null);
});

test('parses the contextual capture request and keeps the evidence path bounded to cwd by default', () => {
  const options = parseArgs(['--target', 'active-window', '--reason', 'check panel overlap', '--step', 'after-fix'], '/tmp/work');
  assert.equal(options.target, 'active-window');
  assert.equal(options.reason, 'check panel overlap');
  assert.equal(options.step, 'after-fix');
  assert.equal(options.evidenceDir, '/tmp/work/.dsh/evidence/visual');
  assert.equal(options.delayMs, 250);
});

test('rejects an unknown target instead of silently widening the capture scope', () => {
  assert.throws(
    () => parseArgs(['--target', 'some-window', '--reason', 'check layout']),
    (error) => error.code === 'INVALID_TARGET',
  );
});

test('rejects empty or unsupported image bytes', () => {
  assert.throws(() => inspectImageBuffer(Buffer.alloc(0)), (error) => error.code === 'EMPTY_IMAGE');
  assert.throws(() => inspectImageBuffer(Buffer.from('not an image')), (error) => error.code === 'INVALID_IMAGE');
});

test('recognizes a non-empty PNG before handing it to the native image reader', () => {
  const png = Buffer.alloc(24);
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]).copy(png, 0);
  png.write('IHDR', 12, 4, 'ascii');
  png.writeUInt32BE(1280, 16);
  png.writeUInt32BE(720, 20);
  assert.deepEqual(inspectImageBuffer(png), { bytes: 24, mediaType: 'image/png', width: 1280, height: 720 });
});

test('does not select a screen-only backend for a window request', () => {
  const discovered = [{ definition: { name: 'screen-only', supports: new Set(['screen']) }, command: '/usr/bin/fake' }];
  assert.equal(selectBackend(discovered, 'active-window'), null);
  assert.equal(selectBackend(discovered, 'under-cursor'), null);
});

test('reports a missing graphical session without claiming capture', async () => {
  const { exitCode, result } = await main(
    ['--target', 'screen', '--reason', 'acceptance test'],
    '/tmp/work',
    { PATH: '', WAYLAND_DISPLAY: '', DISPLAY: '', MIR_SOCKET: '' },
  );
  assert.equal(exitCode, 1);
  assert.equal(result.ok, false);
  assert.equal(result.captured, false);
  assert.equal(result.error.code, 'NO_GRAPHICAL_SESSION');
  assert.equal(result.filePath, null);
});

test('disables under-cursor capture before invoking Spectacle', async () => {
  const { exitCode, result } = await main(
    ['--target', 'under-cursor', '--reason', 'avoid an interactive region selector'],
    '/tmp/work',
    { PATH: '/usr/bin:/bin', WAYLAND_DISPLAY: 'wayland-0', DISPLAY: ':0' },
  );
  assert.equal(exitCode, 1);
  assert.equal(result.captured, false);
  assert.equal(result.error.code, 'CAPTURE_TARGET_DISABLED');
  assert.equal(result.target, 'under-cursor');
});
