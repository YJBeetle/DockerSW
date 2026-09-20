import os
import subprocess
import tempfile
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SWCLI_SCRIPT = RUNTIME_ROOT / "bin" / "sw-cli"
DAEMON_SCRIPT = RUNTIME_ROOT / "bin" / "swclid"


class RuntimeWrapperTests(unittest.TestCase):
    def test_scripts_are_executable_and_valid_bash(self):
        for script in (SWCLI_SCRIPT, DAEMON_SCRIPT):
            self.assertTrue(os.access(script, os.X_OK), f"not executable: {script}")
            result = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
    def test_sw_cli_translates_typed_path_argument(self):
        invocation = self._run_with_fake_wine(
            SWCLI_SCRIPT, ["document", "open", "/workspace/model.SLDPRT", "--json"]
        )
        self.assertIn(
            "python3: -m swcli document open W:/workspace/model.SLDPRT --json",
            invocation,
        )

    def test_sw_cli_keeps_host_diagnostics_in_windows_python(self):
        invocation = self._run_with_fake_wine(
            SWCLI_SCRIPT, ["host", "probe", "--json"]
        )
        self.assertIn(
            "wine: C:\\Python311\\python.exe -m swcli host probe --json",
            invocation,
        )

    def test_typed_cli_uses_resident_daemon(self):
        script = SWCLI_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("swclid_ensure", script)
        self.assertIn("python3 -m swcli.daemon status", script)
        self.assertIn("-m swcli.daemon serve", script)
        self.assertIn("SWCLI_ENDPOINT", script)

    def test_swclid_marks_docker_host_as_linux_wine(self):
        invocation = self._run_with_fake_wine(
            DAEMON_SCRIPT, ["serve", "--port", "19000"]
        )
        self.assertIn(
            "-m swcli.daemon serve --host-platform linux-wine --port 19000",
            invocation,
        )

    def _run_with_fake_wine(self, script: Path, args: list[str]) -> str:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            binary_dir = root / "bin"
            binary_dir.mkdir()
            wine_log = root / "wine.log"
            python_log = root / "python.log"
            winepath = binary_dir / "winepath"
            winepath.write_text(
                "#!/usr/bin/env bash\nprintf 'W:%s\\n' \"${@: -1}\"\n",
                encoding="utf-8",
            )
            winepath.chmod(0o755)
            wine = binary_dir / "wine"
            wine.write_text(
                f"#!/usr/bin/env bash\nprintf 'wine: %s\\n' \"$*\" > '{wine_log}'\n",
                encoding="utf-8",
            )
            wine.chmod(0o755)
            python3 = binary_dir / "python3"
            python3.write_text(
                f"#!/usr/bin/env bash\nprintf 'python3: %s\\n' \"$*\" > '{python_log}'\n",
                encoding="utf-8",
            )
            python3.chmod(0o755)
            environment = dict(os.environ)
            environment["PATH"] = f"{binary_dir}:{environment['PATH']}"
            result = subprocess.run(
                [str(script), *args], capture_output=True, text=True, env=environment
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            logs = []
            for log in (wine_log, python_log):
                if log.exists():
                    logs.append(log.read_text(encoding="utf-8"))
            return "".join(logs)


if __name__ == "__main__":
    unittest.main()
