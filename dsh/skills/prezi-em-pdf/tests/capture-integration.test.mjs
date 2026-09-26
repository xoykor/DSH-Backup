import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const script = fileURLToPath(new URL('../scripts/capture.mjs', import.meta.url));
const fixture = `<html><body style="margin:0;background:#b03040"><button aria-label="Present">Present</button><button class="webgl-viewer-navigation-button-next">Next</button><button id="restart" hidden>Restart</button>
<script>let step=0;document.querySelector('[aria-label=Present]').onclick=e=>e.target.remove();const restart=document.querySelector('#restart');
addEventListener('keydown',e=>{if(e.key==='ArrowRight'){step=Math.min(3,step+1);document.body.style.background=['#b03040','#3060b0','#b03041','#b03040'][step];restart.hidden=step!==3;}});</script></body></html>`;

test('real browser writes verified completion and refuses to call capped capture complete', { timeout: 60000 }, async t => {
  const root = await mkdtemp(path.join(tmpdir(), 'prezi-regression-'));
  const server = http.createServer((request, response) => {
    response.writeHead(200, { 'content-type': 'text/html' }); response.end(fixture);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); await rm(root, { recursive: true, force: true }); });
  const url = `http://127.0.0.1:${server.address().port}`;
  for (const [name, cap, expectedCode, expectedReason] of [['complete', '10', 0, 'viewer-restart'], ['partial', '2', 2, 'max-pages']]) {
    const pages = path.join(root, name, 'pages');
    const child = spawn(process.execPath, [script, url, pages], { env: {
      ...process.env, PREZI_MAX_PAGES: cap, PREZI_NOCHANGE_STREAK: '2',
      PREZI_SETTLE_POLL_MS: '20', PREZI_SETTLE_MAX_MS: '500', PREZI_DEADLINE_MS: '10000',
    }, stdio: ['ignore', 'pipe', 'pipe'] });
    let log = '';
    child.stdout.on('data', data => { log += data; }); child.stderr.on('data', data => { log += data; });
    const timeout = setTimeout(() => child.kill('SIGTERM'), 25000);
    const code = await new Promise((resolve, reject) => { child.on('error', reject); child.on('close', resolve); }).finally(() => clearTimeout(timeout));
    assert.equal(code, expectedCode, log);
    const manifest = JSON.parse(await readFile(path.join(pages, '..', 'manifest.json'), 'utf8'));
    assert.equal(manifest.completed, expectedCode === 0);
    assert.equal(manifest.stopReason, expectedReason);
    if (expectedCode === 0) assert.equal(manifest.completionEvidence, 'viewer-restart-visible');
    assert.equal(manifest.pages.length, 2);
    assert.equal((await readdir(pages)).length, manifest.pages.length);
  }
});
