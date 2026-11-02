import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import http from 'node:http';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import { loopbackFetch } from '../src/bridge.mjs';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const binary = process.env.AUGELAB_BRIDGE_PATH ?? fileURLToPath(new URL('../dist/augelab-mcp.mjs', import.meta.url));
const init = { jsonrpc: '2.0', id: 'init-1', method: 'initialize', params: {
  protocolVersion: '2025-03-26', capabilities: { sampling: {} }, clientInfo: { name: 'bridge-test', version: '1' },
} };
const initResult = { protocolVersion: '2025-03-26', capabilities: { tools: {}, resources: {}, prompts: {} },
  serverInfo: { name: 'Studio fixture', version: 'test' }, instructions: 'Read live Studio instructions.' };
const toolList = { tools: [{ name: 'echo', description: 'Fixture echo', inputSchema: {
  type: 'object', properties: { text: { type: 'string' } }, required: ['text'],
}, annotations: { readOnlyHint: true } }] };
const resource = { contents: [{ uri: 'augelab://studio/agent-instructions', mimeType: 'text/plain', text: 'Türkçe 🐈\nline 2' }] };

async function fixture(t, handler) {
  const seen = [];
  let events;
  const streams = new Map();
  const server = http.createServer(async (req, res) => {
    if (req.method === 'GET') {
      events = res;
      res.writeHead(200, { 'content-type': 'text/event-stream' });
      res.flushHeaders();
      return;
    }
    if (req.method === 'DELETE') { seen.push({ delete: true, headers: req.headers }); res.writeHead(200).end(); return; }
    let body = '';
    for await (const chunk of req) body += chunk;
    const msg = JSON.parse(body);
    seen.push({ msg, headers: req.headers });
    const json = result => res.writeHead(200, { 'content-type': 'application/json', 'mcp-session-id': 'test-session' })
      .end(JSON.stringify({ jsonrpc: '2.0', id: msg.id, result }));
    const sse = message => res.write(`event: message\ndata: ${JSON.stringify(message)}\n\n`);
    if (handler?.({ req, res, msg, json, sse })) return;
    if (msg.method === 'initialize') return json(initResult);
    if (msg.method === 'tools/list') return json(toolList);
    if (msg.method === 'resources/read') return json(resource);
    if (msg.method === 'prompts/list') return json({ prompts: [{ name: 'agent-instructions' }] });
    if (msg.method === 'tools/call' && msg.params.name === 'echo') {
      res.writeHead(200, { 'content-type': 'text/event-stream' });
      sse({ jsonrpc: '2.0', method: 'notifications/progress', params: { progressToken: 'p', progress: 1 } });
      sse({ jsonrpc: '2.0', id: msg.id, result: { content: [{ type: 'text', text: msg.params.arguments.text }] } });
      res.end(); return;
    }
    if (msg.method === 'tools/call' && msg.params.name === 'ask') {
      streams.set('ask', { res, id: msg.id });
      res.writeHead(200, { 'content-type': 'text/event-stream' });
      sse({ jsonrpc: '2.0', id: 'server-1', method: 'sampling/createMessage', params: { messages: [], maxTokens: 20 } });
      return;
    }
    if (msg.id === 'server-1' && msg.result) {
      const stream = streams.get('ask');
      stream.res.end(`data: ${JSON.stringify({ jsonrpc: '2.0', id: stream.id, result: { content: [msg.result.content] } })}\n\n`);
      res.writeHead(202).end(); return;
    }
    if (msg.method === 'tools/call' && msg.params.name === 'wait') {
      streams.set('wait', { res, id: msg.id });
      res.writeHead(200, { 'content-type': 'text/event-stream' });
      res.flushHeaders(); return;
    }
    if (msg.method === 'notifications/cancelled') {
      const stream = streams.get('wait');
      stream.res.end(`data: ${JSON.stringify({ jsonrpc: '2.0', id: stream.id, error: { code: -32800, message: 'Cancelled' } })}\n\n`);
    }
    if ('method' in msg && 'id' in msg) {
      res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify({
        jsonrpc: '2.0', id: msg.id, error: { code: -32601, message: 'Unknown method', data: { method: msg.method } },
      })); return;
    }
    res.writeHead(202).end();
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => { server.closeAllConnections(); server.close(); });
  return { port: server.address().port, seen, server,
    notify: msg => events.write(`data: ${JSON.stringify(msg)}\n\n`) };
}

