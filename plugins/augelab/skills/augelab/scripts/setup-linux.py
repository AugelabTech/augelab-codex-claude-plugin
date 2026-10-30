#!/usr/bin/env python3
"""Set up the official Linux desktop installer. Requires Python 3.9+ (stdlib only)."""

import argparse
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ENDPOINT = "http://127.0.0.1:8765/mcp"
INSTALLER_HOST = "studio-desktop-application.s3.eu-central-1.amazonaws.com"
MAX_BYTES = 2 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def installer_config():
    architecture = {"amd64": "x86_64", "arm64": "aarch64"}.get(
        platform.machine().lower(), platform.machine().lower())
    paths = {"x86_64": "linux", "aarch64": "linux_arm64"}
    if platform.system() != "Linux" or architecture not in paths:
        raise ValueError("Setup requires Linux x86-64 or ARM64. macOS is not supported.")
    configs = json.loads(Path(__file__).with_name("linux-installers.json").read_text(encoding="utf-8"))
    config = configs[architecture]
    expected_url = f"https://{INSTALLER_HOST}/{paths[architecture]}/installer.sh"
    if config["url"] != expected_url or not re.fullmatch(r"[a-f0-9]{64}", config["sha256"]):
        raise ValueError("Invalid pinned official Linux installer configuration.")
    return config


def verify_hash(path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Installer SHA-256 mismatch. Nothing was executed; update the reviewed plugin pin.")


def save_installer(config, home):
    cache = home / ".cache/augelab/plugin-setup"
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = cache / ("installer-" + config["sha256"] + ".sh")
    if destination.is_symlink():
        raise ValueError("The installer cache file must not be a symbolic link.")
    if destination.exists():
        verify_hash(destination, config["sha256"])
        return destination
    opener = urllib.request.build_opener(NoRedirect())
    print("Downloading the official AugeLab Studio Linux installer...", file=sys.stderr)
    with opener.open(config["url"], timeout=60) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Unexpected installer size; nothing was executed.")
    # Write to a private staging file, then verify before publishing the cache entry.
    descriptor, name = tempfile.mkstemp(prefix="installer-", suffix=".partial", dir=cache)
    partial = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        verify_hash(partial, config["sha256"])
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)
    return destination


def is_initialize_result(value):
    result = value.get("result", {})
    return (value.get("id") == 1 and bool(result.get("protocolVersion")) and
            re.search(r"augelab|studio", result.get("serverInfo", {}).get("name", ""), re.I) is not None)


def mcp_ready():
    # Never send loopback traffic through an environment-configured HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "augelab-plugin-setup", "version": "0.1.5"}}}
    request = urllib.request.Request(ENDPOINT, json.dumps(payload).encode(), headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    session = None
    try:
        with opener.open(request, timeout=2) as response:
            session = response.headers.get("Mcp-Session-Id")
            if response.headers.get_content_type() != "text/event-stream":
                return is_initialize_result(json.loads(response.read(MAX_BYTES)))
            total = 0
            event = []
            while total < MAX_BYTES:
                line = response.readline(MAX_BYTES - total + 1)
                total += len(line)
                if not line or total > MAX_BYTES:
                    return False
                if line.startswith(b"data:"):
                    event.append(line[5:].strip())
                elif not line.strip() and event:
                    value = json.loads(b"\n".join(event))
                    if value.get("id") == 1:
                        return is_initialize_result(value)
                    event = []
        return False
    except (OSError, HTTPException, ValueError, TypeError, AttributeError):
        return False
    finally:
        if session:
            cleanup = urllib.request.Request(ENDPOINT, method="DELETE", headers={"Mcp-Session-Id": session})
            try:
                with opener.open(cleanup, timeout=2):
                    pass
            except (OSError, HTTPException, ValueError):
                pass


def find_launcher(home, requested=None):
    candidates = [Path(requested)] if requested else [
        home / ".local/bin/augelab_studio", Path(shutil.which("augelab_studio") or "/nonexistent")]
    return next((path for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)


def studio_running(home):
    # The official launcher execs this interpreter with Studio's UI on stdin.
    interpreter = os.fsencode(str(home / "studio_venv/bin/python"))
    for process in Path("/proc").glob("[0-9]*"):
        try:
            if process.stat().st_uid != os.getuid():
                continue
            command = (process / "cmdline").read_bytes().split(b"\0")
            if command[:2] == [interpreter, b"-"]:
                return True
        except (OSError, ProcessLookupError):
            continue
    return False


def setup(args):
    config = installer_config()
    home = Path.home()
    if args.launcher and not Path(args.launcher).is_absolute():
        raise ValueError("--launcher must be an absolute path to an existing Studio launcher.")
    if args.download_only:
        return {"status": "downloaded", "installer": str(save_installer(config, home)), "executed": False}
    launcher = find_launcher(home, args.launcher)
    ready = mcp_ready()
    if args.check_only:
        return {"status": "checked", "executable": str(launcher) if launcher else None,
                "mcpReady": ready, "changed": False}
    if ready:
        return {"status": "mcp-ready", "installedNow": False, "mcpReady": True}
    if os.geteuid() == 0:
        raise ValueError("Run setup as the desktop user, not root. The official installer requests sudo for system dependencies.")
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise ValueError("A local Linux graphical desktop session is required for Studio activation and MCP. Headless/remote setup is not supported here.")
    if args.launcher and not launcher:
        raise ValueError("The requested Studio launcher is missing or not executable; repair that installation first.")
    installed = False
    if not launcher:
        # The vendor installer always uses this location; do not overwrite an unknown venv.
        if (home / "studio_venv").exists() or (home / ".local/bin/augelab_studio").exists():
            raise ValueError("A Studio destination already exists without a usable launcher; repair it before setup.")
        bash = shutil.which("bash")
        if not bash:
            raise ValueError("The official Linux installer requires bash.")
        installer = save_installer(config, home)
        verify_hash(installer, config["sha256"])
        command = [bash, str(installer), "--ui"]
        if args.include_ai:
            command.append("--ai")
        print("Installing Studio; the official installer may request sudo for system dependencies.", file=sys.stderr)
        subprocess.run(command, check=True, stdout=sys.stderr, stderr=sys.stderr)
        launcher = find_launcher(home)
        if not launcher:
            raise ValueError("Installer returned success but the Studio launcher is missing; setup is incomplete.")
        installed = True
    if not studio_running(home):
        subprocess.Popen([str(launcher)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + args.mcp_wait_seconds
    while True:
        ready = mcp_ready()
        if ready or time.monotonic() >= deadline:
            break
        time.sleep(2)
    return {"status": "mcp-ready" if ready else "needs-activation-or-mcp", "executable": str(launcher),
            "installedNow": installed, "mcpReady": ready}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check-only", action="store_true", help="Inspect only; no download, install, launch, or file changes.")
    modes.add_argument("--download-only", action="store_true", help="Download and verify without executing.")
    parser.add_argument("--include-ai", action="store_true", help="Include the requested GPU/AI profile on a fresh install.")
    parser.add_argument("--launcher", help="Absolute path to an existing custom Studio launcher.")
    parser.add_argument("--mcp-wait-seconds", type=int, choices=range(61), default=20, metavar="0..60")
    return parser.parse_args(argv)


def main():
    try:
        print(json.dumps(setup(parse_args())))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("Setup failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
