# Add the separate local Studio connection

Use this workflow for the skills-only plugin after Studio installation and
license activation. The plugin supplies guidance and reviewed setup helpers;
it does not expose MCP tools automatically. The connection added here belongs
to the user's client and remains separate from the installed plugin.

## Inspect before adding

1. Use a local desktop session on the same Windows/Linux computer as Studio.
   Hosted chats and remote shells cannot reach the user's loopback server.
2. Reuse an already-loaded compatible Studio connection. If the installed
   plugin declares its own MCP server, troubleshoot that declaration instead
   of registering a second connection. Do not modify plugin cache files.
3. Open Studio's **Chat > Settings > MCP > Start** and read its active address.
   The default is `http://127.0.0.1:8765/mcp`; startup may choose another port.
   Use the displayed active port. Do not scan ports or expose Studio publicly.
4. Identify the current agent client and inspect its existing entry before
   changing settings. Explain that connecting grants that client access to
   Studio's advertised tools and resources. Obtain any required client/user
   approval for this concrete connection. A skill invocation alone must not be
   treated as permission to broaden unrelated access or disable tool approvals.

## Codex desktop / local Codex

If the Codex CLI is available, inspect the proposed name:

```sh
codex mcp get augelab-studio --json
```

If it already points to the intended Studio server, reuse it. If that name is
occupied by another configuration, preserve it and resolve the conflict with
the user; do not run `add` over an existing entry. Treat unexpected inspection
errors as errors, not proof that the entry is absent. Check disabled or
workspace-managed entries without enabling/overriding them silently.

For an absent entry, after the local connection is authorized:

```sh
codex mcp add augelab-studio --url http://127.0.0.1:8765/mcp
codex mcp get augelab-studio --json
```

Substitute only the confirmed active port. This writes user-level Codex MCP
configuration. Use the CLI rather than replacing `config.toml`; preserve model,
effort, installed plugins, other MCP entries and per-tool approval settings.
If the CLI is missing, use the client's MCP settings UI to add the displayed
Streamable HTTP address. Do not install an unrelated CLI or guess config keys.

Reconnect through the client's available MCP controls. If the running chat does
not reload newly configured tools, explain that a new local chat or client
restart is needed, then resume there. Do not restart the user's other tasks.

## Claude Code

Inspect the existing name first:

```sh
claude mcp get augelab-studio
```

Reuse the matching entry; preserve conflicts as above. For an absent entry,
the default local scope keeps the setting private to the current project:

```sh
claude mcp add --transport http --scope local augelab-studio http://127.0.0.1:8765/mcp
claude mcp get augelab-studio
```

Use `--scope user` only if the user wants this Studio connection available in
all their projects. Do not write a shared project `.mcp.json` unless requested.
Use `/mcp` to check/reconnect; start a new session when needed. These commands
target Claude Code, not Claude Desktop's separate configuration.

## Verify and recover

Read the actual Studio status and `augelab://studio/agent-instructions` using
the connected client's MCP tools; use the advertised instructions prompt if
resource access is unavailable. Only then use the live schemas to create/edit
or run an authorized computer vision project.

Keep these outcomes separate: Studio installed, license activated, server
running, client configuration saved, and tools connected. If permissions, local
execution, CLI/UI access or hot reload are unavailable, report the exact
remaining action and provide the matching manual command/settings steps.
Do not claim the plugin alone has connected Studio or bypass a client or
organization policy. On a port change, resolve the saved connection deliberately
instead of creating duplicate entries. Uninstalling this skills-only plugin does
not remove the independent MCP entry; use the client manager to remove that
entry only if the user asks.

Official client references:
- https://learn.chatgpt.com/docs/extend/mcp
- https://code.claude.com/docs/en/mcp
