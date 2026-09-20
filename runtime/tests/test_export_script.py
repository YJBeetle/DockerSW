import os
import subprocess
import tempfile
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SWCLI_SCRIPT = RUNTIME_ROOT / "bin" / "sw-cli"
ENTRYPOINT_SCRIPT = RUNTIME_ROOT / "entrypoint.sh"


class RuntimeWrapperTests(unittest.TestCase):
    def test_scripts_are_executable_and_valid_bash(self):
        for script in (SWCLI_SCRIPT,):
            self.assertTrue(os.access(script, os.X_OK), f"not executable: {script}")
            result = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((RUNTIME_ROOT / "bin" / "swclid").exists())
    def test_sw_cli_translates_typed_path_argument(self):
        invocation = self._run_with_fake_wine(
            SWCLI_SCRIPT, ["document", "open", "/workspace/model.SLDPRT", "--json"]
        )
        self.assertIn(
            "python3: -m swcli document open W:/workspace/model.SLDPRT --json",
            invocation,
        )

    def test_sw_cli_keeps_doctor_diagnostics_in_windows_python(self):
        invocation = self._run_with_fake_wine(
            SWCLI_SCRIPT, ["doctor", "--json"]
        )
        self.assertIn(
            "wine: C:\\Python311\\python.exe -m swcli doctor --json",
            invocation,
        )

    def test_typed_cli_does_not_manage_daemon_lifecycle(self):
        script = SWCLI_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("start_daemon", script)
        self.assertIn("SWCLI_ENDPOINT", script)

    def test_entrypoint_eagerly_starts_daemon_for_installed_solidworks(self):
        entrypoint = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('[ "${SOLIDWORKS_INSTALLED}" != true ]', entrypoint)
        self.assertIn('command -v sw-cli', entrypoint)
        self.assertIn('当前镜像未安装 SWCLI', entrypoint)
        self.assertIn('nohup sw-cli daemon serve', entrypoint)
        self.assertIn('sw-cli daemon status --endpoint', entrypoint)
        self.assertIn('当前镜像未安装 SOLIDWORKS', entrypoint)
        self.assertNotIn('SWCLID_AUTO_START', entrypoint)

    def test_daemon_serve_marks_docker_host_as_linux_wine(self):
        invocation = self._run_with_fake_wine(
            SWCLI_SCRIPT, ["daemon", "serve", "--port", "19000"]
        )
        self.assertIn(
            "-m swcli daemon serve --host-platform linux-wine --port 19000",
            invocation,
        )

    def test_daemon_status_runs_in_windows_python(self):
        invocation = self._run_with_fake_wine(
            SWCLI_SCRIPT, ["daemon", "status", "--json"]
        )
        self.assertIn(
            "wine: C:\\Python311\\python.exe -m swcli daemon status --json",
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
