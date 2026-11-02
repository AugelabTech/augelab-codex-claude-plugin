# OpenAI desktop-only submission

The preparation profile is `dist/augelab-openai-local-0.1.6.zip`. It contains the
same AugeLab computer vision/AI metadata, logo, single shared skill and Studio
setup helpers as the GitHub package, plus a standalone local MCP bridge and
upstream license notices. Its `.mcp.json` launches `node` with a `${PLUGIN_ROOT}`
path; the bridge connects only to the configured Studio loopback port.

## Build and inspect

1. Follow the build commands in [the bridge guide](../bridge/README.md). The
   build uses the committed lockfile. The packager rejects stale bridge inputs
   and creates reproducible archives using explicit file allowlists.
2. Verify `dist/SHA256SUMS.txt` and inspect the separate submission ZIP. It must
   contain `server/augelab-mcp.mjs`, `server/THIRD_PARTY_NOTICES.txt`,
   `server/build-info.json` and `server/README.md`, with a stdio `.mcp.json`.
   The ordinary GitHub ZIP continues to declare the local HTTP endpoint.
3. Extract the submission ZIP into a clean directory. With Node.js 22+ and a
   local stdio MCP client, initialize the server, discover tools, read
   `augelab://studio/agent-instructions` and run an authorized sample workflow.
   Complete the [desktop smoke test](smoke-test.md), including first setup.
4. Review install-surface copy: Windows x64 / graphical Linux x86-64 or ARM64,
   Node.js 22+, separately installed Studio and a valid Studio license. Avoid
   implying that plugin installation itself provides a license.

## Submit through the approved local flow

The [official OpenAI desktop-only guide](https://developers.openai.com/plugins/deploy/desktop-only)
requires eligibility confirmation and organization allowlisting before local
MCP submission. A business identity verification is a separate prerequisite.

After OpenAI confirms access, create a fresh plugin using the documented local
submission path (the guide labels it Create plugin / Skills only; portal labels
may change) and upload the complete ZIP including its local MCP configuration.
Keep the package name `augelab` and display name AugeLab. Confirm that the portal
recognizes desktop execution and the local MCP before submitting for review.
Publish only after review approval.

Do not use a fabricated remote HTTPS endpoint, omit the declared MCP to bypass
checks, or reuse an unrelated legacy app ID as the package name. The bridge is
a technical submission candidate; its use of a separately installed licensed
Studio app remains subject to OpenAI's architecture and eligibility review.

Maintain organization IDs, support correspondence and test evidence in private
submission records, outside public plugin archives. Use a company support
contact in the portal's required support field; no personal mailbox is bundled.
