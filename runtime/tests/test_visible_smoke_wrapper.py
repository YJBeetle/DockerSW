import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "Bash and jq required")
class VisibleWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.trace = self.directory / "trace.json"
        executable = f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
role = Path(sys.argv[0]).name
if role == 'python3':
    Path(os.environ['TRACE']).write_text(json.dumps(sys.argv[1:]))
    print('shared visible diagnostic', file=sys.stderr)
    sys.exit(int(os.environ.get('VISIBLE_EXIT', '0')))
if role == 'winepath':
    assert sys.argv[1] == '-w'
    print('Z:' + sys.argv[2].replace('/', '\\\\'))
else:
    assert sys.argv[1:] == ['--request-timeout', '2', 'daemon', 'status', '--json']
    print(json.dumps({'success': False, 'error': {'code': os.environ.get('STOP_ERROR', 'ConnectionRefusedError')}}))
    sys.exit(1)
'''
        for name in ("python3", "winepath", "sw-cli"):
            path = self.directory / name
            path.write_text(executable)
            path.chmod(0o755)

    def run_wrapper(self, **values):
        return subprocess.run(["bash", str(ROOT / "smoke-test/verify-visible.sh")],
            env={**os.environ, "PATH": str(self.directory) + os.pathsep + os.environ["PATH"],
                 "TRACE": str(self.trace), "SW_SMOKE_EVIDENCE_DIR": str(self.directory / "proof"),
                 "WINEPREFIX": "/prefix with spaces", **values}, capture_output=True, text=True, timeout=10)

    def test_delegates_independent_shared_script_and_requires_stopped_endpoint(self):
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.trace.read_text())
        self.assertEqual(args[0], "/opt/swcli/scripts/ci/verify-visible.py")
        self.assertIn("/usr/local/bin/sw-cli", args)
        self.assertIn("--sample-part", args)
        self.assertIn("shared visible diagnostic", result.stderr)
        self.assertNotIn("--suite", args)

    def test_shared_failure_code_and_terminal_shutdown_error_remain_failures(self):
        self.assertEqual(self.run_wrapper(VISIBLE_EXIT="37").returncode, 37)
        result = self.run_wrapper(STOP_ERROR="HostDisconnected")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shutdown could not be verified", result.stderr)

    def test_ci_requires_both_modes_and_never_publishes_vnc_port(self):
        workflow = (ROOT / ".github/workflows/build.yml").read_text()
        visible = workflow.split("- name: Shared lightweight visible smoke", 1)[1].split("- name:", 1)[0]
        self.assertIn("--env SWCLID_VISIBLE=true --env VNC_ENABLE=true", visible)
        self.assertIn("verify-visible.sh", visible)
        self.assertNotIn("--publish", visible)
        self.assertNotIn(" -p ", visible)
        self.assertIn("trap 'docker rm -f", visible)
        self.assertLess(workflow.index("Shared lightweight visible smoke"), workflow.index("Make public smoke evidence readable"))
        publish = workflow.split("- name: Publish verified CLI images", 1)[1].split("run:", 1)[0]
        self.assertIn("steps.smoke-visible.outcome == 'success'", publish)
        self.assertIn("steps.smoke-generic.outcome == 'success'", publish)
