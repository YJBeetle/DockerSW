"""Only test DockerSW's shell delegation; CAD assertions live in SWCLI."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("bash"), "Bash is required")
class SharedSmokeWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.evidence = self.directory / "evidence with spaces"
        self.evidence.mkdir()
        self.trace = self.directory / "command.json"
        python = self.directory / "python3"
        python.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['TRACE']).write_text(json.dumps({'args':sys.argv[1:],'pythonpath':os.environ['PYTHONPATH']}))\n"
            "sys.stderr.write('native diagnostic stderr\\n')\n"
            "sys.exit(int(os.environ.get('EXIT_CODE','0')))\n",
            encoding="utf-8",
        )
        python.chmod(0o755)
        winepath = self.directory / "winepath"
        winepath.write_text(
            f"#!{sys.executable}\nimport sys\n"
            "assert sys.argv[1] == '-w' and len(sys.argv) == 3\n"
            "print('C:\\\\mapped' + sys.argv[2].replace('/', '\\\\'))\n",
            encoding="utf-8",
        )
        winepath.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": str(self.directory) + os.pathsep + os.environ["PATH"],
            "TRACE": str(self.trace),
            "SW_SMOKE_EVIDENCE_DIR": str(self.evidence),
            "SWCLI_SOURCE": "/source with spaces/src",
            "SWCLI_DEPS": "/deps with spaces",
        }

    def run_wrapper(self, name, *arguments, **environment):
        return subprocess.run(
            ["bash", str(ROOT / "smoke-test" / name), *arguments],
            env={**self.environment, **environment},
            capture_output=True,
            text=True,
            timeout=10,
        )

    def call(self):
        return json.loads(self.trace.read_text())

    def value(self, flag):
        arguments = self.call()["args"]
        return arguments[arguments.index(flag) + 1]

    def test_modeling_delegates_paths_and_samples_without_its_own_cad_logic(self):
        output = self.evidence / "modeling"
        result = self.run_wrapper("verify-swcli.sh", "/wine drive C", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.call()["args"][0], "/opt/swcli/scripts/ci/verify-modeling.py"
        )
        self.assertEqual(self.value("--output-dir"), str(output))
        self.assertTrue(self.value("--host-output-dir").startswith("C:"))
        self.assertIn("wine drive C", self.value("--sample-part"))
        self.assertTrue(self.value("--sample-part").endswith("Paper Airplane.SLDPRT"))
        self.assertTrue(
            self.value("--sample-assembly").endswith("bezel moldbase.sldasm")
        )
        self.assertEqual(self.value("--cli-command"), "/usr/local/bin/sw-cli")
        self.assertEqual(
            self.call()["pythonpath"], "/source with spaces/src:/deps with spaces/linux"
        )
        self.assertEqual(output.stat().st_mode & 0o777, 0o755)
        self.assertIn("native diagnostic stderr", result.stderr)

    def test_local_repeat_runs_use_distinct_directories(self):
        self.assertEqual(self.run_wrapper("verify-swcli.sh", "/wine").returncode, 0)
        first = Path(self.value("--output-dir"))
        model = first / "model.SLDPRT"
        model.write_bytes(b"previous evidence")
        self.assertEqual(self.run_wrapper("verify-swcli.sh", "/wine").returncode, 0)
        second = Path(self.value("--output-dir"))
        self.assertNotEqual(first, second)
        self.assertEqual(model.read_bytes(), b"previous evidence")
        self.assertEqual(first.parent, self.evidence)
        self.assertEqual(second.parent, self.evidence)

    def test_driving_requires_and_forwards_predecessor_record(self):
        record = str(self.evidence / "modeling/modeling.json")
        result = self.run_wrapper("verify-driving.sh", record)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.value("--after-modeling"), record)
        self.assertEqual(
            self.call()["args"][0], "/opt/swcli/scripts/ci/verify-driving-dimensions.py"
        )
        self.assertTrue(Path(self.value("--output-dir")).is_dir())
        self.trace.unlink()
        missing = self.run_wrapper("verify-driving.sh")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("MODELING_JSON", missing.stderr)
        self.assertFalse(self.trace.exists())

    def test_shared_failure_propagates_without_retry_or_suppressing_stderr(self):
        for script, arguments in (
            ("verify-swcli.sh", ("/wine",)),
            ("verify-driving.sh", ("/proof/modeling.json",)),
        ):
            with self.subTest(script=script):
                result = self.run_wrapper(script, *arguments, EXIT_CODE="23")
                self.assertEqual(result.returncode, 23)
                self.assertIn("native diagnostic stderr", result.stderr)


if __name__ == "__main__":
    unittest.main()
