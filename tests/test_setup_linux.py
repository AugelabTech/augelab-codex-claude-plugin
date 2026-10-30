"""Exercise Linux setup without real installers, Studio, sudo, or external network."""

from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/augelab/skills/augelab/scripts/setup-linux.py"
SPEC = importlib.util.spec_from_file_location("setup_linux", SCRIPT)
setup = importlib.util.module_from_spec(SPEC)
# Load without leaving bytecode in the plugin's strict release inventory.
exec(compile(SCRIPT.read_bytes(), str(SCRIPT), "exec"), setup.__dict__)


class LinuxSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.fixture = self.home / "fixture.sh"
        self.fixture.write_bytes(b"Test data, not an executable installer.\n")
        self.config = {"url": "https://" + setup.INSTALLER_HOST + "/linux/installer.sh",
                       "sha256": hashlib.sha256(self.fixture.read_bytes()).hexdigest()}
        self.launcher = self.home / ".local/bin/augelab_studio"
        self.start_patch(setup.platform, "system", return_value="Linux")
        self.start_patch(setup.platform, "machine", return_value="x86_64")
        self.start_patch(setup.Path, "home", return_value=self.home)
        self.start_patch(setup.os, "geteuid", return_value=1000, create=True)
        environment = patch.dict(setup.os.environ, {"DISPLAY": ":0"}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.ready = self.start_patch(setup, "mcp_ready", return_value=False)
        self.running = self.start_patch(setup, "studio_running", return_value=False)
        self.find = self.start_patch(setup, "find_launcher", return_value=None)
        self.save = self.start_patch(setup, "save_installer", return_value=self.fixture)
        self.run = self.start_patch(setup.subprocess, "run")
        self.launch = self.start_patch(setup.subprocess, "Popen")

    def start_patch(self, obj, name, **kwargs):
        patcher = patch.object(obj, name, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def execute(self, *args):
        return setup.setup(setup.parse_args(["--mcp-wait-seconds", "0", *args]))

    def fresh_install(self, *args):
        self.find.side_effect = [None, self.launcher]
        with patch.object(setup, "installer_config", return_value=self.config), \
                patch.object(setup.shutil, "which", return_value="/usr/bin/bash"):
            return self.execute(*args)

    def test_platform_and_architecture_selection(self):
        for architecture, expected in (("x86_64", "/linux/"), ("amd64", "/linux/"),
                                       ("aarch64", "/linux_arm64/"), ("arm64", "/linux_arm64/")):
            with self.subTest(architecture=architecture), patch.object(setup.platform, "machine", return_value=architecture):
                self.assertIn(expected, setup.installer_config()["url"])
        for system, architecture in (("Darwin", "arm64"), ("Windows", "AMD64"), ("Linux", "armv7l")):
            with self.subTest(system=system, architecture=architecture), \
                    patch.object(setup.platform, "system", return_value=system), \
                    patch.object(setup.platform, "machine", return_value=architecture):
                with self.assertRaisesRegex(ValueError, "requires Linux"):
                    setup.installer_config()

    def test_check_only_has_no_file_or_process_side_effects(self):
        result = self.execute("--check-only")
        self.assertEqual(result["status"], "checked")
        self.assertFalse(result["changed"])
        self.assertEqual(list(self.home.iterdir()), [self.fixture])
        self.save.assert_not_called()
        self.run.assert_not_called()
        self.launch.assert_not_called()

    def test_working_mcp_is_reused_without_install_or_launch(self):
        self.ready.return_value = True
        self.assertEqual(self.execute()["status"], "mcp-ready")
        self.save.assert_not_called()
        self.run.assert_not_called()
        self.launch.assert_not_called()

    def test_fresh_setup_uses_ui_profile_and_reports_activation(self):
        result = self.fresh_install()
        self.assertTrue(result["installedNow"])
        self.assertEqual(result["status"], "needs-activation-or-mcp")
        self.assertEqual(self.run.call_args.args[0], ["/usr/bin/bash", str(self.fixture), "--ui"])
        self.run.assert_called_once()
        self.launch.assert_called_once()

    def test_gpu_profile_is_explicit(self):
        self.fresh_install("--include-ai")
        self.assertEqual(self.run.call_args.args[0][-2:], ["--ui", "--ai"])

    def test_mismatched_hash_prevents_execution(self):
        self.fixture.write_bytes(b"Modified installer")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.fresh_install()
        self.run.assert_not_called()
        self.launch.assert_not_called()

    def test_failed_installer_stops_without_retry_or_launch(self):
        self.run.side_effect = subprocess.CalledProcessError(1, ["bash", "fixture"])
        with self.assertRaises(subprocess.CalledProcessError):
            self.fresh_install()
        self.run.assert_called_once()
        self.launch.assert_not_called()

    def test_exit_zero_without_launcher_is_not_success(self):
        self.find.side_effect = [None, None]
        with patch.object(setup, "installer_config", return_value=self.config), \
                patch.object(setup.shutil, "which", return_value="/usr/bin/bash"):
            with self.assertRaisesRegex(ValueError, "launcher is missing"):
                self.execute()
        self.launch.assert_not_called()

    def test_unknown_existing_venv_is_not_overwritten(self):
        (self.home / "studio_venv").mkdir()
        with self.assertRaisesRegex(ValueError, "destination already exists"):
            self.execute()
        self.save.assert_not_called()
        self.run.assert_not_called()

    def test_existing_studio_is_not_reinstalled_or_launched_twice(self):
        self.find.return_value = self.launcher
        self.running.return_value = True
        self.assertFalse(self.execute()["installedNow"])
        self.save.assert_not_called()
        self.run.assert_not_called()
        self.launch.assert_not_called()

    def test_download_only_does_not_probe_or_execute(self):
        result = self.execute("--download-only")
        self.assertEqual(result["status"], "downloaded")
        self.assertFalse(result["executed"])
        self.ready.assert_not_called()
        self.run.assert_not_called()
        self.launch.assert_not_called()

    def test_root_and_missing_graphical_session_stop_before_install(self):
        with patch.object(setup.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(ValueError, "desktop user"):
                self.execute()
        with patch.dict(setup.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "graphical desktop"):
                self.execute()
        self.save.assert_not_called()
        self.run.assert_not_called()

    def test_bad_custom_launcher_is_not_silently_replaced(self):
        with self.assertRaisesRegex(ValueError, "absolute path"):
            self.execute("--launcher", "relative")
        with self.assertRaisesRegex(ValueError, "missing or not executable"):
            self.execute("--launcher", str(self.launcher))
        self.save.assert_not_called()
        self.run.assert_not_called()


class DownloadTests(unittest.TestCase):
    def test_download_is_verified_cached_and_mismatch_leaves_no_partial(self):
        data = b"Fixture installer"
        config = {"url": "https://" + setup.INSTALLER_HOST + "/linux/installer.sh",
                  "sha256": hashlib.sha256(data).hexdigest()}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(setup.urllib.request.OpenerDirector, "open", return_value=io.BytesIO(data)) as opened:
            home = Path(directory)
            destination = setup.save_installer(config, home)
            self.assertEqual(destination.read_bytes(), data)
            self.assertEqual(setup.save_installer(config, home), destination)
            opened.assert_called_once()
            destination.write_bytes(b"Corrupted cache")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                setup.save_installer(config, home)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(setup.urllib.request.OpenerDirector, "open", return_value=io.BytesIO(b"wrong bytes")):
            home = Path(directory)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                setup.save_installer(config, home)
            self.assertEqual(list((home / ".cache/augelab/plugin-setup").iterdir()), [])


@unittest.skipUnless(sys.platform == "linux", "Requires Linux executable permissions and /proc")
class NativeLinuxTests(unittest.TestCase):
    def test_existing_launcher_discovery_and_running_process_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            launcher = home / ".local/bin/augelab_studio"
            launcher.parent.mkdir(parents=True)
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            launcher.chmod(0o700)
            self.assertEqual(setup.find_launcher(home), launcher)
            launcher.chmod(0o600)
            with patch.object(setup.shutil, "which", return_value=None):
                self.assertIsNone(setup.find_launcher(home))
            interpreter = home / "studio_venv/bin/python"
            interpreter.parent.mkdir(parents=True)
            interpreter.symlink_to(sys.executable)
            process = subprocess.Popen([str(interpreter), "-"], stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self.assertTrue(setup.studio_running(home))
            finally:
                process.terminate()
                process.wait(timeout=5)
                process.stdin.close()
            self.assertFalse(setup.studio_running(home))


class McpProbeTests(unittest.TestCase):
    @contextmanager
    def server(self, mode):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):
                requests.append(self.path)
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.server.testcase.assertEqual(body["method"], "initialize")
                if mode == "redirect":
                    self.send_response(307)
                    self.send_header("Location", "/redirected")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                value = {"jsonrpc": "2.0", "id": 1, "result": {
                    "protocolVersion": "2025-03-26", "serverInfo": {
                        "name": "unrelated-service" if mode == "unrelated" else "AugeLab Studio"}}}
                payload = json.dumps(value).encode()
                if mode == "invalid":
                    payload = b"not JSON"
                self.send_response(200)
                self.send_header("Mcp-Session-Id", "test-session")
                self.send_header("Content-Type", "text/event-stream" if mode == "sse" else "application/json")
                if mode != "sse":
                    self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(b"data: " + payload + b"\n\n" if mode == "sse" else payload)
                self.wfile.flush()

            def do_DELETE(self):
                requests.append("DELETE " + self.path)
                self.server.testcase.assertEqual(self.headers["Mcp-Session-Id"], "test-session")
                self.send_response(204)
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.testcase = self
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(setup, "ENDPOINT", f"http://127.0.0.1:{server.server_port}/mcp"):
                yield requests
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_json_and_open_sse_sessions_are_detected_and_closed(self):
        for mode in ("json", "sse", "unrelated", "invalid", "redirect"):
            with self.subTest(mode=mode), self.server(mode) as requests:
                self.assertEqual(setup.mcp_ready(), mode in {"json", "sse"})
                self.assertNotIn("/redirected", requests)
                self.assertEqual(requests, ["/mcp"] if mode == "redirect" else ["/mcp", "DELETE /mcp"])


if __name__ == "__main__":
    unittest.main()
