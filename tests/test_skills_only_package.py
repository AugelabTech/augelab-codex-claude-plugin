"""Skills-only archive and isolated real-client registration checks."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("plugin_package", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class SkillsOnlyPackageTests(unittest.TestCase):
    def test_archive_has_one_skill_and_no_declared_or_bundled_mcp(self):
        version = package.validate()
        archive = ROOT / "dist" / f"augelab-openai-skills-only-{version}.zip"
        with zipfile.ZipFile(archive) as plugin:
            names = set(plugin.namelist())
            self.assertEqual(names, set(package.PLUGIN_FILES) - {".mcp.json"})
            self.assertEqual(len([n for n in names if n.endswith("/SKILL.md")]), 1)
            self.assertFalse(names & {".mcp.json", "mcp.json", ".app.json"})
            self.assertFalse(any(n.startswith(("server/", "hooks/", "node_modules/")) for n in names))
            for name in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
                manifest = json.loads(plugin.read(name))
                self.assertEqual(manifest["name"], "augelab-setup")
                self.assertEqual(manifest["version"], version)
                self.assertNotIn("mcpServers", manifest)
                self.assertNotIn("apps", manifest)
                self.assertNotIn("hooks", manifest)
            manifest = json.loads(plugin.read(".codex-plugin/plugin.json"))
            self.assertTrue(manifest["requires_local_executor"])
            self.assertLessEqual(len(manifest["interface"]["shortDescription"]), 30)
            self.assertTrue((plugin.read("skills/augelab/references/client-mcp.md")))

    def test_profile_does_not_mutate_the_full_integration_manifest(self):
        before = (package.PLUGIN / ".codex-plugin/plugin.json").read_bytes()
        package.skills_only_files(package.validate())
        self.assertEqual(before, (package.PLUGIN / ".codex-plugin/plugin.json").read_bytes())
        self.assertEqual(json.loads(before)["mcpServers"], "./.mcp.json")

    @unittest.skipUnless(shutil.which("codex"), "Local Codex CLI unavailable")
    def test_real_codex_registration_preserves_unrelated_settings_in_isolated_home(self):
        with tempfile.TemporaryDirectory(prefix="augelab-client-config-") as temp:
            home = Path(temp)
            config = home / "config.toml"
            config.write_text('model = "fixture-model"\nmodel_reasoning_effort = "medium"\n'
                              '[mcp_servers.other]\nurl = "http://127.0.0.1:1/mcp"\n', encoding="utf-8")
            # Only child CLI processes receive this test config directory.
            # No changes are made to the user's running clients or configuration.
            env = os.environ.copy()
            env["CODEX_HOME"] = str(home)
            def cli(*args):
                return subprocess.run([shutil.which("codex"), "mcp", *args], env=env, cwd=temp,
                                      capture_output=True, text=True, encoding="utf-8", timeout=20)
            absent = cli("get", "augelab-studio", "--json")
            self.assertNotEqual(absent.returncode, 0)
            added = cli("add", "augelab-studio", "--url", "http://127.0.0.1:8765/mcp")
            self.assertEqual(added.returncode, 0, added.stderr)
            current = cli("get", "augelab-studio", "--json")
            self.assertEqual(current.returncode, 0, current.stderr)
            entry = json.loads(current.stdout)
            self.assertEqual(entry["transport"]["url"], "http://127.0.0.1:8765/mcp")
            self.assertEqual(entry["transport"]["type"], "streamable_http")
            other = cli("get", "other", "--json")
            self.assertEqual(other.returncode, 0)
            self.assertEqual(json.loads(other.stdout)["transport"]["url"], "http://127.0.0.1:1/mcp")
            saved = config.read_text(encoding="utf-8")
            self.assertIn('model = "fixture-model"', saved)
            self.assertIn('model_reasoning_effort = "medium"', saved)
            # A readback of a matching entry is enough; no second add is needed.
            before = config.read_bytes()
            self.assertEqual(cli("get", "augelab-studio", "--json").returncode, 0)
            self.assertEqual(config.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
