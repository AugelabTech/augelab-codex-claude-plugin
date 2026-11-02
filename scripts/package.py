"""Validate and build the public plugin packages from explicit file allowlists."""

from __future__ import annotations

import hashlib
import argparse
import json
import re
import struct
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "augelab"
PLUGIN_FILES = (
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    ".mcp.json",
    "assets/augelab.png",
    "skills/augelab/SKILL.md",
    "skills/augelab/agents/openai.yaml",
    "skills/augelab/assets/augelab.png",
    "skills/augelab/references/connection.md",
    "skills/augelab/references/setup.md",
    "skills/augelab/references/account-and-license.md",
    "skills/augelab/scripts/setup-windows.ps1",
    "skills/augelab/scripts/windows-installer.json",
    "skills/augelab/scripts/setup-linux.py",
    "skills/augelab/scripts/linux-installers.json",
)
MARKETPLACE_FILES = (
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
    "README.md",
    "README.tr.md",
    "docs/smoke-test.md",
    "docs/openai-local-submission.md",
    "bridge/README.md",
)
BRIDGE = ROOT / "bridge"
BRIDGE_FILES = ("augelab-mcp.mjs", "THIRD_PARTY_NOTICES.txt", "build-info.json")


def content(source: Path | bytes) -> bytes:
    return source if isinstance(source, bytes) else source.read_bytes()


