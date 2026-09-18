import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VNC_SCRIPT = REPO_ROOT / "runtime" / "bin" / "sw-vnc"


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
            self.assertIn("VNC_PASSWORD", res.stdout)
            self.assertIn("VNC_PORT", res.stdout)
            self.assertIn("DISPLAY_RESOLUTION", res.stdout)

    def _run_vnc(self, args, env=None):
        test_env = dict(os.environ)
        bin_dir = str(REPO_ROOT / "runtime" / "bin")
        test_env["PATH"] = f"{bin_dir}:{test_env.get('PATH', '')}"
        if env:
            test_env.update(env)
        return subprocess.run(
            [str(VNC_SCRIPT)] + args,
            capture_output=True,
            text=True,
            env=test_env,
        )

    def test_rejects_unknown_argument(self):
        res = self._run_vnc(["--non-existent-flag"])
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("未知选项", res.stderr)

    def test_dry_run_defaults(self):
        res = self._run_vnc(["--dry-run"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("1920x1080", res.stdout)
        self.assertIn("5900", res.stdout)
        self.assertIn("openbox", res.stdout)
        self.assertIn("--visible --user-control", res.stdout)

    def test_dry_run_custom_args(self):
        res = self._run_vnc([
            "--dry-run",
            "--port", "5901",
            "--resolution", "2560x1440",
            "--password", "mypass",
        ])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("2560x1440", res.stdout)
        self.assertIn("5901", res.stdout)
        self.assertIn("passwd", res.stdout)
        self.assertIn("--visible --user-control", res.stdout)

    def test_dry_run_env_overrides(self):
        res = self._run_vnc(["--dry-run"], env={
            "VNC_PORT": "5905",
            "DISPLAY_RESOLUTION": "1280x720",
            "VNC_PASSWORD": "envpass",
        })
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("5905", res.stdout)
        self.assertIn("1280x720", res.stdout)
        self.assertIn("passwd", res.stdout)


if __name__ == "__main__":
    unittest.main()