function client(t, args) {
  const proc = spawn(process.execPath, [binary, ...args], { stdio: ['pipe', 'pipe', 'pipe'], cwd: process.env.TEMP ?? '/tmp' });
  const messages = [];
  const waiters = [];
  let stderr = '';
  const exited = once(proc, 'exit');
  proc.stderr.setEncoding('utf8').on('data', chunk => { stderr += chunk; });
  const lines = createInterface({ input: proc.stdout });
  lines.on('line', line => {
    // Every stdout line must be a JSON-RPC message, including startup/failures.
    const message = JSON.parse(line);
    assert.equal(message.jsonrpc, '2.0');
    messages.push(message);
    for (const item of [...waiters]) if (item.predicate(message)) item.resolve(message);
  });
  t.after(() => { proc.kill(); lines.close(); });
  const send = message => proc.stdin.write(JSON.stringify(message) + '\n');
  const wait = predicate => {
    const existing = messages.find(predicate);
    if (existing) return Promise.resolve(existing);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`No bridge response. ${stderr}`)), 5000);
      const item = { predicate, resolve: value => {
        clearTimeout(timer); waiters.splice(waiters.indexOf(item), 1); resolve(value);
      } };
      waiters.push(item);
    });
  };
  return { proc, messages, exited, send, wait, stderr: () => stderr,
    response: id => wait(m => !('method' in m) && m.id === id),
    async initialize() {
      send(init);
      assert.deepEqual((await wait(m => m.id === init.id)).result, initResult);
      send({ jsonrpc: '2.0', method: 'notifications/initialized' });
    } };
}

test('JSON/SSE passthrough preserves IDs, schemas, resources, prompts, errors and session headers', { timeout: 15000 }, async t => {
  const f = await fixture(t);
  const c = client(t, ['--port', String(f.port)]);
  await c.initialize();
  c.send({ jsonrpc: '2.0', id: 0, method: 'tools/list' });
  c.send({ jsonrpc: '2.0', id: 'resource', method: 'resources/read', params: { uri: 'augelab://studio/agent-instructions' } });
  c.send({ jsonrpc: '2.0', id: 'prompts', method: 'prompts/list' });
  assert.deepEqual((await c.response(0)).result, toolList);
  assert.deepEqual((await c.response('resource')).result, resource);
  assert.equal((await c.response('prompts')).result.prompts[0].name, 'agent-instructions');
  // Fragmented stdio frames and UTF-8 content survive the transport boundary.
  const wire = JSON.stringify({ jsonrpc: '2.0', id: 'echo', method: 'tools/call',
    params: { name: 'echo', arguments: { text: 'Şişe 🐈\nvideo' } } }) + '\n';
  c.proc.stdin.write(wire.slice(0, 30)); c.proc.stdin.write(wire.slice(30));
  assert.equal((await c.response('echo')).result.content[0].text, 'Şişe 🐈\nvideo');
  await c.wait(m => m.method === 'notifications/progress');
  c.send({ jsonrpc: '2.0', id: 'unknown', method: 'custom/method' });
  assert.deepEqual((await c.response('unknown')).error, { code: -32601, message: 'Unknown method', data: { method: 'custom/method' } });
  for (const { msg, headers } of f.seen.filter(item => item.msg?.method !== 'initialize')) {
    assert.equal(headers['mcp-session-id'], 'test-session');
    if (msg) assert.equal(headers['mcp-protocol-version'], '2025-03-26');
  }
  c.proc.stdin.end();
  assert.equal((await c.exited)[0], 0);
  assert.ok(f.seen.some(m => m.delete));
  assert.equal(c.stderr(), '');
});

test('server-initiated requests, client replies, cancellation and GET notifications flow concurrently', { timeout: 15000 }, async t => {
  const f = await fixture(t);
  const c = client(t, ['--port', String(f.port)]);
  await c.initialize();
  c.send({ jsonrpc: '2.0', id: 'ask', method: 'tools/call', params: { name: 'ask' } });
  await c.wait(m => m.id === 'server-1');
  c.send({ jsonrpc: '2.0', id: 'server-1', result: { content: { type: 'text', text: 'client reply' } } });
  assert.equal((await c.response('ask')).result.content[0].text, 'client reply');
  c.send({ jsonrpc: '2.0', id: 'wait', method: 'tools/call', params: { name: 'wait' } });
  // A separate request must complete while the first request is awaiting SSE.
  c.send({ jsonrpc: '2.0', id: 'parallel', method: 'tools/list' });
  await c.response('parallel');
  c.send({ jsonrpc: '2.0', method: 'notifications/cancelled', params: { requestId: 'wait', reason: 'test' } });
  assert.equal((await c.response('wait')).error.code, -32800);
  f.notify({ jsonrpc: '2.0', method: 'notifications/tools/list_changed' });
  await c.wait(m => m.method === 'notifications/tools/list_changed');
  c.proc.stdin.end();
  assert.equal((await c.exited)[0], 0);
});

test('official MCP SDK client discovers tools and reads Studio instructions through the bundled process', { timeout: 15000 }, async t => {
  const f = await fixture(t);
  const transport = new StdioClientTransport({ command: process.execPath,
    args: [binary, '--port', String(f.port)], stderr: 'pipe' });
  const sdkClient = new Client({ name: 'sdk-roundtrip', version: '1' });
  t.after(() => sdkClient.close());
  await sdkClient.connect(transport);
  assert.deepEqual(sdkClient.getServerCapabilities(), initResult.capabilities);
  assert.equal(sdkClient.getInstructions(), initResult.instructions);
  assert.deepEqual(await sdkClient.listTools(), toolList);
  assert.deepEqual(await sdkClient.readResource({ uri: 'augelab://studio/agent-instructions' }), resource);
  const result = await sdkClient.callTool({ name: 'echo', arguments: { text: 'SDK client round trip' } });
  assert.equal(result.content[0].text, 'SDK client round trip');
  await sdkClient.close();
});

