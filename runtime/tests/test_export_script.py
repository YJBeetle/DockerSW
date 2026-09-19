import os
import subprocess
import tempfile
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SWCLI_SCRIPT = RUNTIME_ROOT / "bin" / "sw-cli"
EXPORT_SCRIPT = RUNTIME_ROOT / "bin" / "sw-export"


class ExportWrapperTests(unittest.TestCase):
    def test_scripts_are_executable_and_valid_bash(self):
        for script in (SWCLI_SCRIPT, EXPORT_SCRIPT):
            self.assertTrue(os.access(script, os.X_OK), f"not executable: {script}")
            result = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_sw_cli_translates_typed_path_argument(self):
        invocation = self._run_with_fake_wine(
            SWCLI_SCRIPT, ["document", "open", "/workspace/model.SLDPRT", "--json"]
        )
        self.assertIn("-m swcli document open W:/workspace/model.SLDPRT --json", invocation)

    def test_sw_export_translates_manifest_paths_and_calls_docker_runner(self):
        invocation = self._run_with_fake_wine(
            EXPORT_SCRIPT,
            [
                "--list",
                "/workspace/list.txt",
                "--workspace",
                "/workspace",
                "--outdir",
                "/workspace/out",
                "--overwrite",
            ],
        )
        self.assertIn("W:/opt/sw-runtime/scripts/swcli_docker_export.py", invocation)
        self.assertIn("--list W:/workspace/list.txt", invocation)
        self.assertIn("--workspace W:/workspace", invocation)
        self.assertIn("--outdir W:/workspace/out", invocation)
        self.assertIn("--overwrite", invocation)

    def _run_with_fake_wine(self, script: Path, args: list[str]) -> str:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            binary_dir = root / "bin"
            binary_dir.mkdir()
            log = root / "wine.log"
            winepath = binary_dir / "winepath"
            winepath.write_text(
                "#!/usr/bin/env bash\nprintf 'W:%s\\n' \"${@: -1}\"\n",
                encoding="utf-8",
            )
            winepath.chmod(0o755)
            wine = binary_dir / "wine"
            wine.write_text(
                f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > '{log}'\n",
                encoding="utf-8",
            )
            wine.chmod(0o755)
            environment = dict(os.environ)
            environment["PATH"] = f"{binary_dir}:{environment['PATH']}"
            result = subprocess.run(
                [str(script), *args], capture_output=True, text=True, env=environment
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return log.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
