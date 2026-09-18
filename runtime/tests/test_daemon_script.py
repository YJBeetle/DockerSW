#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for sw-daemon management script (runtime/scripts/sw-daemon).
"""

import os
import subprocess
import unittest

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "sw-daemon"))


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
        self.assertIn("run", out)
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
        self.assertIn("--visible", res_vnc.stdout)
        self.assertNotIn("--user-control", res_vnc.stdout)

        res_interactive = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "start", "--vnc-interactive"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_interactive.returncode, 0, res_interactive.stderr)
        self.assertNotIn("-viewonly", res_interactive.stdout)
        self.assertIn("--visible", res_interactive.stdout)
        self.assertIn("--user-control", res_interactive.stdout)

    def test_run_foreground_dry_run(self):
        res = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("foreground", res.stdout.lower())

    def test_env_vnc_triggers(self):
        env_vnc = dict(os.environ, SW_VNC="true")
        res = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
            env=env_vnc,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("x11vnc", res.stdout)
        self.assertIn("-viewonly", res.stdout)

        env_interactive = dict(os.environ, SW_VNC="true", SW_VNC_INTERACTIVE="true")
        res_inter = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
            env=env_interactive,
        )
        self.assertEqual(res_inter.returncode, 0, res_inter.stderr)
        self.assertIn("x11vnc", res_inter.stdout)
        self.assertNotIn("-viewonly", res_inter.stdout)

    def test_vnc_port_option(self):
        res = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "--vnc", "--vnc-port", "5905", "start"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("-rfbport 5905", res.stdout)

    def test_env_vnc_port(self):
        env_sw = dict(os.environ, SW_VNC="true", SW_VNC_PORT="5908")
        res_sw = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
            env=env_sw,
        )
        self.assertEqual(res_sw.returncode, 0, res_sw.stderr)
        self.assertIn("-rfbport 5908", res_sw.stdout)

        env_compat = dict(os.environ, SW_VNC="true", VNC_PORT="5909")
        res_compat = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
            env=env_compat,
        )
        self.assertEqual(res_compat.returncode, 0, res_compat.stderr)
        self.assertIn("-rfbport 5909", res_compat.stdout)

    def test_vnc_resolution_and_password_options(self):
        res = subprocess.run(
            [
                SCRIPT_PATH,
                "--dry-run",
                "--vnc-interactive",
                "-r", "2560x1440",
                "-P", "secret123",
                "run",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("2560x1440", res.stdout)
        self.assertIn("openbox", res.stdout)
        self.assertIn("passwd", res.stdout)
        self.assertIn("--visible --user-control", res.stdout)


if __name__ == "__main__":
    unittest.main()
