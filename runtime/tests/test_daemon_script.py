#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for sw-daemon management script (runtime/scripts/sw-daemon).
"""

import os
import subprocess
import unittest

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "sw-daemon"))


class TestDaemonScript(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(os.path.isfile(SCRIPT_PATH), f"Script not found at {SCRIPT_PATH}")
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK), "Script is not executable")

    def test_bash_syntax(self):
        res = subprocess.run(["bash", "-n", SCRIPT_PATH], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Bash syntax check failed: {res.stderr}")

    def test_help_output(self):
        res = subprocess.run([SCRIPT_PATH, "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        out = res.stdout.lower()
        self.assertIn("usage", out)
        self.assertIn("start", out)
        self.assertIn("stop", out)
        self.assertIn("restart", out)
        self.assertIn("status", out)
        self.assertIn("--vnc", out)
        self.assertIn("--vnc-interactive", out)
        self.assertIn("--port", out)

    def test_unknown_subcommand_fails(self):
        res = subprocess.run([SCRIPT_PATH, "unknown_cmd"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("unknown", res.stderr.lower())

    def test_status_when_stopped(self):
        # Point to a fake non-existent PID file
        env = dict(os.environ, SW_DAEMON_PID_FILE="/tmp/sw_daemon_nonexistent_test.pid")
        res = subprocess.run([SCRIPT_PATH, "status"], capture_output=True, text=True, env=env)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not running", res.stdout.lower() + res.stderr.lower())

    def test_vnc_viewonly_argument_logic(self):
        # Dry-run test command to inspect generated VNC arguments
        res_vnc = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "start", "--vnc"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_vnc.returncode, 0, res_vnc.stderr)
        self.assertIn("-viewonly", res_vnc.stdout)

        res_interactive = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "start", "--vnc-interactive"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_interactive.returncode, 0, res_interactive.stderr)
        self.assertNotIn("-viewonly", res_interactive.stdout)


if __name__ == "__main__":
    unittest.main()
