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
        # Commands
        self.assertIn("usage", out)
        self.assertIn("run", out)
        self.assertIn("start", out)
        self.assertIn("stop", out)
        self.assertIn("restart", out)
        self.assertIn("status", out)

        # Options
        self.assertIn("--host", out)
        self.assertIn("--port", out)
        self.assertIn("--timeout", out)
        self.assertIn("--visible", out)
        self.assertIn("--user-control", out)
        self.assertIn("--vnc", out)
        self.assertIn("--vnc-interactive", out)
        self.assertIn("--vnc-port", out)
        self.assertIn("--vnc-password", out)
        self.assertIn("--resolution", out)

        # Environment Variables
        self.assertIn("sw_daemon_host", out)
        self.assertIn("sw_daemon_port", out)
        self.assertIn("sw_daemon_timeout", out)
        self.assertIn("vnc_enable", out)
        self.assertIn("vnc_interactive", out)
        self.assertIn("vnc_port", out)
        self.assertIn("vnc_password", out)
        self.assertIn("display_resolution", out)

    def test_unknown_subcommand_fails(self):
        res = subprocess.run([SCRIPT_PATH, "unknown_cmd"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("unknown", res.stderr.lower())

    def test_run_foreground_dry_run(self):
        res = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("foreground", res.stdout.lower())

    def test_status_when_stopped(self):
        # Point to a fake non-existent PID file
        env = dict(os.environ, DAEMON_PID_FILE="/tmp/sw_daemon_nonexistent_test.pid")
        res = subprocess.run([SCRIPT_PATH, "status"], capture_output=True, text=True, env=env)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not running", res.stdout.lower() + res.stderr.lower())

    # --- CLI Options Tests ---

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

    def test_vnc_port_option(self):
        res = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "--vnc", "--vnc-port", "5905", "start"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("-rfbport 5905", res.stdout)

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

    # --- Environment Variables Tests ---

    def test_env_vnc_triggers(self):
        env_vnc = dict(os.environ, VNC_ENABLE="true")
        res = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
            env=env_vnc,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("x11vnc", res.stdout)
        self.assertIn("-viewonly", res.stdout)

        env_interactive = dict(os.environ, VNC_ENABLE="true", VNC_INTERACTIVE="true")
        res_inter = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
            env=env_interactive,
        )
        self.assertEqual(res_inter.returncode, 0, res_inter.stderr)
        self.assertIn("x11vnc", res_inter.stdout)
        self.assertNotIn("-viewonly", res_inter.stdout)

    def test_env_vnc_port(self):
        env_vnc = dict(os.environ, VNC_ENABLE="true", VNC_PORT="5909")
        res_vnc = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
            env=env_vnc,
        )
        self.assertEqual(res_vnc.returncode, 0, res_vnc.stderr)
        self.assertIn("-rfbport 5909", res_vnc.stdout)

    def test_env_daemon_and_display_overrides(self):
        env_custom = dict(
            os.environ,
            SW_DAEMON_HOST="0.0.0.0",
            SW_DAEMON_PORT="19000",
            VNC_ENABLE="true",
            VNC_PASSWORD="custom_pass",
            DISPLAY_RESOLUTION="2560x1440",
        )
        res = subprocess.run(
            [SCRIPT_PATH, "--dry-run", "run"],
            capture_output=True,
            text=True,
            env=env_custom,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("0.0.0.0:19000", res.stdout)
        self.assertIn("2560x1440", res.stdout)
        self.assertIn("passwd", res.stdout)


if __name__ == "__main__":
    unittest.main()
