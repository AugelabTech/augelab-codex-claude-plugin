# AugeLab for Codex and Claude Code

Build computer vision and AI workflows with AugeLab Studio, from image processing
and visual inspection to model training. One shared skill connects Codex and
Claude Code to the running Studio's tools through its local MCP server.

**0.1.6 beta:** A separate OpenAI desktop-only package bundles a stdio-to-Studio
bridge. GitHub installations retain their direct HTTP connection.
Setup on Windows and Linux downloads and installs Studio when missing, then
helps register an account, confirm email, and activate the user's license.
[Türkçe kurulum](README.tr.md).

## Prerequisites

- A local Codex or Claude Code session on the same computer as Studio.
- Supported desktop targets: **Windows x64** and **Linux x86-64/ARM64**.
- First setup downloads and verifies the official installer for your platform.
- Linux setup requires Python 3.9+, bash, and a graphical desktop session.
- **macOS is not supported.**
- A valid Studio license. Setup helps obtain and activate the user's own key;
  installing the plugin does not grant a license.
- Once activated, start Studio's server: **Chat > Settings > MCP > Start**.
- The default endpoint is `http://127.0.0.1:8765/mcp`.
- This plugin does not include Studio, a Studio license, or Studio dependencies.

## Install from GitHub

Install from `AugelabTech/augelab-codex-claude-plugin`:

### Codex

```sh
codex plugin marketplace add AugelabTech/augelab-codex-claude-plugin
codex plugin add augelab@augelab-plugins
```

Select **Run setup** when offered after installation. The existing `augelab`
skill is the onboarding entry point. On older clients, open a new local chat:

> $augelab Set up Studio on this computer, install it if missing, and help activate my license using my connected Gmail or Outlook account.

### Claude Code

Run these commands inside Claude Code:

```text
/plugin marketplace add AugelabTech/augelab-codex-claude-plugin
/plugin install augelab@augelab-plugins
```

Start a new session and invoke `/augelab:augelab Set up Studio on this computer`,
or ask Claude to use AugeLab and complete setup.
This configuration targets **Claude Code**, not the separate Claude Desktop chat
configuration file. Claude discovers the plugin's shared `.mcp.json` and `skills/`.

## First setup and activation

The agent selects the bundled setup helper for the local operating system. If
Studio is missing, it downloads the official installer from AugeLab's public S3
bucket, checks the pinned SHA-256, and installs the desktop application:

- **Windows x64:** the EXE installs into `%LOCALAPPDATA%\Programs\AugeLab Studio`.
- **Linux x86-64/ARM64:** the matching shell installer runs in UI mode, creates
  `~/studio_venv` and `~/.local/bin/augelab_studio`, and adds desktop entries.
  Run as the desktop user; the installer may request sudo for system dependencies.

Existing installations are reused. Base setup omits the optional GPU/AI bundle;
it can be added for a requested workflow with compatible NVIDIA drivers installed.
Linux requires a graphical session for activation and Studio's MCP server;
a headless-only runtime does not replace this desktop connection.

For license activation, the agent uses the official [account site](https://account.augelab.com).
It can use authorized Gmail/Outlook tools to identify the chosen address and
find the registration confirmation or license email, then enter the user's key
in Studio. Email connectors and browser/desktop tools are optional client
capabilities, not bundled services. The user completes required sign-in,
password, terms, CAPTCHA, or MFA steps. If tools or account entitlements are
missing, the agent explains the exact remaining manual steps. Keys stay out of
chat, logs, and repository files.

Automatic download runs in the setup conversation, not immediately upon plugin
installation. Clients without onboarding support need the setup prompt above.
The package does not use lifecycle hooks. See the detailed
[setup](plugins/augelab/skills/augelab/references/setup.md) and
[activation](plugins/augelab/skills/augelab/references/account-and-license.md) workflows.

## Install from a local folder or ZIP

Extract the marketplace ZIP first. From the extracted root:

```sh
codex plugin marketplace add .
codex plugin add augelab@augelab-plugins
```

For Claude Code, from that directory:

```sh
claude plugin marketplace add .
claude plugin install augelab@augelab-plugins
```

## Connection troubleshooting

Check the **active address** shown in Studio. Enabling startup alone does not start
the current MCP server. If the configured port is occupied, Studio may start on
the next port.

For a custom port, use a local checkout and change `plugins/augelab/.mcp.json` to
the displayed loopback address. Keep the connection local. Reinstall through the
client's plugin manager and start a new chat; do not edit generated cache files.
Do not add both a Git-backed and a local marketplace with the same name: choose
one source. Removing a marketplace does not remove the source files.

For updates to a Git-backed installation:

```sh
codex plugin marketplace upgrade augelab-plugins
codex plugin add augelab@augelab-plugins
```

In Claude Code use `/plugin marketplace update augelab-plugins`, then
`/plugin update augelab@augelab-plugins`. Restart the client session afterward.

## Validate and package

Python 3.12+, standard library only:

```sh
python scripts/package.py
```

For the separate OpenAI local-MCP submission package, Node.js 22+ is also required
at build time and on the user's desktop. Build dependencies are pinned in
`bridge/package-lock.json`; their JavaScript code and license texts are included
in the resulting ZIP, so startup does not use npm or download code:

```sh
cd bridge
npm ci --ignore-scripts
npm run build
npm test
cd ..
python scripts/package.py --openai-local
python -m unittest discover -s tests -p test_submission_package.py -v
```

See [bridge runtime and protocol behavior](bridge/README.md) and the
[submission checklist](docs/openai-local-submission.md). OpenAI must confirm
organization eligibility before the ZIP is submitted to its public directory.

Windows setup regression tests (no real installation or mailbox access):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/setup-windows.tests.ps1
```

Linux setup regression tests (standard library; no real installation or external network):

```sh
python3 -m unittest discover -s tests -p test_setup_linux.py -v
```

Outputs:

- `dist/augelab-0.1.6.zip`: plugin root, including both hidden client manifests.
- `dist/augelab-marketplace-0.1.6.zip`: both catalogs, plugin, and installation docs.
- `dist/augelab-openai-local-0.1.6.zip`: generated with `--openai-local`; uses the
  bundled stdio bridge and requires a local Node.js 22+ runtime.
- `dist/SHA256SUMS.txt`: archive checksums.

The packager uses explicit file allowlists and validates archive contents.
GitHub Actions runs the same command on pushes and pull requests. Package checks
do not replace the [desktop smoke test](docs/smoke-test.md).

## What is included

```text
.agents/plugins/marketplace.json       Codex catalog
.claude-plugin/marketplace.json        Claude Code catalog
plugins/augelab/
  .codex-plugin/plugin.json            Codex metadata
  .claude-plugin/plugin.json           Claude Code metadata
  .mcp.json                           Shared local MCP connection
  skills/augelab/SKILL.md              One shared entry-point skill
  skills/augelab/scripts/              Windows/Linux setup and reviewed download pins
  skills/augelab/references/           Setup, account/license, and MCP guidance
bridge/                               Stdio bridge source, lockfile, build and tests
```

This repository contains the plugin only, not the proprietary Studio source.
GitHub distribution does not imply listing in either vendor's official directory.

## Report an issue

Include the client and Studio versions, OS, installation method, and a redacted
error message. Do not attach credentials, license files, customer images, or
private project files. For connection errors, include the port, not private logs.

## References

- [Codex plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Claude Code marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Claude Code plugin manifests](https://code.claude.com/docs/en/plugins-reference)
