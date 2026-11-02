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

## Downloads

- `augelab-0.1.6.zip`: plugin package with direct local HTTP MCP.
- `augelab-marketplace-0.1.6.zip`: Codex/Claude Code catalogs, plugin and guides.
- `augelab-openai-local-0.1.6.zip`: desktop-only stdio package; requires Node.js
  22+ on the user's PATH. Dependencies are bundled; startup does not use npm.
- `SHA256SUMS.txt`: SHA-256 checksums for these three archives.

All profiles require a separately installed and activated AugeLab Studio on
Windows x64 or graphical Linux x86-64/ARM64, with its MCP server started. macOS
is unsupported. The shared setup skill helps install Studio and activate the
user's own license.

OpenAI directory distribution requires separate local-MCP eligibility and review.
This GitHub release does not itself provide an official directory listing.
