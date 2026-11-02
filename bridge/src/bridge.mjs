import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

export function optionsFromArgs(args) {
  const options = { port: 8765, requestTimeoutMs: 300_000 };
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i];
    const value = args[i + 1];
    if (!['--port', '--request-timeout-ms'].includes(key) || !/^\d+$/.test(value ?? '')) {
      throw new Error('Expected --port <1..65535> or --request-timeout-ms <1..1800000>.');
    }
    const number = Number(value);
    if (number < 1 || number > (key === '--port' ? 65_535 : 1_800_000)) {
      throw new Error('Port or request timeout is out of range.');
    }
    options[key === '--port' ? 'port' : 'requestTimeoutMs'] = number;
  }
  return options;
}

// Restrict every SDK request, including SSE and session teardown, to one literal
// loopback endpoint. Neither redirects nor OAuth discovery may leave it.
export function loopbackFetch(endpoint, fetchImpl = fetch) {
  return (input, init = {}) => {
    const url = new URL(input instanceof Request ? input.url : String(input));
    if (url.href !== endpoint.href) throw new Error('Only the configured Studio endpoint is allowed.');
    return fetchImpl(url, { ...init, redirect: 'error', credentials: 'omit' });
  };
}

export async function runBridge({ port, requestTimeoutMs }) {
  const endpoint = new URL(`http://127.0.0.1:${port}/mcp`);
  const local = new StdioServerTransport(process.stdin, process.stdout, { maxBufferSize: 32 * 1024 * 1024 });
  const remote = new StreamableHTTPClientTransport(endpoint, {
    fetch: loopbackFetch(endpoint),
    requestInit: { redirect: 'error' },
    // Never replay a tool request automatically. A broken session needs a fresh
    // client connection; server operations may already have taken effect.
    reconnectionOptions: { initialReconnectionDelay: 1000, maxReconnectionDelay: 1000,
      reconnectionDelayGrowFactor: 1, maxRetries: 0 },
  });
  const pending = new Map();
  let closing = false;
  let failed = false;
  let writes = Promise.resolve();
  let initializeId;
  let initialized = Promise.resolve();
  const log = text => process.stderr.write(`[augelab-mcp] ${text}\n`);
  const sendLocal = message => {
    writes = writes.then(() => local.send(message));
    return writes;
  };

  async function stop(code = 0) {
    if (closing) return;
    closing = true;
    process.exitCode = code;
    for (const timer of pending.values()) clearTimeout(timer);
    pending.clear();
    // A hung local server must not keep an orphaned bridge alive after the
    // client disconnects. DELETE ends only this connection's MCP session.
    const forceExit = setTimeout(() => process.exit(code), 2000);
    forceExit.unref();
    let teardownTimer;
    await Promise.race([
      remote.terminateSession().catch(() => {}),
      new Promise(resolve => { teardownTimer = setTimeout(resolve, 500); }),
    ]);
    clearTimeout(teardownTimer);
    await remote.close();
    await writes.catch(() => {});
    await local.close();
  }

  async function fail(id, text) {
    if (closing || failed) return;
    failed = true;
    log(text);
    // Never include an upstream body, tool arguments, resource contents or
    // exception stack in diagnostics; these can contain customer data.
    try {
      for (const requestId of pending.keys()) {
        await sendLocal({ jsonrpc: '2.0', id: requestId,
          error: { code: -32001, message: requestId === id ? text : 'Studio connection closed. Reconnect the plugin.' } });
      }
    } catch {
      // The client may have already closed stdout during a transport failure.
    } finally {
      await stop(1);
    }
  }

  remote.onmessage = message => {
    if (closing || failed) return;
    if (!('method' in message) && 'id' in message) {
      clearTimeout(pending.get(message.id));
      pending.delete(message.id);
      if (message.id === initializeId && message.result?.protocolVersion) {
        remote.setProtocolVersion(message.result.protocolVersion);
      }
    }
    sendLocal(message).catch(() => stop(1));
  };
  remote.onerror = () => {
    if (!closing) log('Studio transport error. Check Studio > Chat > Settings > MCP and reconnect if needed.');
  };
  local.onerror = () => { void fail(undefined, 'Invalid stdio input. Reconnect the plugin.'); };
  process.stdout.on('error', () => { void stop(1); });
  process.stdin.once('end', () => { void stop(); });
  process.once('SIGINT', () => { void stop(); });
  process.once('SIGTERM', () => { void stop(); });

  local.onmessage = message => {
    if (closing || failed) return;
    const isRequest = 'method' in message && 'id' in message;
    if (isRequest) {
      if (pending.has(message.id)) {
        void fail(message.id, 'Duplicate request ID. Reconnect the plugin.');
        return;
      }
      if (message.method === 'initialize') initializeId = message.id;
      pending.set(message.id, setTimeout(() => {
        void fail(message.id, 'Studio request timed out. Check operation status before retrying; reconnect the plugin.');
      }, requestTimeoutMs));
    }
    // Do not serialize tool calls behind each other: cancellation, progress,
    // and replies to Studio-initiated requests must still flow both ways.
    const forward = async () => {
      if ('method' in message) await initialized;
      if (!closing && !failed) await remote.send(message);
    };
    const sent = forward().catch(() => fail(message.id,
      `Cannot communicate with Studio on 127.0.0.1:${port}. Start its MCP server, check the active port, then reconnect the plugin.`));
    if (message.method === 'notifications/initialized') initialized = sent;
  };
  await remote.start();
  await local.start();
}
