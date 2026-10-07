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
COLLECT_STEP = "Collect native daemon diagnostics & clean smoke container"
LOCALIZED_STEP = "Smoke test localized SOLIDWORKS images"
NATIVE_LOG = "/root/.wine/drive_c/users/root/AppData/Local/SWCLI/logs/daemon.log"
CONTAINER_ID = "d" * 64


@unittest.skipUnless(shutil.which("bash"), "Bash is required for CI evidence tests")
class SmokeEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="swcli-ci-evidence-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.workflow = (PROJECT_ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.trace = self.directory / "commands.jsonl"
        self.runner = self.directory / "runner"
        self.smoke_root = self.runner / "sw-cli-export-smoke"
        self.fake_bin = self.directory / "bin"
        self.fake_bin.mkdir()
        executable = f"#!{sys.executable}\n" + textwrap.dedent(
            """
            import json, os, sys
            from pathlib import Path
            role = Path(sys.argv[0]).name
            args = sys.argv[1:]
            with open(os.environ['FAKE_TRACE'], 'a', encoding='utf-8') as stream:
                stream.write(json.dumps([role, *args]) + '\\n')
            if role == 'chmod':
                if os.environ.get('FAKE_CHMOD_FAILURE'):
                    print('chmod fixture failure', file=sys.stderr)
                    sys.exit(9)
                os.chmod(args[1], int(args[0], 8))
            elif args[0] == 'inspect':
                if os.environ.get('FAKE_CONTAINER_ABSENT'):
                    sys.exit(1)
                if not os.environ.get('FAKE_CONTAINER_EMPTY_ID'):
                    print('d' * 64)
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
                print('InsertSketch native failure fixture', file=sys.stderr)
                sys.exit(23)
            else:
                sys.exit(99)
            """
        )
        for name in ("docker", "chmod"):
            path = self.fake_bin / name
            path.write_text(executable, encoding="utf-8")
            path.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": str(self.fake_bin) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_TRACE": str(self.trace),
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

    def run_step(self, name: str, **environment: str) -> subprocess.CompletedProcess:
        body = textwrap.dedent(self.step(name).split("        run: |\n", maxsplit=1)[1])
        return subprocess.run(
            ["bash", "-c", body],
            env={**self.environment, **environment},
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def calls(self) -> list:
        return [json.loads(line) for line in self.trace.read_text(encoding="utf-8").splitlines()]

    def test_trace_and_retention_are_ci_only_and_collection_precedes_cleanup_upload(self) -> None:
        main = self.step(MAIN_STEP)
        collector = self.step(COLLECT_STEP)
        localized = self.step(LOCALIZED_STEP)
        self.assertIn("timeout-minutes: 10", main)
        self.assertIn("docker run \\\n", main)
        self.assertNotIn("docker run --rm", main)
        self.assertIn("--env 'WINEDEBUG=-all,+seh,+loaddll'", main)
        self.assertIn("--env SWCLID_VISIBLE=true", main)
        self.assertNotIn("VNC_ENABLE", main)
        self.assertIn("if: always() && steps.check-images.outputs.already_verified != 'true'", collector)
        self.assertIn("docker run --rm", localized)
        self.assertNotIn("WINEDEBUG", localized)
        self.assertIn("ENV WINEDEBUG=-all", (PROJECT_ROOT / "runtime/Dockerfile").read_text())
        self.assertIn('${WINEDEBUG:--all}', (PROJECT_ROOT / "runtime/entrypoint.sh").read_text())
        names = [
            MAIN_STEP,
            COLLECT_STEP,
            LOCALIZED_STEP,
            "Unmount installation media",
            "Upload export smoke-test artifacts",
        ]
        positions = [self.workflow.index("      - name: " + name + "\n") for name in names]
        self.assertEqual(positions, sorted(positions))

    def test_collects_readable_log_then_removes_resolved_container_id(self) -> None:
        completed = self.run_step(COLLECT_STEP)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        log_path = self.smoke_root / "daemon.log"
        self.assertEqual(log_path.read_text(), "trace:seh native fault fixture\n")
        self.assertEqual(log_path.stat().st_mode & 0o777, 0o644)
        self.assertEqual(
            self.calls(),
            [
                ["docker", "inspect", "--type", "container", "--format", "{{.Id}}", "sw-cli-export-smoke-fixture-run-2"],
                ["docker", "cp", CONTAINER_ID + ":" + NATIVE_LOG, str(log_path)],
                ["chmod", "0644", str(log_path)],
                ["docker", "rm", "-f", CONTAINER_ID],
            ],
        )
        self.assertNotIn("::warning::", completed.stdout)

    def test_missing_log_warns_and_still_removes_exact_container(self) -> None:
        completed = self.run_step(COLLECT_STEP, FAKE_COPY_FAILURE="1")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("::warning::", completed.stdout)
        self.assertIn(NATIVE_LOG, completed.stdout)
        self.assertIn("daemon.log fixture missing", completed.stderr)
        self.assertEqual([call[1] for call in self.calls()], ["inspect", "cp", "rm"])
        self.assertEqual(self.calls()[-1], ["docker", "rm", "-f", CONTAINER_ID])

    def test_unreadable_copy_warns_and_still_removes_exact_container(self) -> None:
        completed = self.run_step(COLLECT_STEP, FAKE_CHMOD_FAILURE="1")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Could not collect a readable daemon log", completed.stdout)
        self.assertIn("chmod fixture failure", completed.stderr)
        self.assertEqual(self.calls()[-1], ["docker", "rm", "-f", CONTAINER_ID])

    def test_absent_or_empty_container_id_never_targets_another_container(self) -> None:
        for option in ("FAKE_CONTAINER_ABSENT", "FAKE_CONTAINER_EMPTY_ID"):
            with self.subTest(option=option):
                self.trace.write_text("", encoding="utf-8")
                completed = self.run_step(COLLECT_STEP, **{option: "1"})
                self.assertEqual(completed.returncode, 0)
                self.assertIn("is unavailable; native daemon log was not collected", completed.stdout)
                self.assertEqual(len(self.calls()), 1)
                self.assertEqual(self.calls()[0][1], "inspect")

    def test_removal_failure_is_warning_not_a_new_step_failure(self) -> None:
        completed = self.run_step(COLLECT_STEP, FAKE_REMOVE_FAILURE="1")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Could not clean smoke container", completed.stdout)
        self.assertIn(CONTAINER_ID, completed.stdout)
        self.assertIn("container remove fixture failure", completed.stderr)

    def test_original_smoke_exit_code_survives_diagnostic_collection(self) -> None:
        smoke = self.run_step(MAIN_STEP)
        self.assertEqual(smoke.returncode, 23)
        self.assertIn("InsertSketch native failure fixture", smoke.stdout)
        collected = self.run_step(COLLECT_STEP)
        self.assertEqual(collected.returncode, 0)
        self.assertEqual(smoke.returncode, 23)
        self.assertTrue((self.smoke_root / "sw-cli-export.log").is_file())
        self.assertTrue((self.smoke_root / "daemon.log").is_file())


if __name__ == "__main__":
    unittest.main()
