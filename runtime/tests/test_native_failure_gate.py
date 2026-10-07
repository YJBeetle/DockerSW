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
VERIFY_SCRIPT = PROJECT_ROOT / "smoke-test/verify-swcli.sh"
FAILURE_START = "# Native rejection is also evidence:"
FAILURE_END = '\nsw-cli document inspect --json | jq -e --arg id "${created_b_id}"'
FINAL_START = "# Check the native open-document list,"


@unittest.skipUnless(
    shutil.which("bash") and shutil.which("jq"),
    "Bash and jq are required for native failure gate tests",
)
class NativeFailureGateTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="swcli-native-failure-gate-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.source = VERIFY_SCRIPT.read_text(encoding="utf-8")
        self.trace = self.directory / "calls.jsonl"
        self.denied = {
            "ok": False,
            "action": "feature.cut-extrude",
            "error": {"type": "CutExtrusionFailed", "message": "native cut rejected"},
        }
        self.document = {
            "ok": True,
            "action": "document.inspect",
            "document": {"document_id": "d-first", "title": "Rejected cut part"},
            "needs_rebuild": 0,
        }
        self.sketch = {"ok": True, "action": "sketch.inspect", "editing": False}
        self.documents = {
            "ok": True,
            "action": "document.list",
            "count": 0,
            "documents": [],
            "current_document_id": None,
        }
        executable = f"#!{sys.executable}\n" + textwrap.dedent("""
            import json, os, sys
            from pathlib import Path

            args = sys.argv[1:]
            with Path(os.environ['FAKE_TRACE']).open('a') as stream:
                stream.write(json.dumps(args) + '\\n')
            if args[:2] == ['--session', 'smoke-cut-failure']:
                args = args[2:]
            if args[:2] in (['sketch', 'rectangle'], ['sketch', 'circle']):
                result = {'ok': True, 'sketch': {'sketch_id': 's-first'}}
            elif args[:2] == ['feature', 'cut-extrude']:
                result = json.loads(os.environ['FAKE_DENIED'])
                print(json.dumps(result))
                sys.exit(int(os.environ.get('FAKE_CUT_EXIT', '1')))
            elif args[:2] == ['document', 'inspect']:
                result = json.loads(os.environ['FAKE_DOCUMENT'])
            elif args[:2] == ['sketch', 'inspect']:
                result = json.loads(os.environ['FAKE_SKETCH'])
            elif args[:2] == ['document', 'list']:
                result = json.loads(os.environ['FAKE_DOCUMENTS'])
            elif args[:2] == ['document', 'measure']:
                result = {'ok': True, 'metrics': {'solid_body_count': 1, 'volume_mm3': 12000}}
            else:
                result = {'ok': True}
            print(json.dumps(result))
            if args[:2] == ['sketch', 'inspect']:
                sys.exit(int(os.environ.get('FAKE_SKETCH_EXIT', '0')))
            """)
        fake_cli = self.directory / "sw-cli"
        fake_cli.write_text(executable, encoding="utf-8")
        fake_cli.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": str(self.directory) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_TRACE": str(self.trace),
            "FAKE_DENIED": json.dumps(self.denied),
            "FAKE_DOCUMENT": json.dumps(self.document),
            "FAKE_SKETCH": json.dumps(self.sketch),
            "FAKE_DOCUMENTS": json.dumps(self.documents),
        }

    def run_gate(self, *, final: bool = False, **environment: str):
        helper = self.source.split('workspace="', maxsplit=1)[0]
        if final:
            fragment = FINAL_START + self.source.split(FINAL_START, maxsplit=1)[1]
        else:
            fragment = FAILURE_START + self.source.split(
                FAILURE_START, maxsplit=1
            )[1].split(FAILURE_END, maxsplit=1)[0]
        script = self.directory / "native-failure-gate.sh"
        script.write_text(helper + "\n" + fragment, encoding="utf-8")
        return subprocess.run(
            ["bash", str(script)],
            env={**self.environment, **environment},
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def calls(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def test_native_rejection_checks_read_only_state_before_measure_and_close(self):
        completed = self.run_gate()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = self.calls()
        self.assertEqual(
            [call[2:4] for call in calls],
            [
                ["document", "create"],
                ["sketch", "rectangle"],
                ["feature", "extrude"],
                ["sketch", "circle"],
                ["feature", "cut-extrude"],
                ["document", "inspect"],
                ["sketch", "inspect"],
                ["document", "measure"],
                ["document", "close"],
            ],
        )
        self.assertTrue(
            all(call[:2] == ["--session", "smoke-cut-failure"] for call in calls)
        )
        self.assertIn("s-first", calls[6])
        self.assertIn("--discard", calls[-1])
        self.assertIn(json.dumps(self.document), completed.stdout)
        self.assertIn(json.dumps(self.sketch), completed.stdout)
        self.assertNotIn("native cut rejected", completed.stdout)
        self.assertNotIn("restart", str(calls))

    def test_cleanup_warning_fails_before_any_followup_native_operation(self):
        for code in ("selection-cleanup-failed", "sketch-cleanup-failed"):
            with self.subTest(code=code):
                self.trace.write_text("")
                denied = {
                    **self.denied,
                    "warnings": [{"code": code, "message": "state not restored"}],
                }
                completed = self.run_gate(FAKE_DENIED=json.dumps(denied))
                self.assertEqual(completed.returncode, 1)
                self.assertIn(code, completed.stderr)
                self.assertIn("state not restored", completed.stderr)
                self.assertIn("CutExtrusionFailed", completed.stderr)
                self.assertEqual(self.calls()[-1][2:4], ["feature", "cut-extrude"])

    def test_active_missing_or_null_edit_state_cannot_pass(self):
        for editing in (True, None, "false", 0, "missing"):
            with self.subTest(editing=editing):
                self.trace.write_text("")
                sketch = dict(self.sketch)
                if editing == "missing":
                    sketch.pop("editing")
                else:
                    sketch["editing"] = editing
                completed = self.run_gate(FAKE_SKETCH=json.dumps(sketch))
                self.assertEqual(completed.returncode, 1)
                self.assertIn("editing active or unknown", completed.stderr)
                self.assertIn(json.dumps(sketch), completed.stderr)
                self.assertIn("Rejected cut part", completed.stderr)
                self.assertEqual(self.calls()[-1][2:4], ["sketch", "inspect"])

    def test_inspection_command_failure_keeps_its_json_and_exit_status(self):
        sketch = {
            "ok": False,
            "error": {"type": "ObservationUnavailable", "message": "COM failed"},
        }
        completed = self.run_gate(
            FAKE_SKETCH=json.dumps(sketch), FAKE_SKETCH_EXIT="23"
        )
        self.assertEqual(completed.returncode, 23)
        self.assertIn("COM failed", completed.stderr)
        self.assertIn("ObservationUnavailable", completed.stderr)
        self.assertIn("sketch inspect s-first --json", completed.stderr)
        self.assertEqual(self.calls()[-1][2:4], ["sketch", "inspect"])

    def test_unavailable_document_state_fails_before_sketch_inspection(self):
        document = {
            "ok": False,
            "error": {"type": "ObservationUnavailable", "message": "document unreadable"},
        }
        completed = self.run_gate(FAKE_DOCUMENT=json.dumps(document))
        self.assertEqual(completed.returncode, 1)
        self.assertIn("document state is unavailable", completed.stderr)
        self.assertIn(json.dumps(document), completed.stderr)
        self.assertEqual(self.calls()[-1][2:4], ["document", "inspect"])

    def test_successful_native_cut_cannot_replace_the_expected_rejection(self):
        completed = self.run_gate(FAKE_DENIED='{"ok": true}', FAKE_CUT_EXIT="0")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("reported as a successful cut", completed.stderr)
        self.assertIn('{"ok": true}', completed.stderr)
        self.assertEqual(self.calls()[-1][2:4], ["feature", "cut-extrude"])

    def test_unexpected_native_failure_is_reported_without_continuing(self):
        denied = {
            **self.denied,
            "error": {"type": "HostDisconnected", "message": "native host lost"},
        }
        completed = self.run_gate(FAKE_DENIED=json.dumps(denied))
        self.assertEqual(completed.returncode, 1)
        self.assertIn("HostDisconnected", completed.stderr)
        self.assertIn("native host lost", completed.stderr)
        self.assertEqual(self.calls()[-1][2:4], ["feature", "cut-extrude"])

    def test_empty_native_open_document_list_passes(self):
        completed = self.run_gate(final=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.calls(), [["document", "list", "--json"]])
        self.assertIn(json.dumps(self.documents), completed.stdout)

    def test_remaining_or_inconsistent_documents_fail_with_full_json(self):
        cases = (
            (1, [{"title": "Part still open", "document_id": "d-live"}]),
            (0, [{"title": "Hidden part"}]),
            (1, []),
        )
        for count, documents in cases:
            with self.subTest(count=count, documents=documents):
                self.trace.write_text("")
                payload = {**self.documents, "count": count, "documents": documents}
                completed = self.run_gate(final=True, FAKE_DOCUMENTS=json.dumps(payload))
                self.assertEqual(completed.returncode, 1)
                self.assertIn("Open documents remain", completed.stderr)
                self.assertIn(json.dumps(payload), completed.stderr)


if __name__ == "__main__":
    unittest.main()
