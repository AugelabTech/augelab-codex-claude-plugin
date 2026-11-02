"""Verify the submission ZIP, its provenance and its standalone runtime."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("plugin_package", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class SubmissionPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.version = package.validate()
        cls.archive = ROOT / "dist" / f"augelab-openai-local-{cls.version}.zip"
        if not cls.archive.is_file():
            raise RuntimeError("Build bridge and run scripts/package.py --openai-local first")

    def test_inventory_configuration_and_private_data_boundaries(self):
        with zipfile.ZipFile(self.archive) as archive:
            expected = set(package.PLUGIN_FILES) | {
                "server/augelab-mcp.mjs", "server/THIRD_PARTY_NOTICES.txt",
                "server/build-info.json", "server/README.md",
            }
            self.assertEqual(set(archive.namelist()), expected)
            config = json.loads(archive.read(".mcp.json"))["mcpServers"]["augelab-studio"]
            self.assertEqual(config, {
                "type": "stdio", "command": "node",
                "args": ["${PLUGIN_ROOT}/server/augelab-mcp.mjs", "--port", "8765"],
                "cwd": "${PLUGIN_ROOT}",
            })
            manifest = json.loads(archive.read(".codex-plugin/plugin.json"))
            self.assertEqual(manifest["name"], "augelab")
            self.assertEqual(manifest["version"], self.version)
            self.assertTrue(manifest["requires_local_executor"])
            self.assertIn("Node.js 22+", manifest["interface"]["longDescription"])
            for entry in archive.infolist():
                self.assertFalse(entry.filename.endswith(".map"))
                self.assertNotIn("node_modules/", entry.filename)
                self.assertFalse(Path(entry.filename).is_absolute())
                self.assertNotIn("..", Path(entry.filename).parts)
                text = archive.read(entry).decode("utf-8", errors="ignore").lower()
                for forbidden in ("hub.augelab.com/mcp", "c:\\users\\", "c:/users/", "/users/", "@gmail.com", "@outlook.com"):
                    self.assertNotIn(forbidden, text, entry.filename)

    def test_default_distribution_remains_http(self):
        archive = ROOT / "dist" / f"augelab-{self.version}.zip"
        with zipfile.ZipFile(archive) as plugin:
            self.assertEqual(json.loads(plugin.read(".mcp.json"))["mcpServers"]["augelab-studio"], {
                "type": "http", "url": "http://127.0.0.1:8765/mcp",
            })
            self.assertFalse(any(name.startswith("server/") for name in plugin.namelist()))

    def test_archive_rebuild_is_byte_identical_and_checksums_match(self):
        with tempfile.TemporaryDirectory(prefix="augelab-rebuild-") as temp:
            output = Path(temp) / "submission.zip"
            package.write_archive(output, package.openai_files(self.version))
            self.assertEqual(output.read_bytes(), self.archive.read_bytes())
        sums = (ROOT / "dist/SHA256SUMS.txt").read_text(encoding="utf-8")
        self.assertIn(f"{hashlib.sha256(self.archive.read_bytes()).hexdigest()}  {self.archive.name}", sums)

    def test_stale_source_and_tampered_bundle_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="augelab-provenance-") as temp:
            source = Path(temp)
            shutil.copytree(ROOT / "bridge", source / "bridge", ignore=shutil.ignore_patterns("node_modules", "test"))
            copied = source / "bridge"
            with patch.object(package, "BRIDGE", copied):
                package.validate_bridge(self.version)
                (copied / "src/index.mjs").write_text("changed", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "stale"):
                    package.validate_bridge(self.version)
                shutil.copyfile(ROOT / "bridge/src/index.mjs", copied / "src/index.mjs")
                (copied / "dist/augelab-mcp.mjs").write_text("tampered", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    package.validate_bridge(self.version)

    def test_extracted_bundle_runs_without_node_modules_in_a_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="augelab-stdio-") as temp:
            extracted = Path(temp) / "AugeLab test Türkçe"
            with zipfile.ZipFile(self.archive) as archive:
                archive.extractall(extracted)
            self.assertFalse((extracted / "node_modules").exists())
            env = os.environ.copy()
            for key in ("NODE_PATH", "NODE_OPTIONS"):
                env.pop(key, None)
            env["AUGELAB_BRIDGE_PATH"] = str(extracted / "server/augelab-mcp.mjs")
            # Run all black-box protocol tests against the extracted artifact;
            # child processes start outside the repository, with no npm install.
            result = subprocess.run([shutil.which("node"), "--test", str(ROOT / "bridge/test/bridge.test.mjs")],
                                    env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