test('concurrent transport failures complete each outstanding request only once', { timeout: 15000 }, async t => {
  const f = await fixture(t, ({ msg, res }) => {
    if (msg.method !== 'initialize') { res.writeHead(503).end(); return true; }
  });
  const c = client(t, ['--port', String(f.port)]);
  c.send(init); await c.response(init.id);
  for (const id of ['one', 'two', 'three']) c.send({ jsonrpc: '2.0', id, method: 'tools/list' });
  for (const id of ['one', 'two', 'three']) assert.equal((await c.response(id)).error.code, -32001);
  assert.equal((await c.exited)[0], 1);
  for (const id of ['one', 'two', 'three']) assert.equal(c.messages.filter(m => m.id === id).length, 1);
});

test('HTTP failure is sanitized, correlated and never automatically retried', { timeout: 15000 }, async t => {
  const f = await fixture(t, ({ msg, res }) => {
    if (msg.method !== 'initialize') {
      res.writeHead(500).end('SECRET-CUSTOMER-CONTENT'); return true;
    }
  });
  const c = client(t, ['--port', String(f.port)]);
  c.send(init); await c.response(init.id);
  c.send({ jsonrpc: '2.0', id: 77, method: 'tools/list' });
  assert.equal((await c.response(77)).error.code, -32001);
  assert.equal((await c.exited)[0], 1);
  assert.equal(f.seen.filter(x => x.msg?.id === 77).length, 1);
  assert.ok(!c.stderr().includes('SECRET'));
  assert.ok(!JSON.stringify(c.messages).includes('SECRET'));
});

test('unavailable Studio fails initialize with actionable stderr and a JSON-RPC error', { timeout: 15000 }, async t => {
  const f = await fixture(t);
  await new Promise(resolve => f.server.close(resolve));
  const c = client(t, ['--port', String(f.port)]);
  c.send(init);
  assert.match((await c.response(init.id)).error.message, /Start its MCP server/);
  assert.equal((await c.exited)[0], 1);
});

test('a request deadline closes the session without replaying the operation', { timeout: 15000 }, async t => {
  const f = await fixture(t);
  const c = client(t, ['--port', String(f.port), '--request-timeout-ms', '1000']);
  await c.initialize();
  c.send({ jsonrpc: '2.0', id: 'long', method: 'tools/call', params: { name: 'wait' } });
  assert.match((await c.response('long')).error.message, /Check operation status before retrying/);
  assert.equal((await c.exited)[0], 1);
  assert.equal(f.seen.filter(x => x.msg?.id === 'long').length, 1);
});

test('redirects cannot reach another endpoint', { timeout: 15000 }, async t => {
  const target = await fixture(t);
  const f = await fixture(t, ({ res }) => {
    res.writeHead(307, { location: `http://127.0.0.1:${target.port}/mcp` }).end(); return true;
  });
  const c = client(t, ['--port', String(f.port)]);
  c.send(init);
  assert.equal((await c.response(init.id)).error.code, -32001);
  assert.equal((await c.exited)[0], 1);
  assert.equal(target.seen.length, 0);
});

test('outbound endpoint restriction applies to every fetch and disables redirects', async () => {
  const endpoint = new URL('http://127.0.0.1:8765/mcp');
  const calls = [];
  const fetchLocal = loopbackFetch(endpoint, async (...args) => { calls.push(args); return new Response(); });
  for (const url of ['https://example.com/mcp', 'http://localhost:8765/mcp', 'http://127.0.0.1:8766/mcp',
    'http://127.0.0.1:8765/other', 'http://user:pass@127.0.0.1:8765/mcp']) {
    assert.throws(() => fetchLocal(url));
  }
  await fetchLocal(endpoint, { redirect: 'follow', method: 'GET' });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1].redirect, 'error');
  assert.equal(calls[0][1].credentials, 'omit');
});

test('invalid port or arbitrary URL arguments fail before protocol output', { timeout: 15000 }, async t => {
  for (const args of [['--port', '0'], ['--port', '65536'], ['--url', 'https://example.com'], ['--port']]) {
    const c = client(t, args);
    assert.equal((await c.exited)[0], 1);
    assert.equal(c.messages.length, 0);
    assert.match(c.stderr(), /Expected|out of range/);
  }
});

test('stdin EOF closes an idle bridge promptly without touching Studio', { timeout: 5000 }, async t => {
  const c = client(t, []);
  c.proc.stdin.end();
  assert.equal((await c.exited)[0], 0);
  assert.equal(c.messages.length, 0);
});
