import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_STEP = "Smoke test real SOLIDWORKS exports"
GENERIC_STEP = "Smoke test SWCLI modeling & protocol"
DRIVING_STEP = "Smoke test SWCLI driving dimensions"
COLLECT_STEP = "Collect native daemon diagnostics & clean smoke container"
LOCALIZED_STEP = "Smoke test localized SOLIDWORKS images"
PUBLISH_STEP = "Publish verified CLI images & promote atomically"
NATIVE_LOG = "/root/.wine/drive_c/users/root/AppData/Local/SWCLI/logs/daemon.log"
NATIVE_STDERR_DIR = "/ci-smoke/native-runtime-stderr"
NATIVE_STDERR_FIND_ARGS = [
    "-maxdepth",
    "1",
    "-type",
    "f",
    "-name",
    "swclid-start-error.*",
    "-exec",
    "chmod",
    "0644",
    "{}",
    "+",
]
CONTAINER_ID = "d" * 64
CONTAINER_NAME = "sw-cli-export-smoke-fixture-run-2"
EXPORT_NAMES = (
    "bezel moldbase.PDF",
    "bezel moldbase.DWG",
    "bezel moldbase.STEP",
    "cabinet_bath.PDF",
    "cabinet_bath.DWG",
    "Paper Airplane.STEP",
)
PHASES = {
    MAIN_STEP: ("export.sh", "sw-cli-export.log"),
    GENERIC_STEP: ("verify-swcli.sh", "sw-cli-modeling.log"),
    DRIVING_STEP: ("verify-driving.sh", "sw-cli-driving.log"),
}
STATUS_COMMAND = ["sw-cli", "--request-timeout", "2", "daemon", "status", "--json"]


