import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VNC_SCRIPT = REPO_ROOT / "runtime" / "scripts" / "sw-vnc"


class TestVncScript(unittest.TestCase):
    def test_script_exists_and_executable(self):
        self.assertTrue(VNC_SCRIPT.exists(), f"sw-vnc not found at {VNC_SCRIPT}")
        self.assertTrue(os.access(VNC_SCRIPT, os.X_OK), "sw-vnc must be executable")

    def test_bash_syntax(self):
        res = subprocess.run(
            ["bash", "-n", str(VNC_SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Syntax error in sw-vnc: {res.stderr}")

    def test_help_output(self):
        for flag in ["-h", "--help"]:
            res = subprocess.run(
                [str(VNC_SCRIPT), flag],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("sw-vnc", res.stdout)
            self.assertIn("--port", res.stdout)
            self.assertIn("--password", res.stdout)
            self.assertIn("--resolution", res.stdout)
            self.assertIn("--desktop", res.stdout)
            self.assertIn("--bash", res.stdout)
            self.assertIn("VNC_PASSWORD", res.stdout)
            self.assertIn("VNC_PORT", res.stdout)

    def test_rejects_unknown_argument(self):
        res = subprocess.run(
            [str(VNC_SCRIPT), "--non-existent-flag"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("未知选项", res.stderr)

    def test_dry_run_defaults(self):
        res = subprocess.run(
            [str(VNC_SCRIPT), "--dry-run"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("CONFIG:PORT=5900", res.stdout)
        self.assertIn("CONFIG:RESOLUTION=1920x1080", res.stdout)
        self.assertIn("CONFIG:PASSWORD_SET=true", res.stdout)
        self.assertIn("CONFIG:TARGET=sw", res.stdout)

    def test_dry_run_custom_args(self):
        res = subprocess.run(
            [
                str(VNC_SCRIPT),
                "--dry-run",
                "--port",
                "5901",
                "--resolution",
                "2560x1440",
                "--password",
                "mypass",
                "--bash",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("CONFIG:PORT=5901", res.stdout)
        self.assertIn("CONFIG:RESOLUTION=2560x1440", res.stdout)
        self.assertIn("CONFIG:TARGET=bash", res.stdout)

    def test_dry_run_desktop_mode(self):
        res = subprocess.run(
            [str(VNC_SCRIPT), "--dry-run", "--desktop"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("CONFIG:TARGET=desktop", res.stdout)

    def test_dry_run_env_overrides(self):
        env = os.environ.copy()
        env["VNC_PORT"] = "5905"
        env["VNC_RESOLUTION"] = "1280x720"
        env["VNC_PASSWORD"] = "envpass"
        res = subprocess.run(
            [str(VNC_SCRIPT), "--dry-run"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("CONFIG:PORT=5905", res.stdout)
        self.assertIn("CONFIG:RESOLUTION=1280x720", res.stdout)


if __name__ == "__main__":
    unittest.main()
