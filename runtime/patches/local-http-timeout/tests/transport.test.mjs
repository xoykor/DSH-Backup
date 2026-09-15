import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import vm from 'node:vm';
const modules = process.env.DSH_RUNTIME_MODULES ?? '/home/x/.local/lib/dsh-runtime-0.1.5-rc.2/node_modules';
const require = createRequire(modules + '/test.cjs');
const { Agent, getGlobalDispatcher } = require('undici');
const source = readFileSync(new URL('../lib/index.js', import.meta.url), 'utf8');
const start = source.indexOf('function localProfileFetch(');
const end = source.indexOf('/** Copy profile stream knobs', start);
const context = vm.createContext({ URL, getGlobalDispatcher, fetch: globalThis.fetch });
vm.runInContext(source.slice(start, end) + ';globalThis.factory = localProfileFetch;', context);
const factory = context.factory;
const profile = baseURL => ({ baseURL, timeoutMs: 8000, streamIdleTimeoutMs: 8000 });

test('nonlocal and invalid profiles do not receive a fetch override', () => {
  for (const url of [undefined, 'invalid', 'https://example.com/v1', 'http://localhost.example.com', 'ftp://localhost']) assert.equal(factory(profile(url)), undefined);
  assert.equal(factory({ baseURL: 'http://localhost', streamIdleTimeoutMs: 0 }), undefined);
});

test('dispatch sets local deadlines, preserving body, signal and other origins', async () => {
  let observed;
  const upstream = { dispatch(options) { observed = options; return true; } };
  const c = vm.createContext({ URL, getGlobalDispatcher: () => upstream, fetch: async (input, init) => ({ input, init }) });
  vm.runInContext(source.slice(start, end) + ';globalThis.factory = localProfileFetch;', c);
  const f = c.factory(profile('http://127.0.0.1:1234/v1'));
  const signal = new AbortController().signal;
  const result = await f('http://127.0.0.1:1234/v1/responses', { method: 'POST', body: 'payload', signal });
  assert.equal(result.init.signal, signal); assert.equal(result.init.body, 'payload');
  result.init.dispatcher.dispatch({ origin: 'http://127.0.0.1:1234', headersTimeout: 300000, bodyTimeout: 300000 }, {});
  assert.equal(observed.headersTimeout, 8000); assert.equal(observed.bodyTimeout, 8000);
  result.init.dispatcher.dispatch({ origin: 'https://example.com', bodyTimeout: 300000 }, {});
  assert.equal(observed.bodyTimeout, 300000);
});

test('silent prefill fails with short transport timeout, succeeds with profile deadline, remains cancellable', async () => {
  const timers = new Set();
  const server = createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/event-stream' }); res.flushHeaders();
    const timer = setTimeout(() => { timers.delete(timer); res.end('data: ready\n\n'); }, 2000);
    timers.add(timer); res.on('close', () => { clearTimeout(timer); timers.delete(timer); });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const agent = new Agent();
  const short = { dispatch(options, handler) { return agent.dispatch({ ...options, bodyTimeout: 100 }, handler); } };
  try {
    await assert.rejects(async () => (await fetch(origin, { dispatcher: short })).text(), error => error.cause?.code === 'UND_ERR_BODY_TIMEOUT');
    const f = factory(profile(origin));
    const response = await f(origin, { dispatcher: agent });
    assert.equal(await response.text(), 'data: ready\n\n');
    const controller = new AbortController();
    const cancelled = await f(origin, { dispatcher: agent, signal: controller.signal });
    controller.abort();
    await assert.rejects(cancelled.text(), error => error.name === 'AbortError');
  } finally {
    for (const timer of timers) clearTimeout(timer);
    await agent.destroy(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
  }
});
