import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "smoke-test/verify-swcli.sh"


@unittest.skipUnless(shutil.which("bash"), "Bash is required")
class SmokeArtifactPathsTests(unittest.TestCase):
    def test_repeat_runs_keep_distinct_evidence_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence with spaces"
            evidence.mkdir()
            fake_cli = root / "sw-cli"
            fake_cli.write_text("#!/usr/bin/env bash\nprintf '{}\\n'\n")
            fake_cli.chmod(0o755)
            preamble = SCRIPT.read_text().split("# Unsaved documents", 1)[0]
            environment = {
                **os.environ,
                "PATH": str(root) + os.pathsep + os.environ["PATH"],
                "SW_SMOKE_EVIDENCE_DIR": str(evidence),
            }

            def run():
                result = subprocess.run(
                    ["bash", "-c", preamble + '\nprintf "%s\\n" "$modeling_outdir"',
                     "artifact-fixture", "/unused/wine/drive_c"],
                    env=environment, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                directory = Path(result.stdout.splitlines()[-1])
                self.assertEqual(directory.parent, evidence)
                self.assertTrue(directory.name.startswith("swcli-generic."))
                self.assertEqual(directory.stat().st_mode & 0o777, 0o755)
                return directory

            first = run()
            earlier = first / "model.SLDPRT"
            earlier.write_bytes(b"retained earlier native model")
            second = run()
            self.assertNotEqual(first, second)
            self.assertEqual(earlier.read_bytes(), b"retained earlier native model")
            self.assertFalse((second / "model.SLDPRT").exists())

    def test_all_extra_artifacts_use_the_run_directory(self):
        source = SCRIPT.read_text()
        self.assertIn('native_path="${modeling_outdir}/model.SLDPRT"', source)
        for name in ("lease-denied.STEP", "leased.STEP", "multi-document.STEP"):
            self.assertIn('"${modeling_outdir}/' + name + '"', source)
        self.assertNotIn("/tmp/swcli-smoke-", source)


if __name__ == "__main__":
    unittest.main()
