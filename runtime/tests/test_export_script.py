#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for sw-export wrapper script (runtime/scripts/sw-export).
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "sw-export"))


EXPORTER_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "utils", "sw_exporter.py"))


class TestExportScript(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(os.path.isfile(SCRIPT_PATH), f"Script not found: {SCRIPT_PATH}")
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK), "Script is not executable")

    def test_bash_syntax(self):
        res = subprocess.run(["bash", "-n", SCRIPT_PATH], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Bash syntax check failed: {res.stderr}")

    def test_help_output(self):
        env = dict(os.environ, EXPORTER_SCRIPT=EXPORTER_SCRIPT)
        res = subprocess.run([SCRIPT_PATH, "--help"], capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        out = res.stdout.lower()
        self.assertIn("sw-export", out)
        self.assertIn("--list", out)
        self.assertIn("--workspace", out)
        self.assertIn("--outdir", out)

    def test_missing_args_fails(self):
        env = dict(os.environ, EXPORTER_SCRIPT=EXPORTER_SCRIPT)
        res = subprocess.run([SCRIPT_PATH], capture_output=True, text=True, env=env)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("缺少必须参数", res.stderr + res.stdout)

    def test_auto_start_daemon_and_delegates_to_cli(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()

            # Create a mock sw-cli that records invocations
            cli_log = tmp_path / "cli_calls.log"
            mock_cli = fake_bin / "sw-cli"
            mock_cli.write_text(f"""#!/usr/bin/env bash
echo "$@" >> "{cli_log}"
exit 0
""")
            mock_cli.chmod(0o755)

            env = dict(
                os.environ,
                PATH=f"{fake_bin}:{os.environ['PATH']}",
                EXPORTER_SCRIPT=EXPORTER_SCRIPT,
            )
            res = subprocess.run(
                [SCRIPT_PATH, "--list", "test.list", "--workspace", "/ws", "--outdir", "/out"],
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(res.returncode, 0, res.stderr)

            # Check that sw-cli run was called with --auto-start and arguments
            cli_calls = cli_log.read_text()
            self.assertIn("--auto-start", cli_calls)
            self.assertIn("run", cli_calls)
            self.assertIn(EXPORTER_SCRIPT, cli_calls)
            self.assertIn("test.list", cli_calls)
            self.assertIn("/ws", cli_calls)
            self.assertIn("/out", cli_calls)

    def test_host_port_and_timeout_forwarding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()

            cli_log = tmp_path / "cli_calls.log"
            mock_cli = fake_bin / "sw-cli"
            mock_cli.write_text(f"""#!/usr/bin/env bash
echo "$@" >> "{cli_log}"
exit 0
""")
            mock_cli.chmod(0o755)

            env = dict(
                os.environ,
                PATH=f"{fake_bin}:{os.environ['PATH']}",
                EXPORTER_SCRIPT=EXPORTER_SCRIPT,
            )
            res = subprocess.run(
                [
                    SCRIPT_PATH,
                    "--host", "10.0.0.1",
                    "--port", "19000",
                    "--timeout", "120",
                    "--list", "test.list",
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(res.returncode, 0, res.stderr)

            # Verify sw-cli was invoked with host, port, timeout and run
            cli_calls = cli_log.read_text()
            self.assertIn("--auto-start", cli_calls)
            self.assertIn("--host 10.0.0.1", cli_calls)
            self.assertIn("--port 19000", cli_calls)
            self.assertIn("--timeout 120", cli_calls)
            self.assertIn("run", cli_calls)
            self.assertIn("--list test.list", cli_calls)


if __name__ == "__main__":
    unittest.main()
