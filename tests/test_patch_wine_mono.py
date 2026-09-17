import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestPatchWineMono(unittest.TestCase):
    def setUp(self):
        self.script_path = Path(__file__).resolve().parent.parent / "docker" / "patch_wine_mono.pl"

        # Pattern in libmono-2.0-x86_64.dll:
        # 4d8b6e084d85ed0f849f00000041837d0000 0f84ac000000 488b8048040000
        self.expected_bytes = bytes.fromhex("4d8b6e084d85ed0f849f00000041837d00000f84ac000000488b8048040000")
        self.patched_bytes = bytes.fromhex("4d8b6e084d85ed0f849f00000041837d0000909090909090488b8048040000")
        self.fast_offset = 0x175588

    def test_patch_fast_offset(self):
        """Test patching when pattern is at exact Wine-Mono 11.3.0 offset 0x175588."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_name = f.name
            f.write(b"\x00" * self.fast_offset)
            f.write(self.expected_bytes)
            f.write(b"\x00" * 1024)

        try:
            # 1. Apply patch
            res = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("Successfully applied Wine-Mono CCW release assertion patch", res.stdout)

            # 2. Verify bytes
            with open(temp_name, "rb") as f:
                f.seek(self.fast_offset)
                data = f.read(len(self.patched_bytes))
                self.assertEqual(data, self.patched_bytes)

            # 3. Test idempotency (running again should report already patched)
            res2 = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res2.returncode, 0)
            self.assertIn("already patched", res2.stdout)

        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)

    def test_patch_scan_offset(self):
        """Test patching when pattern is at arbitrary offset (scan mode)."""
        arbitrary_offset = 0x80000
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_name = f.name
            f.write(b"\x00" * arbitrary_offset)
            f.write(self.expected_bytes)
            f.write(b"\x00" * 512)

        try:
            res = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("Successfully applied Wine-Mono CCW release assertion patch", res.stdout)

            with open(temp_name, "rb") as f:
                f.seek(arbitrary_offset)
                data = f.read(len(self.patched_bytes))
                self.assertEqual(data, self.patched_bytes)

        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)

    def test_nonexistent_file(self):
        """Non-existent file should exit cleanly with 0."""
        res = subprocess.run(["perl", str(self.script_path), "/tmp/nonexistent_mono.dll"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

    def test_patch_real_dll_if_available(self):
        """Test on actual extracted libmono-2.0-x86_64.dll if present in scratch dir."""
        real_dll = Path("/Users/YJBeetle/.gemini/antigravity-ide/brain/fe479a1c-6cdb-4536-94f3-88d1e1ed13f3/scratch/libmono-2.0-x86_64.dll")
        if not real_dll.exists():
            return

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_name = f.name
            f.write(real_dll.read_bytes())

        try:
            res = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("Successfully applied Wine-Mono CCW release assertion patch", res.stdout)
            self.assertIn("at 0x175588", res.stdout)

            # Re-run for idempotency
            res2 = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res2.returncode, 0)
            self.assertIn("already patched at 0x175588", res2.stdout)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)


if __name__ == "__main__":
    unittest.main()
