# First setup on the user's computer

Run this workflow for a setup request or the Codex onboarding conversation.
It is part of the existing `augelab` skill. Claude Code users invoke
`/augelab:augelab Set up Studio`; clients without onboarding support can ask
`$augelab Set up Studio` in a new local chat.

## Windows x64

Explain that setup installs the official AugeLab Studio desktop application
when missing and then helps activate the user's own license. Use local shell
execution on the same Windows computer as Studio. A hosted/cloud shell cannot
install software onto the user's computer. Run the concrete command shown in
the main skill, omitting `-CheckOnly` for an authorized installation. Claude
Code resolves the skill directory in that command when loading `SKILL.md`.
For other clients, use the installed directory containing the loaded skill's
`SKILL.md`, not the user's project directory. Do not search the user profile.

The execution policy option applies to this child process only. It does not
change machine policy. If organizational policy blocks the script, explain the
block and use the official interactive installer rather than weakening policy.

The script probes the bundled local MCP address, discovers Studio in standard
locations and its uninstall registry entry, and downloads only if missing.
It verifies the pinned SHA-256 before running the AWS EXE with
`--silent --install-dir <absolute-directory> --start-menu-shortcut`. The default
destination is `%LOCALAPPDATA%\Programs\AugeLab Studio`. It starts Studio for
activation, without editing project files, licenses, or MCP settings.
An existing installation is reused, not upgraded. An unrecognized nonempty
destination requires repair or an explicitly chosen alternative directory.

Use `-CheckOnly` to inspect without downloading, installing, or launching.
Use `-DownloadOnly` to download and verify without executing. Optional
`-IncludeAI` adds the GPU/AI bundle for a requested GPU workflow after confirming
compatible NVIDIA hardware and drivers. Base setup does not install that bundle.
Do not silently substitute a Python/source installation for the Windows EXE.

Installation can take several minutes because the EXE downloads runtime
dependencies. Run it with a shell tool that can yield a session and poll that
session; keep the user informed instead of launching a second installer.
Windows may show a permission prompt for a missing VC++ runtime.

Interpret the JSON output:

- `checked`: inspection only; `changed` is false.
- `downloaded`: hash verified; `executed` is false.
- `needs-activation-or-mcp`: Studio was found or installed and launched, but
  the configured MCP endpoint is not yet ready. Continue account/license setup.
- `mcp-ready`: a Studio MCP initialization response was received. Read the
  actual Studio status and agent instructions using the client's MCP tools.

On a download or hash failure, execute nothing and report the specific error.
An updated AWS binary requires a reviewed hash update in a new plugin version;
do not replace the pin with whatever was downloaded. Installer errors are in
`%TEMP%\augelab-installer-startup.log`. Do not repeatedly reinstall on license
or MCP errors. Success requires the launcher as well as installer exit code 0.

## Linux x86-64 and ARM64

Use a local graphical Linux session on the same computer as Studio. Python 3.9+
is required for the bundled standard-library helper. Both the agent and Studio
must have access to that desktop session. A headless server, SSH-only session,
container, or remote/cloud executor is not a substitute for the desktop MCP flow.

Run the Linux command in the main skill with `--check-only` first. For an
authorized installation, omit `--check-only`. The helper selects the official
S3 `linux/installer.sh` for x86-64 or `linux_arm64/installer.sh` for ARM64, then
verifies the bundled SHA-256 pin before executing it with `bash ... --ui`.
It never executes a failed download, hash mismatch, or redirected response.
The download is cached privately under `~/.cache/augelab/plugin-setup`.

The official installer sets up `~/studio_venv`,
`~/.local/bin/augelab_studio`, and desktop entries. It handles system dependencies
through its supported package manager (apt, dnf, or pacman). Run the helper as the
desktop user, not with `sudo`; the installer may ask for sudo to install system
dependencies. If the agent cannot satisfy that interactive prompt, hand off the
official installer in a local terminal and resume after it finishes. Do not change
sudo policy or run a second installer while the first is active.

`--check-only` never downloads, installs, launches Studio, or writes files.
`--download-only` downloads and verifies without executing. `--include-ai` adds
`--ai` only on a fresh install for a requested GPU workflow with compatible NVIDIA
drivers already installed; the installer does not install NVIDIA drivers.
`--mcp-wait-seconds 0..60` controls the connection wait. Existing installations
are reused without upgrading or changing their GPU profile.

The helper discovers the standard launcher and `augelab_studio` on PATH. Use
`--launcher /absolute/path/to/augelab_studio` for an existing custom installation.
It refuses to overwrite an existing `~/studio_venv` without a usable launcher;
repair that installation rather than deleting user data or reinstalling blindly.

The same JSON status names as Windows apply: `checked`, `downloaded`,
`needs-activation-or-mcp`, and `mcp-ready`. Installer exit code zero alone is not
success: a usable launcher is also required. After launching, continue activation
and start **Chat > Settings > MCP**. Only a compatible initialization response
establishes connection readiness; use live tools to verify the actual Studio state.

On installer or hash failure, report the concrete error and execute nothing else.
Installer progress appears on stderr; the helper's final JSON is on stdout.
A changed S3 script needs a reviewed pin update in a new plugin version. Do not
replace the pin automatically or fetch an unrelated `studio` package.

## Account, license, and MCP

If the running Studio is already activated, keep that license and proceed.
Otherwise follow [account-and-license.md](account-and-license.md). When Studio
has accepted the user's key, open **Chat > Settings > MCP > Start** (using
available UI tools or user guidance), then follow [connection.md](connection.md).
Do not claim full readiness until MCP tools read the Studio status and instructions.

For the skills-only distribution, complete the separate client connection with
[client-mcp.md](client-mcp.md) after starting Studio MCP. The agent should handle
the supported client CLI/UI steps once the connection is authorized, preserve
existing settings, and give the exact manual fallback if blocked. This package
does not declare or auto-register a server during plugin installation.

Automatic installation is attached to the Codex **Run setup** onboarding step,
not an unattended plugin-install lifecycle hook. Plugins with lifecycle hooks
are ineligible for the public OpenAI directory. Older clients and Claude Code
need an explicit first setup invocation. See the official
[onboarding documentation](https://developers.openai.com/plugins/build/plugins).

## Unsupported platforms or missing local tools

macOS is not supported. Do not offer an installation path or run either helper
there. Other unrecognized operating systems or architectures are unsupported by
these helpers; report the exact limitation. If local execution or UI tools are
missing on Windows/Linux, direct the user to https://account.augelab.com for the
official installation flow and give the remaining manual steps. Do not run a
Windows EXE on Linux or pretend a remote install sets up the user's computer.
