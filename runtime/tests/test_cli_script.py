#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for sw-cli client tool (runtime/scripts/sw-cli).
Uses local mock HTTP server to test subcommands, JSON formatting, and exit codes.
"""

import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "sw-cli"))


class MockDaemonHandler(BaseHTTPRequestHandler):
    last_request_path = ""
    last_request_body = {}
    mock_execute_response = {
        "success": True,
        "exit_code": 0,
        "stdout": "mocked output\n",
        "stderr": "",
        "data": {"metric": 99},
        "duration_ms": 15,
    }
    mock_canvas_response = {
        "success": True,
        "path": "/tmp/mock_canvas.png",
        "doc_title": "part1.SLDPRT",
    }
    mock_health_response = {
        "status": "ok",
        "ready": True,
        "sw_connected": True,
        "sw_version": "33.5.0",
        "uptime_s": 10.5,
    }

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        MockDaemonHandler.last_request_path = self.path
        if self.path in ("/v1/health", "/health"):
            self._send_json(200, MockDaemonHandler.mock_health_response)
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        MockDaemonHandler.last_request_path = self.path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            MockDaemonHandler.last_request_body = json.loads(raw.decode("utf-8"))
        except Exception:
            MockDaemonHandler.last_request_body = {}

        if self.path in ("/v1/execute", "/execute"):
            self._send_json(200, MockDaemonHandler.mock_execute_response)
        elif self.path in ("/v1/canvas", "/canvas"):
            self._send_json(200, MockDaemonHandler.mock_canvas_response)
        elif self.path in ("/v1/screenshot", "/screenshot"):
            self._send_json(200, {"success": True, "path": "/tmp/mock_screen.png"})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass


class TestCliScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start a local mock server on an ephemeral port
        cls.server = HTTPServer(("127.0.0.1", 0), MockDaemonHandler)
        cls.port = cls.server.server_port
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_script_exists_and_is_executable(self):
        self.assertTrue(os.path.isfile(SCRIPT_PATH), f"Script not found: {SCRIPT_PATH}")
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK), "Script is not executable")

    def test_bash_syntax(self):
        res = subprocess.run(["bash", "-n", SCRIPT_PATH], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Bash syntax check failed: {res.stderr}")

    def test_help_output(self):
        res = subprocess.run([SCRIPT_PATH, "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        out = res.stdout.lower()
        self.assertIn("usage", out)
        self.assertIn("run", out)
        self.assertIn("eval", out)
        self.assertIn("status", out)
        self.assertIn("canvas", out)
        self.assertIn("screenshot", out)
        self.assertIn("--json", out)

    def test_status_command(self):
        res = subprocess.run(
            [SCRIPT_PATH, "status", "--port", str(self.port)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("ready", res.stdout.lower())

    def test_status_command_json(self):
        res = subprocess.run(
            [SCRIPT_PATH, "status", "--port", str(self.port), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(data.get("status"), "ok")
        self.assertTrue(data.get("ready"))

    def test_eval_command(self):
        MockDaemonHandler.mock_execute_response = {
            "success": True,
            "exit_code": 0,
            "stdout": "result of eval\n",
            "stderr": "",
            "data": {"count": 10},
            "duration_ms": 5,
        }
        res = subprocess.run(
            [SCRIPT_PATH, "eval", "print('hello')", "--port", str(self.port)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("result of eval", res.stdout)
        self.assertEqual(MockDaemonHandler.last_request_body.get("code"), "print('hello')")

    def test_eval_command_json(self):
        MockDaemonHandler.mock_execute_response = {
            "success": True,
            "exit_code": 0,
            "stdout": "eval stdout\n",
            "stderr": "",
            "data": {"foo": "bar"},
            "duration_ms": 12,
        }
        res = subprocess.run(
            [SCRIPT_PATH, "eval", "1+1", "--port", str(self.port), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"], {"foo": "bar"})

    def test_run_command_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("print('running script file')\n")
            temp_py = f.name

        try:
            MockDaemonHandler.mock_execute_response = {
                "success": True,
                "exit_code": 0,
                "stdout": "executed from file\n",
                "stderr": "",
                "data": {},
                "duration_ms": 20,
            }
            res = subprocess.run(
                [SCRIPT_PATH, "run", temp_py, "arg1", "--port", str(self.port)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("executed from file", res.stdout)
            self.assertEqual(MockDaemonHandler.last_request_body.get("path"), temp_py)
            self.assertEqual(MockDaemonHandler.last_request_body.get("args"), ["arg1"])
        finally:
            if os.path.exists(temp_py):
                os.remove(temp_py)

    def test_canvas_command(self):
        MockDaemonHandler.mock_canvas_response = {
            "success": True,
            "path": "/workspace/my_canvas.png",
            "doc_title": "bracket.SLDPRT",
        }
        res = subprocess.run(
            [SCRIPT_PATH, "canvas", "/workspace/my_canvas.png", "--port", str(self.port)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("/workspace/my_canvas.png", res.stdout)
        self.assertEqual(MockDaemonHandler.last_request_path, "/v1/canvas")

    def test_error_exit_code_forwarding(self):
        MockDaemonHandler.mock_execute_response = {
            "success": False,
            "exit_code": 42,
            "stdout": "",
            "stderr": "Custom failure occurred",
            "data": {},
            "duration_ms": 3,
        }
        res = subprocess.run(
            [SCRIPT_PATH, "eval", "fail()", "--port", str(self.port)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 42)
        self.assertIn("Custom failure occurred", res.stderr)

    def test_auto_start_invokes_daemon_start_if_unhealthy(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_bin = Path(tmpdir)
            daemon_log = fake_bin / "daemon.log"
            mock_daemon = fake_bin / "sw-daemon"
            mock_daemon.write_text(f"""#!/usr/bin/env bash
echo "$@" >> "{daemon_log}"
if [[ "$*" == *"status"* ]]; then
    exit 1
fi
exit 0
""")
            mock_daemon.chmod(0o755)

            env = dict(
                os.environ,
                SW_DAEMON_BIN=str(mock_daemon),
            )
            res = subprocess.run(
                [SCRIPT_PATH, "--auto-start", "eval", "1+1", "--port", str(self.port)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            daemon_calls = daemon_log.read_text()
            self.assertIn("status", daemon_calls)
            self.assertIn("start", daemon_calls)


if __name__ == "__main__":
    unittest.main()
