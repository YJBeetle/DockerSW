import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PROJECT_ROOT / "runtime"
SWCLI_ROOT = PROJECT_ROOT / "swcli"
SWCLI_SCRIPT = SWCLI_ROOT / "bin" / "sw-cli"
TRANSLATOR_SCRIPT = SWCLI_ROOT / "bin" / "linux-to-wine-path"
RUNTIME_ENTRYPOINT = RUNTIME_ROOT / "entrypoint.sh"
CLI_ENTRYPOINT = SWCLI_ROOT / "entrypoint-cli.sh"


class RuntimeWrapperTests(unittest.TestCase):
    def test_scripts_are_executable_and_valid_bash(self):
        for script in (
            SWCLI_SCRIPT,
            TRANSLATOR_SCRIPT,
            RUNTIME_ENTRYPOINT,
            CLI_ENTRYPOINT,
        ):
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

    def test_daemon_start_marks_child_host_as_linux_wine(self):
        invocation = self._run_with_fake_wine(["daemon", "start", "--json"])
        self.assertIn("HOST_PLATFORM=linux-wine", invocation)

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
                f"printf 'wine: PYTHONPATH=%s %s HOST_PLATFORM=%s\\n' "
                f"\"$PYTHONPATH\" \"$*\" \"$SWCLI_HOST_PLATFORM\" > '{wine_log}'\n",
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
        for entrypoint_path in (RUNTIME_ENTRYPOINT, CLI_ENTRYPOINT):
            entrypoint = entrypoint_path.read_text(encoding="utf-8")
            self.assertNotIn('echo "[DockerSW] 执行指令: $@"', entrypoint)

    def test_runtime_entrypoint_has_no_swcli_lifecycle(self):
        entrypoint = RUNTIME_ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn("export SOLIDWORKS_INSTALLED=true", entrypoint)
        self.assertIn('exec "$@"', entrypoint)
        self.assertNotIn("SWCLI", entrypoint)
        self.assertNotIn("sw-cli", entrypoint)

    def test_cli_entrypoint_eagerly_starts_daemon_for_installed_solidworks(self):
        entrypoint = CLI_ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn('[ "${SOLIDWORKS_INSTALLED:-false}" != true ]', entrypoint)
        self.assertIn("SWCLID_START_ARGS=(", entrypoint)
        self.assertIn("daemon start", entrypoint)
        self.assertIn('sw-cli "${SWCLID_START_ARGS[@]}"', entrypoint)
        self.assertIn('--endpoint "${SWCLI_ENDPOINT}"', entrypoint)
        self.assertIn("当前镜像未安装 SOLIDWORKS", entrypoint)
        self.assertNotIn("daemon serve", entrypoint)
        self.assertNotIn("--attach-existing", entrypoint)

    def test_cli_entrypoint_delegates_readiness_to_daemon_start(self):
        entrypoint = CLI_ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn('--startup-timeout "${SWCLID_START_TIMEOUT}"', entrypoint)
        self.assertNotIn("SWCLID_READY_GRACE", entrypoint)
        self.assertNotIn("daemon status", entrypoint)

    def test_cli_entrypoint_makes_solidworks_visible_when_vnc_is_enabled(self):
        entrypoint = CLI_ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn('VNC_ENABLE="${VNC_ENABLE:-false}"', entrypoint)
        self.assertIn('case "${VNC_ENABLE}" in', entrypoint)
        self.assertIn('SWCLID_START_ARGS+=(--visible)', entrypoint)

    def test_cli_entrypoint_starts_once_before_typed_command(self):
        result, calls = self._run_cli_entrypoint()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[0],
            "daemon start --endpoint 127.0.0.1:18495 --startup-timeout 1 --json",
        )
        self.assertEqual(calls[1], "document list --json")
        self.assertNotIn("--attach-existing", calls[0])
        self.assertIn("SWCLI daemon 与 SOLIDWORKS 已就绪", result.stdout)

    def test_cli_entrypoint_adds_visible_only_when_vnc_is_enabled(self):
        result, calls = self._run_cli_entrypoint(vnc_enable="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--visible", calls[0])
        self.assertNotIn("--attach-existing", calls[0])

    def test_cli_entrypoint_surfaces_startup_failure_and_stops(self):
        result, calls = self._run_cli_entrypoint(start_failure=True)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(calls), 1)
        self.assertIn("SWCLI daemon 或 SOLIDWORKS 启动失败", result.stderr)
        self.assertIn("WorkerStartupError", result.stderr)

    def test_cli_entrypoint_rejects_existing_daemon_with_disconnected_host(self):
        result, calls = self._run_cli_entrypoint(host_connected=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("SOLIDWORKS 宿主未连接", result.stderr)
        self.assertIn('"host_connected":false', result.stderr)

    def test_cli_entrypoint_does_not_wait_for_daemon_descendant_stdout(self):
        started_at = time.monotonic()
        result, calls = self._run_cli_entrypoint(hold_start_output=True)
        elapsed = time.monotonic() - started_at
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 2)
        self.assertLess(elapsed, 3.0)

    def _run_cli_entrypoint(
        self,
        *,
        vnc_enable="false",
        start_failure=False,
        hold_start_output=False,
        host_connected=True,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fake_sw_cli = root / "sw-cli"
            call_log = root / "calls.log"
            descendant_pid_file = root / "descendant.pid"
            fake_sw_cli.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$SWCLI_TEST_CALL_LOG\"\n"
                "if [ \"${1:-} ${2:-}\" = 'daemon start' ]; then\n"
                "  if [ \"${SWCLI_TEST_START_FAILURE:-false}\" = true ]; then\n"
                "    printf '%s\\n' "
                "'{\"success\":false,\"error\":{\"code\":\"WorkerStartupError\",\"message\":\"startup failed\"}}'\n"
                "    exit 7\n"
                "  fi\n"
                "  if [ \"${SWCLI_TEST_HOLD_START_OUTPUT:-false}\" = true ]; then\n"
                "    sleep 30 &\n"
                "    printf '%s\\n' \"$!\" > \"$SWCLI_TEST_DESCENDANT_PID_FILE\"\n"
                "  fi\n"
                "  printf '%s\\n' "
                "\"{\\\"success\\\":true,\\\"result\\\":{\\\"started\\\":true,"
                "\\\"health\\\":{\\\"host_connected\\\":${SWCLI_TEST_HOST_CONNECTED}}}}\"\n"
                "fi\n",
                encoding="utf-8",
            )
            fake_sw_cli.chmod(0o755)
            environment = dict(os.environ)
            environment.update(
                {
                    "PATH": f"{root}:{environment['PATH']}",
                    "SOLIDWORKS_INSTALLED": "true",
                    "SWCLID_START_TIMEOUT": "1",
                    "VNC_ENABLE": vnc_enable,
                    "SWCLI_TEST_CALL_LOG": str(call_log),
                    "SWCLI_TEST_START_FAILURE": "true" if start_failure else "false",
                    "SWCLI_TEST_HOLD_START_OUTPUT": "true" if hold_start_output else "false",
                    "SWCLI_TEST_DESCENDANT_PID_FILE": str(descendant_pid_file),
                    "SWCLI_TEST_HOST_CONNECTED": "true" if host_connected else "false",
                }
            )
            try:
                result = subprocess.run(
                    [str(CLI_ENTRYPOINT), "sw-cli", "document", "list", "--json"],
                    capture_output=True,
                    text=True,
                    env=environment,
                    timeout=5.0,
                )
            finally:
                if descendant_pid_file.exists():
                    os.kill(int(descendant_pid_file.read_text()), signal.SIGTERM)
            calls = call_log.read_text(encoding="utf-8").splitlines()
            return result, calls

    def test_delivery_chains_runtime_then_cli_entrypoint(self):
        delivery = (PROJECT_ROOT / "swcli" / "Dockerfile.delivery").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'ENTRYPOINT ["/usr/local/bin/entrypoint.sh", '
            '"/usr/local/bin/entrypoint-cli.sh"]',
            delivery,
        )

if __name__ == "__main__":
    unittest.main()
