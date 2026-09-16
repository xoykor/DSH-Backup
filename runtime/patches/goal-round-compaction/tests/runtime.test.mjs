import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(root, '../manifest.json'), 'utf8'));
const payload = readFileSync(join(root, '../lib/index.js'));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');

test('runtime payload is the approved goal-round compaction patch', () => {
  assert.equal(hash(payload), manifest.patchedSha256);
  const source = payload.toString('utf8');
  assert.match(source, /isTransientCompactionRejection/);
  assert.match(source, /isCompactionAbort/);
  assert.match(source, /wasCompactionPaused/);
  assert.match(source, /retryAfterCompaction/);
  assert.match(source, /goal\.activation === "disarmed"/);
  assert.match(source, /requestDrive\(state\);/);
  assert.match(source, /code: "prompt-rejected"/);
});
