import os
import subprocess
import tempfile
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SWCLI_SCRIPT = RUNTIME_ROOT / "bin" / "sw-cli"
TRANSLATOR_SCRIPT = RUNTIME_ROOT / "bin" / "linux-to-wine-path"
ENTRYPOINT_SCRIPT = RUNTIME_ROOT / "entrypoint.sh"


class RuntimeWrapperTests(unittest.TestCase):
    def test_scripts_are_executable_and_valid_bash(self):
        for script in (SWCLI_SCRIPT, TRANSLATOR_SCRIPT):
            self.assertTrue(os.access(script, os.X_OK), f"not executable: {script}")
            result = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((RUNTIME_ROOT / "bin" / "swclid").exists())

    def test_wrapper_leaves_typed_arguments_untouched_and_sets_translator(self):
        invocation = self._run_with_fake_wine(
            [
                "document",
                "export",
                "--document",
                "d-ab12cd",
                "/workspace/out.STEP",
                "--strict",
                "--json",
            ]
        )
        self.assertIn(
            "python3: TRANSLATOR=/usr/local/bin/linux-to-wine-path "
            "-m swcli document export --document d-ab12cd /workspace/out.STEP "
            "--strict --json",
            invocation,
        )
        self.assertNotIn("W:/workspace", invocation)

    def test_wrapper_does_not_hardcode_positional_path_translation(self):
        script = SWCLI_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("option_takes_value", script)
        self.assertNotIn("translate_positional_path", script)
        self.assertNotIn("translate_first_positional", script)

    def test_windows_python_loads_swcli_from_shared_source(self):
        invocation = self._run_with_fake_wine(["daemon", "status", "--json"])
        self.assertIn("PYTHONPATH=Z:\\opt\\swcli\\src", invocation)

    def test_doctor_runs_under_wine_python(self):
        invocation = self._run_with_fake_wine(["doctor", "--json"])
        self.assertIn(
            "C:\\Python311\\python.exe -m swcli doctor --json",
            invocation,
        )

    def test_daemon_status_runs_under_wine_python(self):
        invocation = self._run_with_fake_wine(["daemon", "status", "--json"])
        self.assertIn(
            "C:\\Python311\\python.exe -m swcli daemon status --json",
            invocation,
        )

    def test_daemon_serve_marks_docker_host_as_linux_wine(self):
        invocation = self._run_with_fake_wine(["daemon", "serve", "--port", "19000"])
        self.assertIn(
            "-m swcli daemon serve --host-platform linux-wine --port 19000",
            invocation,
        )

    def test_daemon_serve_respects_explicit_host_platform(self):
        invocation = self._run_with_fake_wine(
            ["daemon", "serve", "--host-platform", "macos-wine", "--port", "19000"]
        )
        self.assertIn(
            "-m swcli daemon serve --host-platform macos-wine --port 19000",
            invocation,
        )
        self.assertEqual(invocation.count("--host-platform"), 1)

    def test_typed_cli_does_not_manage_daemon_lifecycle(self):
        script = SWCLI_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("start_daemon", script)
        self.assertIn("SWCLI_ENDPOINT", script)

    def _run_with_fake_wine(self, args):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            binary_dir = root / "bin"
            binary_dir.mkdir()
            wine_log = root / "wine.log"
            python_log = root / "python.log"
            wine = binary_dir / "wine"
            wine.write_text(
                "#!/usr/bin/env bash\n"
                f"printf 'wine: PYTHONPATH=%s %s\\n' \"$PYTHONPATH\" \"$*\" > '{wine_log}'\n",
                encoding="utf-8",
            )
            wine.chmod(0o755)
            winepath = binary_dir / "winepath"
            winepath.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' 'Z:\\opt\\swcli\\src'\n",
                encoding="utf-8",
            )
            winepath.chmod(0o755)
            python3 = binary_dir / "python3"
            python3.write_text(
                "#!/usr/bin/env bash\n"
                f"printf 'python3: TRANSLATOR=%s %s\\n' "
                "\"$SWCLI_PATH_TRANSLATE_CMD\" \"$*\" "
                f"> '{python_log}'\n",
                encoding="utf-8",
            )
            python3.chmod(0o755)
            environment = dict(os.environ)
            environment["PATH"] = f"{binary_dir}:{environment['PATH']}"
            result = subprocess.run(
                [str(SWCLI_SCRIPT), *args],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            logs = []
            for log in (wine_log, python_log):
                if log.exists():
                    logs.append(log.read_text(encoding="utf-8"))
            return "".join(logs)


class LinuxToWinePathTests(unittest.TestCase):
    def test_posix_path_goes_through_winepath(self):
        output = self._run(["/workspace/model.SLDPRT"])
        self.assertEqual(output.strip(), "W:/workspace/model.SLDPRT")

    def test_windows_path_passes_through(self):
        output = self._run(["C:\\Program Files\\x.SLDPRT"])
        self.assertEqual(output, "C:\\Program Files\\x.SLDPRT\n")

    def test_relative_posix_path_goes_through_winepath(self):
        output = self._run(["./out.STEP"])
        self.assertEqual(output.strip(), "W:./out.STEP")

    def test_empty_input_produces_no_output(self):
        output = self._run([""])
        self.assertEqual(output, "")

    def _run(self, args):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            binary_dir = root / "bin"
            binary_dir.mkdir()
            winepath = binary_dir / "winepath"
            winepath.write_text(
                "#!/usr/bin/env bash\nprintf 'W:%s\\n' \"${@: -1}\"\n",
                encoding="utf-8",
            )
            winepath.chmod(0o755)
            environment = dict(os.environ)
            environment["PATH"] = f"{binary_dir}:{environment['PATH']}"
            result = subprocess.run(
                [str(TRANSLATOR_SCRIPT), *args],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout


class EntrypointTests(unittest.TestCase):
    def test_entrypoint_does_not_echo_runner_command_payload(self):
        entrypoint = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('echo "[DockerSW] 容器初始化完成"', entrypoint)
        self.assertNotIn('echo "[DockerSW] 执行指令: $@"', entrypoint)

    def test_entrypoint_eagerly_starts_daemon_for_installed_solidworks(self):
        entrypoint = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('[ "${SOLIDWORKS_INSTALLED}" != true ]', entrypoint)
        self.assertIn("command -v sw-cli", entrypoint)
        self.assertIn("当前镜像未安装 SWCLI", entrypoint)
        self.assertIn("SWCLID_SERVE_ARGS=(", entrypoint)
        self.assertIn('nohup sw-cli "${SWCLID_SERVE_ARGS[@]}"', entrypoint)
        self.assertIn("sw-cli daemon status", entrypoint)
        self.assertIn('--endpoint "${SWCLI_ENDPOINT}"', entrypoint)
        self.assertIn("当前镜像未安装 SOLIDWORKS", entrypoint)
        self.assertNotIn("SWCLID_AUTO_START", entrypoint)

    def test_entrypoint_has_a_bounded_daemon_readiness_grace_period(self):
        entrypoint = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('SWCLID_READY_GRACE="${SWCLID_READY_GRACE:-10}"', entrypoint)
        self.assertIn("SWCLID_READY_DEADLINE=$((SECONDS +", entrypoint)
        self.assertIn('timeout "${probe_timeout}s" sw-cli daemon status', entrypoint)

    def test_entrypoint_requires_explicit_remote_daemon_opt_in(self):
        entrypoint = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('SWCLID_ALLOW_REMOTE="${SWCLID_ALLOW_REMOTE:-false}"', entrypoint)
        self.assertIn(
            'require_boolean "SWCLID_ALLOW_REMOTE" "${SWCLID_ALLOW_REMOTE}"',
            entrypoint,
        )
        self.assertIn('SWCLID_SERVE_ARGS+=(--allow-remote)', entrypoint)

if __name__ == "__main__":
    unittest.main()
