import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = PROJECT_ROOT / "smoke-test/verify-swcli.sh"


@unittest.skipUnless(shutil.which("bash"), "Bash is required for smoke diagnostics")
class SmokeDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="swcli-smoke-diagnostics-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.script = VERIFY_SCRIPT.read_text(encoding="utf-8")
        self.failure = json.dumps(
            {
                "ok": False,
                "action": "document.create",
                "error": {
                    "type": "NativeFailure",
                    "message": "native failure reason from the requested source",
                },
            }
        )
        fake_cli = self.directory / "sw-cli"
        fake_cli.write_text(
            f"#!{sys.executable}\n"
            "import os, sys\n"
            "if sys.argv[1:] == ['capabilities', '--json']:\n"
            "    print('{\"ok\": true}')\n"
            "    sys.exit(0)\n"
            "sys.stdout.write(os.environ['FAKE_STDOUT'])\n"
            "sys.stderr.write(os.environ.get('FAKE_STDERR', ''))\n"
            "sys.exit(int(os.environ['FAKE_EXIT_CODE']))\n",
            encoding="utf-8",
        )
        fake_cli.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": str(self.directory) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_STDOUT": self.failure + "\n",
            "FAKE_STDERR": "native stderr diagnostic\n",
            "FAKE_EXIT_CODE": "23",
        }

    def run_helper(self, command: str, **environment: str) -> subprocess.CompletedProcess:
        # Exercise the actual helper with Bash and a fake executable, not a
        # Python equivalent of the command-substitution behavior.
        helper_script = self.directory / "capture-test.sh"
        helper_script.write_text(
            self.script.split('workspace="', maxsplit=1)[0] + command + "\n",
            encoding="utf-8",
        )
        return subprocess.run(
            ["bash", str(helper_script)],
            env={**self.environment, **environment},
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def test_full_smoke_retains_failed_json_and_original_exit_code(self) -> None:
        completed = subprocess.run(
            ["bash", str(VERIFY_SCRIPT), "/workspace/Wine drive C"],
            env=self.environment,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 23)
        self.assertIn('"ok": true', completed.stdout)
        self.assertNotIn("NativeFailure", completed.stdout)
        self.assertIn(str(VERIFY_SCRIPT), completed.stderr)
        self.assertRegex(completed.stderr, r":\d+ failed \(exit 23\):")
        self.assertIn("sw-cli document create --type part --json", completed.stderr)
        self.assertIn(self.failure, completed.stderr)
        self.assertIn("native stderr diagnostic", completed.stderr)

    def test_success_returns_only_original_json_and_keeps_stderr(self) -> None:
        payload = '{\n  "ok": true,\n  "path": "/workspace/a file.STEP"\n}\n'
        completed = self.run_helper(
            'capture_json sw-cli document export "/workspace/a file.STEP" --json',
            FAKE_STDOUT=payload,
            FAKE_EXIT_CODE="0",
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, payload)
        self.assertEqual(completed.stderr, "native stderr diagnostic\n")

    def test_failed_capture_reports_exact_call_and_source_without_stdout(self) -> None:
        completed = self.run_helper(
            'value="$(capture_json sw-cli document export "/workspace/a file.STEP" --json)"\n'
            'printf "%s\\n" "${value}"',
            FAKE_EXIT_CODE="7",
        )
        self.assertEqual(completed.returncode, 7)
        self.assertEqual(completed.stdout, "")
        self.assertIn("capture-test.sh:", completed.stderr)
        self.assertIn("failed (exit 7)", completed.stderr)
        self.assertIn("sw-cli document export /workspace/a\\ file.STEP --json", completed.stderr)
        self.assertIn(self.failure, completed.stderr)

    def test_failure_without_json_still_reports_original_exit_code_and_call(self) -> None:
        completed = self.run_helper(
            "capture_json sw-cli document create --json",
            FAKE_STDOUT="",
            FAKE_EXIT_CODE="2",
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("failed (exit 2): sw-cli document create --json", completed.stderr)
        self.assertIn("native stderr diagnostic", completed.stderr)

    def test_only_intentional_rejections_bypass_capture(self) -> None:
        unwrapped = [
            line.strip()
            for line in self.script.splitlines()
            if re.search(r'="\$\(sw-cli\b', line)
        ]
        self.assertEqual(len(unwrapped), 3)
        self.assertTrue(all(line.startswith("if ") for line in unwrapped))
        self.assertIn('if conflict_json="$(sw-cli --session smoke-contender', self.script)
        self.assertNotIn('if denied_json="$(capture_json ', self.script)
        self.assertNotIn('if conflict_json="$(capture_json ', self.script)


if __name__ == "__main__":
    unittest.main()
