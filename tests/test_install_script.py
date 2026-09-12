import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_solidworks.sh"


class InstallScriptValidationTests(unittest.TestCase):
    def create_media(self, root: Path, include_vc: bool = True) -> None:
        msi = root / "swwi" / "data" / "solidworks.msi"
        msi.parent.mkdir(parents=True)
        msi.write_bytes(b"test-msi")
        if include_vc:
            vc = root / "PreReqs" / "VCRedist17" / "VC_redist.x64.exe"
            vc.parent.mkdir(parents=True)
            vc.write_bytes(b"test-vc")

    def run_validation(self, media: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(INSTALLER), "--media", str(media), "--validate-only"],
            cwd=ROOT,
            env={**os.environ, "LC_ALL": "C"},
            text=True,
            capture_output=True,
            check=False,
        )

    def test_accepts_complete_official_media_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)
            self.create_media(media)
            result = self.run_validation(media)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Validated complete media layout", result.stdout)

    def test_rejects_media_without_official_vc_prerequisite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)
            self.create_media(media, include_vc=False)
            result = self.run_validation(media)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("VC++ x64 prerequisite is missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
