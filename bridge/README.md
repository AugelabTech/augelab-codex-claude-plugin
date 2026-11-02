# AugeLab local MCP bridge

This bridge is the entry point of the OpenAI desktop-only submission profile.
It forwards MCP messages between a local client's stdio connection and the
already-running Studio Streamable HTTP server at `http://127.0.0.1:8765/mcp`.
Studio supplies the capabilities, tools, schemas, prompts and resources; the
bridge does not maintain a second tool catalog.

## Runtime

- Node.js **22 or newer** on PATH in the local desktop client's environment.
  Use a currently supported LTS from https://nodejs.org/en/download . Reopen the
  client after installing Node so its environment includes the runtime.
- Activated AugeLab Studio on the same Windows x64 or graphical Linux
  x86-64/ARM64 machine, with **Chat > Settings > MCP > Start** enabled for the
  current session. Studio and its license are installed separately by the skill.
- The bundle includes its JavaScript dependencies and their license texts.
  Runtime startup uses `node`, not `npx`, `npm install`, or a network download.

The OpenAI submission ZIP launches:

```json
{
  "mcpServers": {
    "augelab-studio": {
      "type": "stdio",
      "command": "node",
      "args": ["${PLUGIN_ROOT}/server/augelab-mcp.mjs", "--port", "8765"],
      "cwd": "${PLUGIN_ROOT}"
    }
  }
}
```

The GitHub/Claude Code distribution keeps its direct HTTP configuration. The
packager substitutes `.mcp.json` only inside the separate OpenAI submission ZIP.

If Studio displays a different active port, change `--port` in a local source
copy and refresh the plugin through the client manager. Do not scan ports or
edit generated client caches. The bridge only accepts an integer port; the host
and `/mcp` path are fixed. HTTP redirects are rejected for all requests.

## Protocol and failure behavior

The bundle uses the official MCP SDK transports. It forwards initialization,
negotiated protocol versions, session headers, JSON and SSE responses, request
IDs, tools/resources/prompts, progress, cancellation and server-initiated
requests. stdout carries only newline-delimited MCP messages. Diagnostics on
stderr exclude upstream error bodies and request/response contents.

Each client connection owns one Studio MCP session. Closing stdin or receiving
SIGINT/SIGTERM attempts session deletion, aborts open streams and exits. It does
not quit Studio. A failed POST is not retried, and SSE resumption is disabled.
On connection failure, start/check Studio and reconnect through the client.
Check an operation's actual status before retrying it, since a disconnected
operation may still have run in Studio.

The request deadline is 300000 ms (five minutes), configurable with
`--request-timeout-ms <1..1800000>`. A deadline closes the connection without
replaying the request. Prefer Studio's durable-operation/status APIs for long
training or execution jobs. Large stdio frames are limited to 32 MiB; use Studio
artifact/resource references for large media instead of inline payloads.

## Build and verify from the repository

```sh
cd bridge
npm ci --ignore-scripts
npm run build
npm test
cd ..
python scripts/package.py --openai-local
python -m unittest discover -s tests -p test_submission_package.py -v
```

The generated ESM bundle needs only Node built-ins and includes five pinned
upstream packages. `THIRD_PARTY_NOTICES.txt` contains their full license texts;
`build-info.json` records input hashes, bundled versions and the bundle hash.
The packager rejects stale build inputs. Source maps, local paths, npm caches,
credentials, licenses and Studio project files are excluded from the ZIP.

Local MCP submission eligibility still requires OpenAI confirmation:
https://developers.openai.com/plugins/deploy/desktop-only . Building this ZIP
does not grant submission access or directory publication.