@unittest.skipUnless(
    shutil.which("bash") and shutil.which("jq"),
    "Bash and jq are required for CI evidence tests",
)
class SmokeEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="swcli-ci-evidence-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.workflow = (PROJECT_ROOT / ".github/workflows/build.yml").read_text(
            encoding="utf-8"
        )
        self.trace = self.directory / "commands.jsonl"
        self.runner = self.directory / "runner"
        self.smoke_root = self.runner / "sw-cli-export-smoke"
        self.runtime_stderr_dir = self.smoke_root / "native-runtime-stderr"
        self.runtime_stderr_dir.mkdir(parents=True)
        self.fake_bin = self.directory / "bin"
        self.fake_bin.mkdir()
        executable = f"#!{sys.executable}\n" + textwrap.dedent("""
            import json, os, subprocess, sys
            from pathlib import Path

            role = Path(sys.argv[0]).name
            args = sys.argv[1:]
            trace = Path(os.environ['FAKE_TRACE'])
            with trace.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps([role, *args]) + '\\n')
            calls = [json.loads(line) for line in trace.read_text().splitlines()]
            status = ['sw-cli', '--request-timeout', '2', 'daemon', 'status', '--json']
            probe_count = sum(
                call[:3] == ['docker', 'exec', 'sw-cli-export-smoke-fixture-run-2']
                and call[3:] == status for call in calls
            )
            if role == 'timeout':
                if os.environ.get('FAKE_PROBE_TIMEOUT'):
                    sys.exit(124)
                sys.exit(subprocess.run(args[2:], check=False).returncode)
            if role == 'sleep':
                sys.exit(0)
            if role == 'stat':
                print(Path(args[-1]).stat().st_size)
                sys.exit(0)
            if role == 'sudo':
                runtime = Path(os.environ['RUNNER_TEMP']) / 'sw-cli-export-smoke' / 'native-runtime-stderr'
                expected = ['find', str(runtime), *json.loads(os.environ['FAKE_NATIVE_STDERR_FIND_ARGS'])]
                if args != expected:
                    print('unexpected runtime log permission scope', file=sys.stderr)
                    sys.exit(99)
                sys.exit(subprocess.run(args, check=False).returncode)
            if role == 'chmod':
                if os.environ.get('FAKE_CHMOD_FAILURE') or (
                    os.environ.get('FAKE_NATIVE_STDERR_CHMOD_FAILURE')
                    and any('native-runtime-stderr' in item for item in args[1:])
                ):
                    print('chmod fixture failure', file=sys.stderr)
                    sys.exit(9)
                for target in args[1:]:
                    os.chmod(target, int(args[0], 8))
                sys.exit(0)
            if args[0] == 'inspect':
                if os.environ.get('FAKE_CONTAINER_ABSENT'):
                    sys.exit(1)
                if args[4] == '{{.State.Running}}':
                    stopped = os.environ.get('FAKE_ENTRYPOINT_EXIT') or (
                        os.environ.get('FAKE_EXIT_AFTER_PROBE') and probe_count > 0
                    )
                    print('false' if stopped else 'true')
                elif not os.environ.get('FAKE_CONTAINER_EMPTY_ID'):
                    print('d' * 64)
            elif args[0] == 'logs':
                print('DockerSW entrypoint startup fixture')
                if os.environ.get('FAKE_LOGS_FAILURE'):
                    print('container logs fixture failure', file=sys.stderr)
                    sys.exit(9)
            elif args[0] == 'cp':
                if os.environ.get('FAKE_COPY_FAILURE'):
                    print('daemon.log fixture missing', file=sys.stderr)
                    sys.exit(1)
                destination = Path(args[2])
                destination.write_text('trace:seh native fault fixture\\n', encoding='utf-8')
                destination.chmod(0o600)
            elif args[0] == 'rm':
                if os.environ.get('FAKE_REMOVE_FAILURE'):
                    print('container remove fixture failure', file=sys.stderr)
                    sys.exit(9)
            elif args[0] == 'run':
                if os.environ.get('FAKE_RUN_FAILURE'):
                    print('docker startup fixture failure', file=sys.stderr)
                    sys.exit(23)
                runtime = Path(os.environ['RUNNER_TEMP']) / 'sw-cli-export-smoke' / 'native-runtime-stderr'
                runtime.mkdir(parents=True, exist_ok=True)
                print('d' * 64)
            elif args[0] == 'exec':
                command = args[2:]
                if os.environ.get('FAKE_ENTRYPOINT_EXIT') or (
                    os.environ.get('FAKE_EXIT_AFTER_PROBE') and probe_count > 0
                ):
                    print('container is not running', file=sys.stderr)
                    sys.exit(1)
                if command == status:
                    ready = probe_count > int(os.environ.get('FAKE_READY_AFTER', '0'))
                    health = dict(host_connected=ready, worker_alive=ready,
                                  recovery_required=False, host={'process_id': 608, 'visible': False})
                    kind = os.environ.get('FAKE_HEALTH_KIND')
                    if kind == 'disconnected':
                        health['host_connected'] = False
                    elif kind == 'dead-worker':
                        health['worker_alive'] = False
                    elif kind == 'recovery':
                        health['recovery_required'] = True
                    elif kind == 'missing-host':
                        health['host'] = None
                    elif kind == 'visible-host':
                        health['host']['visible'] = True
                    elif kind == 'missing-visibility':
                        del health['host']['visible']
                    elif kind == 'invalid-json':
                        print('not JSON')
                        sys.exit(0)
                    print(json.dumps(dict(success=kind != 'failed', result=health)))
                    sys.exit(0 if kind != 'failed' else 1)
                script = Path(command[1]).name
                if script == os.environ.get('FAKE_FAIL_SCRIPT'):
                    print(json.dumps(dict(ok=False, error=dict(
                        type='NativeFailure', message=script + ' native failure fixture'
                    ))), file=sys.stderr)
                    sys.exit(int(os.environ.get('FAKE_PHASE_EXIT_CODE', '23')))
                if script == 'export.sh':
                    outdir = Path(os.environ['RUNNER_TEMP']) / 'sw-cli-export-smoke' / 'output'
                    for name in json.loads(os.environ['FAKE_EXPORT_NAMES']):
                        if name != os.environ.get('FAKE_MISSING_EXPORT'):
                            (outdir / name).write_text('export fixture', encoding='utf-8')
                print(script + ' success fixture')
            else:
                sys.exit(99)
            """)
        for name in ("docker", "chmod", "timeout", "sleep", "stat", "sudo"):
            path = self.fake_bin / name
            path.write_text(executable, encoding="utf-8")
            path.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": str(self.fake_bin) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_TRACE": str(self.trace),
            "FAKE_EXPORT_NAMES": json.dumps(EXPORT_NAMES),
            "FAKE_NATIVE_STDERR_FIND_ARGS": json.dumps(NATIVE_STDERR_FIND_ARGS),
            "GITHUB_RUN_ID": "fixture-run",
            "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_WORKSPACE": str(PROJECT_ROOT),
            "RUNNER_TEMP": str(self.runner),
            "SW_EXECUTABLE_CLI_IMAGE": "fixture:cli",
        }

    def step(self, name: str) -> str:
        return self.workflow.split("      - name: " + name + "\n", maxsplit=1)[1].split(
            "\n      - name:", maxsplit=1
        )[0]

    def run_step(
        self, name: str, *, short_startup: bool = False, **environment: str
    ) -> subprocess.CompletedProcess:
        body = textwrap.dedent(self.step(name).split("        run: |\n", maxsplit=1)[1])
        if short_startup:
            # Run the production deadline loop with a short fixture budget.
            self.assertIn("startup_deadline=$((SECONDS + 300))", body)
            body = body.replace(
                "startup_deadline=$((SECONDS + 300))",
                "startup_deadline=$((SECONDS + 2))",
            )
        return subprocess.run(
            ["bash", "-c", body],
            env={**self.environment, **environment},
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def calls(self, role: str = None) -> list:
        if not self.trace.exists():
            return []
        calls = [
            json.loads(line)
            for line in self.trace.read_text(encoding="utf-8").splitlines()
        ]
        return [call for call in calls if role is None or call[0] == role]

    def business_calls(self) -> list:
        return [
            call
            for call in self.calls("docker")
            if call[1] == "exec" and call[3] == "bash"
        ]

    def test_three_phase_budgets_guards_and_final_collection(self) -> None:
        for name in PHASES:
            with self.subTest(phase=name):
                step = self.step(name)
                self.assertIn("timeout-minutes: 10", step)
                self.assertIn("if: success() &&", step)
                self.assertNotIn("continue-on-error", step)
                self.assertNotIn("timeout-minutes: 30", step)
        self.assertIn(
            "steps.smoke-exports.outcome == 'success'", self.step(GENERIC_STEP)
        )
        self.assertIn(
            "steps.smoke-generic.outcome == 'success'", self.step(DRIVING_STEP)
        )
        for name in (LOCALIZED_STEP, PUBLISH_STEP):
            self.assertIn(
                "if: success() && steps.smoke-driving.outcome == 'success'",
                self.step(name),
            )
        collector = self.step(COLLECT_STEP)
        self.assertIn(
            "if: always() && steps.check-images.outputs.already_verified != 'true'",
            collector,
        )
        names = [
            *PHASES,
            COLLECT_STEP,
            LOCALIZED_STEP,
            PUBLISH_STEP,
            "Unmount installation media",
            "Upload export smoke-test artifacts",
        ]
        positions = [
            self.workflow.index("      - name: " + name + "\n") for name in names
        ]
        self.assertEqual(positions, sorted(positions))

    def test_one_resident_container_complete_mounts_and_unchanged_host_variables(
        self,
    ) -> None:
        main = self.step(MAIN_STEP)
        self.assertIn("docker run -d \\\n", main)
        self.assertNotIn("docker run --rm", main)
        self.assertIn("sleep infinity", main)
        self.assertIn("--env 'WINEDEBUG=-all,+seh,+loaddll'", main)
        self.assertIn("--env SWCLID_VISIBLE=false", main)
        self.assertNotIn("--env SWCLID_VISIBLE=true", main)
        self.assertIn("--env SWCLID_RUNTIME_LOG_DIR=" + NATIVE_STDERR_DIR, main)
        self.assertIn("--env SW_SMOKE_EVIDENCE_DIR=/ci-smoke", main)
        self.assertNotIn("VNC_ENABLE", main)
        for script, _ in PHASES.values():
            self.assertIn(
                "smoke-test/"
                + script
                + ",target=/opt/dockersw-smoke/"
                + script
                + ",readonly",
                main,
            )
        for name in (GENERIC_STEP, DRIVING_STEP):
            self.assertNotIn("docker run", self.step(name))
        localized = self.step(LOCALIZED_STEP)
        self.assertIn("docker run --rm", localized)
        self.assertNotIn("WINEDEBUG", localized)
        self.assertIn(
            "ENV WINEDEBUG=-all", (PROJECT_ROOT / "runtime/Dockerfile").read_text()
        )
        self.assertIn(
            "${WINEDEBUG:--all}",
            (PROJECT_ROOT / "runtime/entrypoint.sh").read_text(),
        )

    def test_real_wrapper_routes_the_readiness_probe_to_linux_python(self) -> None:
        linux_python = self.fake_bin / "python3"
        linux_python.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            "print(json.dumps(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        linux_python.chmod(0o755)
        for name in ("wine", "winepath"):
            forbidden = self.fake_bin / name
            forbidden.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
            forbidden.chmod(0o755)
        completed = subprocess.run(
            ["bash", str(PROJECT_ROOT / "swcli/bin/sw-cli"), *STATUS_COMMAND[1:]],
            env=self.environment,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout), ["-m", "swcli", *STATUS_COMMAND[1:]]
        )

    def test_successful_phases_share_container_without_daemon_restart(self) -> None:
        main_stdout = ""
        for name in PHASES:
            completed = self.run_step(name)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            if name == MAIN_STEP:
                main_stdout = completed.stdout
            self.assertTrue((self.smoke_root / PHASES[name][1]).is_file())
        calls = self.calls("docker")
        runs = [call for call in calls if call[1] == "run"]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0][-2:], ["sleep", "infinity"])
        self.assertEqual(
            self.business_calls(),
            [
                [
                    "docker",
                    "exec",
                    CONTAINER_NAME,
                    "bash",
                    "/opt/dockersw-smoke/export.sh",
                ],
                [
                    "docker",
                    "exec",
                    CONTAINER_NAME,
                    "bash",
                    "/opt/dockersw-smoke/verify-swcli.sh",
                    "/root/.wine/drive_c",
                    "/ci-smoke/modeling",
                ],
                [
                    "docker",
                    "exec",
                    CONTAINER_NAME,
                    "bash",
                    "/opt/dockersw-smoke/verify-driving.sh",
                    "/ci-smoke/modeling/modeling.json",
                ],
            ],
        )
        self.assertEqual(
            sorted(path.name for path in (self.smoke_root / "output").iterdir()),
            sorted(EXPORT_NAMES),
        )
        self.assertIn("6 files verified", main_stdout)
        status = json.loads((self.smoke_root / "startup-status.json").read_text())
        self.assertEqual(status["result"]["host"]["process_id"], 608)
        self.assertFalse(
            any(
                "restart" in call or "start" in call or "stop" in call for call in calls
            )
        )

    def test_bounded_json_readiness_never_runs_business_before_ready(self) -> None:
        completed = self.run_step(MAIN_STEP, FAKE_READY_AFTER="2")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = self.calls("docker")
        probes = [
            index
            for index, call in enumerate(calls)
            if call[1] == "exec" and call[3] == "sw-cli"
        ]
        business = [
            index
            for index, call in enumerate(calls)
            if call[1] == "exec" and call[3] == "bash"
        ]
        self.assertEqual(len(probes), 3)
        self.assertLess(probes[-1], business[0])
        self.assertTrue(
            all(call[1].startswith("--kill-after=") for call in self.calls("timeout"))
        )
        self.assertNotIn("test -f", self.step(MAIN_STEP))

    def test_unready_or_invalid_health_cannot_pass_startup(self) -> None:
        for kind in (
            "disconnected",
            "dead-worker",
            "recovery",
            "missing-host",
            "visible-host",
            "missing-visibility",
            "invalid-json",
            "failed",
        ):
            with self.subTest(kind=kind):
                self.trace.write_text("", encoding="utf-8")
                completed = self.run_step(
                    MAIN_STEP, short_startup=True, FAKE_HEALTH_KIND=kind
                )
                self.assertEqual(completed.returncode, 1)
                self.assertIn("did not become healthy", completed.stderr)
                self.assertEqual(self.business_calls(), [])
                self.assertTrue((self.smoke_root / "startup-status.json").exists())
                self.assertTrue((self.smoke_root / "startup-probe.log").exists())

    def test_entrypoint_exit_fails_immediately_and_retains_startup_log(self) -> None:
        for environment in (
            {"FAKE_ENTRYPOINT_EXIT": "1"},
            {"FAKE_HEALTH_KIND": "disconnected", "FAKE_EXIT_AFTER_PROBE": "1"},
        ):
            with self.subTest(environment=environment):
                self.trace.write_text("", encoding="utf-8")
                completed = self.run_step(MAIN_STEP, **environment)
                self.assertEqual(completed.returncode, 1)
                self.assertIn("entrypoint exited", completed.stderr)
                self.assertEqual(self.business_calls(), [])
                collected = self.run_step(COLLECT_STEP)
                self.assertEqual(collected.returncode, 0, collected.stderr)
                self.assertIn(
                    "entrypoint startup fixture",
                    (self.smoke_root / "startup.log").read_text(),
                )
                self.assertEqual(
                    self.calls("docker")[-1], ["docker", "rm", "-f", CONTAINER_ID]
                )

    def test_probe_and_launch_failures_never_execute_exports(self) -> None:
        timed = self.run_step(MAIN_STEP, short_startup=True, FAKE_PROBE_TIMEOUT="1")
        self.assertEqual(timed.returncode, 1)
        self.assertEqual(self.business_calls(), [])
        self.trace.write_text("", encoding="utf-8")
        launched = self.run_step(MAIN_STEP, FAKE_RUN_FAILURE="1")
        self.assertEqual(launched.returncode, 23)
        self.assertIn("docker startup fixture failure", launched.stderr)
        self.assertEqual(self.business_calls(), [])

    def test_each_phase_preserves_its_failure_code_and_log_after_collection(
        self,
    ) -> None:
        for failed_phase, (script, log_name) in PHASES.items():
            with self.subTest(phase=failed_phase):
                self.trace.write_text("", encoding="utf-8")
                for phase in PHASES:
                    completed = self.run_step(
                        phase, FAKE_FAIL_SCRIPT=script, FAKE_PHASE_EXIT_CODE="37"
                    )
                    if phase == failed_phase:
                        self.assertEqual(completed.returncode, 37)
                        break
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("NativeFailure", (self.smoke_root / log_name).read_text())
                collected = self.run_step(COLLECT_STEP)
                self.assertEqual(collected.returncode, 0)
                self.assertEqual(completed.returncode, 37)
                self.assertTrue((self.smoke_root / "startup.log").is_file())
                self.assertTrue((self.smoke_root / "daemon.log").is_file())
                self.assertEqual(
                    self.calls("docker")[-1], ["docker", "rm", "-f", CONTAINER_ID]
                )

    def test_missing_export_still_fails_the_original_six_file_gate(self) -> None:
        completed = self.run_step(MAIN_STEP, FAKE_MISSING_EXPORT="cabinet_bath.DWG")
        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "Expected export is missing or empty: cabinet_bath.DWG", completed.stderr
        )

    def test_collects_readable_startup_and_native_log_before_exact_cleanup(
        self,
    ) -> None:
        completed = self.run_step(COLLECT_STEP)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        daemon_log = self.smoke_root / "daemon.log"
        startup_log = self.smoke_root / "startup.log"
        self.assertEqual(daemon_log.read_text(), "trace:seh native fault fixture\n")
        self.assertIn("entrypoint startup fixture", startup_log.read_text())
        for path in (startup_log, daemon_log):
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
        self.assertEqual(
            self.calls(),
            [
                [
                    "docker",
                    "inspect",
                    "--type",
                    "container",
                    "--format",
                    "{{.Id}}",
                    CONTAINER_NAME,
                ],
                ["docker", "logs", "--timestamps", CONTAINER_ID],
                ["chmod", "0644", str(startup_log)],
                ["docker", "cp", CONTAINER_ID + ":" + NATIVE_LOG, str(daemon_log)],
                ["chmod", "0644", str(daemon_log)],
                ["sudo", "find", str(self.runtime_stderr_dir), *NATIVE_STDERR_FIND_ARGS],
                ["docker", "rm", "-f", CONTAINER_ID],
            ],
        )
        self.assertNotIn("::warning::", completed.stdout)

    def test_bound_native_stderr_becomes_readable_without_losing_background_writes(
        self,
    ) -> None:
        native_stderr = self.runtime_stderr_dir / "swclid-start-error.fixture"
        native_stderr.write_text("startup native stderr fixture\n", encoding="utf-8")
        native_stderr.chmod(0o600)
        with native_stderr.open("ab") as stream:
            writer = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdin.read(1); "
                    "sys.stderr.write('trace:seh background native fault fixture\\n'); "
                    "sys.stderr.flush()",
                ],
                stdin=subprocess.PIPE,
                stderr=stream,
                text=True,
            )
        try:
            completed = self.run_step(COLLECT_STEP)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn("::warning::", completed.stdout)
            self.assertEqual(native_stderr.stat().st_mode & 0o777, 0o644)
            writer.communicate("x", timeout=5)
            self.assertEqual(writer.returncode, 0)
            self.assertEqual(
                native_stderr.read_text(encoding="utf-8"),
                "startup native stderr fixture\n"
                "trace:seh background native fault fixture\n",
            )
        finally:
            if writer.poll() is None:
                writer.kill()
                writer.communicate(timeout=5)
        calls = self.calls()
        permission_call = [
            "sudo", "find", str(self.runtime_stderr_dir), *NATIVE_STDERR_FIND_ARGS
        ]
        cleanup_call = ["docker", "rm", "-f", CONTAINER_ID]
        self.assertIn(permission_call, calls)
        self.assertLess(calls.index(permission_call), calls.index(cleanup_call))
        self.assertEqual(calls[-1], cleanup_call)
        self.assertFalse(any("cp" in call and NATIVE_STDERR_DIR in str(call) for call in calls))

    def test_stopped_startup_container_still_retains_readable_native_stderr(
        self,
    ) -> None:
        failed_startup = self.run_step(MAIN_STEP, FAKE_ENTRYPOINT_EXIT="1")
        self.assertEqual(failed_startup.returncode, 1)
        self.assertIn("entrypoint exited", failed_startup.stderr)
        native_stderr = self.runtime_stderr_dir / "swclid-start-error.failed-startup"
        native_stderr.write_text("native startup failure fixture\n", encoding="utf-8")
        native_stderr.chmod(0o600)
        completed = self.run_step(COLLECT_STEP, FAKE_ENTRYPOINT_EXIT="1")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("::warning::", completed.stdout)
        self.assertEqual(native_stderr.stat().st_mode & 0o777, 0o644)
        self.assertEqual(native_stderr.read_text(), "native startup failure fixture\n")
        self.assertEqual(failed_startup.returncode, 1)
        self.assertFalse(any(call[1] == "exec" for call in self.calls("docker")))
        self.assertEqual(self.calls("docker")[-1], ["docker", "rm", "-f", CONTAINER_ID])

    def test_runtime_permissions_touch_only_matching_direct_regular_files(self) -> None:
        matched = self.runtime_stderr_dir / "swclid-start-error.first"
        matched_second = self.runtime_stderr_dir / "swclid-start-error.second"
        unrelated = self.runtime_stderr_dir / "unrelated.log"
        nested = self.runtime_stderr_dir / "nested" / "swclid-start-error.nested"
        nested.parent.mkdir()
        external = self.directory / "swclid-start-error.external"
        for target in (matched, matched_second, unrelated, nested, external):
            target.write_text(target.name, encoding="utf-8")
            target.chmod(0o600)
        link = self.runtime_stderr_dir / "swclid-start-error.link"
        link.symlink_to(external)
        matching_directory = self.runtime_stderr_dir / "swclid-start-error.directory"
        matching_directory.mkdir(mode=0o700)
        completed = self.run_step(COLLECT_STEP)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("::warning::", completed.stdout)
        for target in (matched, matched_second):
            self.assertEqual(target.stat().st_mode & 0o777, 0o644)
        for target in (unrelated, nested, external):
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertTrue(link.is_symlink())
        self.assertEqual(matching_directory.stat().st_mode & 0o777, 0o700)

    def test_native_stderr_permission_failure_warns_and_preserves_gate_failure(
        self,
    ) -> None:
        failed_gate = self.run_step(
            MAIN_STEP, FAKE_FAIL_SCRIPT="export.sh", FAKE_PHASE_EXIT_CODE="37"
        )
        self.assertEqual(failed_gate.returncode, 37)
        native_stderr = self.runtime_stderr_dir / "swclid-start-error.fixture"
        native_stderr.write_text("retained native fault fixture\n", encoding="utf-8")
        native_stderr.chmod(0o600)
        completed = self.run_step(COLLECT_STEP, FAKE_NATIVE_STDERR_CHMOD_FAILURE="1")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Could not make native runtime stderr readable", completed.stdout)
        self.assertIn("chmod fixture failure", completed.stderr)
        self.assertEqual(native_stderr.stat().st_mode & 0o777, 0o600)
        self.assertEqual(native_stderr.read_text(), "retained native fault fixture\n")
        self.assertEqual(failed_gate.returncode, 37)
        self.assertEqual(self.calls("docker")[-1], ["docker", "rm", "-f", CONTAINER_ID])

    def test_missing_native_stderr_directory_warns_and_still_cleans_exact_container(
        self,
    ) -> None:
        self.runtime_stderr_dir.rmdir()
        completed = self.run_step(COLLECT_STEP)
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Could not make native runtime stderr readable", completed.stdout)
        self.assertEqual(self.calls("docker")[-1], ["docker", "rm", "-f", CONTAINER_ID])

    def test_missing_or_unreadable_logs_warn_but_cleanup_continues(self) -> None:
        for option, diagnostic in (
            ("FAKE_COPY_FAILURE", "daemon.log fixture missing"),
            ("FAKE_LOGS_FAILURE", "container logs fixture failure"),
            ("FAKE_CHMOD_FAILURE", "chmod fixture failure"),
        ):
            with self.subTest(option=option):
                self.trace.write_text("", encoding="utf-8")
                completed = self.run_step(COLLECT_STEP, **{option: "1"})
                self.assertEqual(completed.returncode, 0)
                self.assertIn("::warning::", completed.stdout)
                diagnostics = (
                    completed.stderr + (self.smoke_root / "startup.log").read_text()
                )
                self.assertIn(diagnostic, diagnostics)
                self.assertEqual(
                    self.calls("docker")[-1], ["docker", "rm", "-f", CONTAINER_ID]
                )

    def test_absent_or_empty_container_id_never_targets_another_container(self) -> None:
        for option in ("FAKE_CONTAINER_ABSENT", "FAKE_CONTAINER_EMPTY_ID"):
            with self.subTest(option=option):
                self.trace.write_text("", encoding="utf-8")
                completed = self.run_step(COLLECT_STEP, **{option: "1"})
                self.assertEqual(completed.returncode, 0)
                self.assertIn(
                    "is unavailable; native daemon log was not collected",
                    completed.stdout,
                )
                self.assertEqual(len(self.calls()), 1)
                self.assertEqual(self.calls()[0][1], "inspect")

    def test_removal_failure_is_warning_not_a_new_step_failure(self) -> None:
        completed = self.run_step(COLLECT_STEP, FAKE_REMOVE_FAILURE="1")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Could not clean smoke container", completed.stdout)
        self.assertIn(CONTAINER_ID, completed.stdout)
        self.assertIn("container remove fixture failure", completed.stderr)


if __name__ == "__main__":
    unittest.main()