def validate_bridge(version: str) -> None:
    info = read_json(BRIDGE / "dist/build-info.json")
    require(info["version"] == version == read_json(BRIDGE / "package.json")["version"],
            "Bridge and plugin versions differ")
    require(info["node"] == ">=22", "Unexpected bridge runtime")
    require(set(info["inputs"]) == {"package.json", "package-lock.json", "build.mjs",
                                   "src/index.mjs", "src/bridge.mjs"}, "Unexpected bridge input inventory")
    for name, digest in info["inputs"].items():
        require(hashlib.sha256((BRIDGE / name).read_bytes()).hexdigest() == digest,
                f"Bridge build is stale: {name}. Run npm run build in bridge/.")
    require(hashlib.sha256((BRIDGE / "dist/augelab-mcp.mjs").read_bytes()).hexdigest() ==
            info["bundleSha256"], "Bridge bundle hash mismatch")
    require(bool(info["dependencies"]), "Bundled dependency inventory is missing")
    for name in BRIDGE_FILES:
        require((BRIDGE / "dist" / name).is_file() and not (BRIDGE / "dist" / name).is_symlink(),
                f"Missing bridge build output: {name}")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate() -> str:
    codex = read_json(PLUGIN / ".codex-plugin/plugin.json")
    claude = read_json(PLUGIN / ".claude-plugin/plugin.json")
    version = codex["version"]
    require(bool(re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?", version)), "Invalid version")
    require(codex["name"] == claude["name"] == "augelab", "Plugin names differ")
    require(claude["version"] == version, "Plugin versions differ")
    require(codex["skills"] == "./skills/", "Unexpected skills path")
    require(codex["mcpServers"] == "./.mcp.json", "Unexpected MCP path")
    require(codex["requires_local_executor"] is True, "Desktop execution must be declared")
    interface = codex["interface"]
    for field in ("displayName", "shortDescription"):
        require(isinstance(interface.get(field), str) and 0 < len(interface[field]) <= 30,
                f"{field} must be 1..30 characters for public submission")
    for field in ("websiteURL", "supportURL", "privacyPolicyURL", "termsOfServiceURL"):
        url = interface.get(field, "")
        parsed = urlsplit(url)
        require(isinstance(url, str) and 0 < len(url) <= 1024 and parsed.scheme == "https"
                and bool(parsed.hostname) and parsed.username is None and parsed.password is None,
                f"{field} must be an HTTPS URL without credentials")
    require(codex["extensions"]["com.openai"]["onboardingSkill"] ==
            "./skills/augelab/SKILL.md", "Setup must reuse the shared skill")
    installer = read_json(PLUGIN / "skills/augelab/scripts/windows-installer.json")
    require(installer["url"] == "https://studio-desktop-application.s3.eu-central-1.amazonaws.com/AugeLab%20Ai%20Studio.exe",
            "Unexpected installer source")
    require(bool(re.fullmatch(r"[a-f0-9]{64}", installer["sha256"])), "Invalid installer pin")
    linux_installers = read_json(PLUGIN / "skills/augelab/scripts/linux-installers.json")
    require(set(linux_installers) == {"x86_64", "aarch64"}, "Expected Linux x86-64 and ARM64 installers")
    for architecture, directory in (("x86_64", "linux"), ("aarch64", "linux_arm64")):
        entry = linux_installers[architecture]
        require(entry["url"] ==
                f"https://studio-desktop-application.s3.eu-central-1.amazonaws.com/{directory}/installer.sh",
                "Unexpected Linux installer source")
        require(bool(re.fullmatch(r"[a-f0-9]{64}", entry["sha256"])), "Invalid Linux installer pin")
    for field in ("logo", "composerIcon"):
        require(codex["interface"].get(field) == "./assets/augelab.png", f"Missing AugeLab {field}")
    logo = (PLUGIN / "assets/augelab.png").read_bytes()
    require(logo[:8] == b"\x89PNG\r\n\x1a\n" and logo[12:16] == b"IHDR", "Invalid logo PNG")
    width, height = struct.unpack(">II", logo[16:24])
    require(48 <= width == height <= 4096 and len(logo) <= 5 * 1024 * 1024, "Invalid logo dimensions or size")
    require(logo == (PLUGIN / "skills/augelab/assets/augelab.png").read_bytes(), "Skill and plugin logos differ")
    servers = read_json(PLUGIN / ".mcp.json")["mcpServers"]
    require(list(servers) == ["augelab-studio"], "Expected exactly one Studio MCP server")
    require(servers["augelab-studio"] == {
        "type": "http", "url": "http://127.0.0.1:8765/mcp"
    }, "Release package must use the documented local endpoint")
    for path, is_codex in ((".agents/plugins/marketplace.json", True), (".claude-plugin/marketplace.json", False)):
        catalog = read_json(ROOT / path)
        require(catalog["name"] == "augelab-plugins", "Marketplace names differ")
        require(len(catalog["plugins"]) == 1, "Expected one plugin per marketplace")
        entry = catalog["plugins"][0]
        require(entry["name"] == "augelab", "Unexpected catalog entry")
        source = entry["source"]["path"] if is_codex else entry["source"]
        require(source == "./plugins/augelab", "Invalid marketplace source")
    skills = list((PLUGIN / "skills").glob("*/SKILL.md"))
    require(skills == [PLUGIN / "skills/augelab/SKILL.md"], "Expected exactly one skill")
    skill = skills[0].read_text(encoding="utf-8")
    require(skill.startswith("---\nname: augelab\ndescription: "), "Invalid skill frontmatter")
    require("\n---\n" in skill[4:], "Unclosed skill frontmatter")
    require("references/connection.md" in skill, "Connection guidance is unreachable")
    for path in [*(PLUGIN / p for p in PLUGIN_FILES), *(ROOT / p for p in MARKETPLACE_FILES)]:
        require(path.is_file() and not path.is_symlink(), f"Missing or linked file: {path}")
        require(bool(path.read_bytes()), f"Empty file: {path}")
    actual = {p.relative_to(PLUGIN).as_posix() for p in PLUGIN.rglob("*") if p.is_file()}
    require(actual == set(PLUGIN_FILES), "Plugin file inventory differs from release allowlist")
    return version


def write_archive(path: Path, files: list[tuple[Path | bytes, str]]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, name in sorted(files, key=lambda pair: pair[1]):
            # Fixed metadata makes identical source files produce identical ZIPs.
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content(source))
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, "ZIP integrity check failed")
        require(set(archive.namelist()) == {name for _, name in files}, "ZIP inventory mismatch")
        for source, name in files:
            require(archive.read(name) == content(source), f"ZIP content mismatch: {name}")


def openai_files(version: str) -> list[tuple[Path | bytes, str]]:
    validate_bridge(version)
    servers = {"mcpServers": {"augelab-studio": {
        "type": "stdio", "command": "node",
        "args": ["${PLUGIN_ROOT}/server/augelab-mcp.mjs", "--port", "8765"],
        "cwd": "${PLUGIN_ROOT}",
    }}}
    codex = read_json(PLUGIN / ".codex-plugin/plugin.json")
    codex["interface"]["longDescription"] += (
        " This desktop-only package also requires Node.js 22+ on PATH to run its bundled local MCP bridge."
    )
    files = [(PLUGIN / name, name) for name in PLUGIN_FILES
             if name not in {".mcp.json", ".codex-plugin/plugin.json"}]
    files.append(((json.dumps(codex, indent=2) + "\n").encode("utf-8"), ".codex-plugin/plugin.json"))
    files.append(((json.dumps(servers, indent=2) + "\n").encode("utf-8"), ".mcp.json"))
    files.extend((BRIDGE / "dist" / name, "server/" + name) for name in BRIDGE_FILES)
    files.append((BRIDGE / "README.md", "server/README.md"))
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openai-local", action="store_true",
                        help="Also build the desktop-only stdio submission ZIP (requires bridge build)")
    args = parser.parse_args()
    version = validate()
    # Fail before producing any archives if the submission bundle is stale.
    submission = openai_files(version) if args.openai_local else None
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    plugin_files = [(PLUGIN / name, name) for name in PLUGIN_FILES]
    marketplace_files = [(ROOT / name, name) for name in MARKETPLACE_FILES]
    marketplace_files += [(path, "plugins/augelab/" + name) for path, name in plugin_files]
    checksums = []
    packages = [
        (f"augelab-{version}.zip", plugin_files),
        (f"augelab-marketplace-{version}.zip", marketplace_files),
    ]
    if submission is not None:
        packages.append((f"augelab-openai-local-{version}.zip", submission))
    for name, files in packages:
        output = dist / name
        write_archive(output, files)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        checksums.append(f"{digest}  {name}")
        print(f"PASS {name}: {len(files)} files")
    (dist / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print("PASS manifests, single skill, local MCP endpoint, archive contents and checksums")


if __name__ == "__main__":
    main()
