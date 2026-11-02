# AugeLab 0.1.6 beta

Build computer vision and AI workflows with AugeLab Studio through one shared
Codex/Claude Code skill.

- Adds a standalone stdio-to-Studio MCP bridge for the OpenAI desktop-only
  package, including pinned JavaScript dependencies and full license notices.
- Preserves Studio tool discovery, resources, prompts, progress, cancellation
  and bidirectional MCP communication. Connections stay on the configured
  loopback port and do not follow redirects or replay failed operations.
- Adds reproducible submission packaging, build provenance, archive validation
  and Windows/Linux CI coverage for the bridge.
- Adds public support and policy links and a concise computer vision/AI subtitle.
- Adds an independent skills-only AugeLab Setup profile. Its first setup guides
  a separate local client MCP connection with user authorization and preserves
  existing settings.

## Downloads

- `augelab-0.1.6.zip`: plugin package with direct local HTTP MCP.
- `augelab-marketplace-0.1.6.zip`: Codex/Claude Code catalogs, plugin and guides.
- `augelab-openai-local-0.1.6.zip`: desktop-only stdio package; requires Node.js
  22+ on the user's PATH. Dependencies are bundled; startup does not use npm.
- `augelab-openai-skills-only-0.1.6.zip`: AugeLab Setup skill with no declared MCP
  server; first setup helps add the independent local client connection. Local
  shell/settings access and reconnect may be needed.
- `SHA256SUMS.txt`: SHA-256 checksums for the generated archives.

All profiles require a separately installed and activated AugeLab Studio on
Windows x64 or graphical Linux x86-64/ARM64, with its MCP server started. macOS
is unsupported. The shared setup skill helps install Studio and activate the
user's own license.

OpenAI directory distribution requires separate local-MCP eligibility and review.
This GitHub release does not itself provide an official directory listing.
