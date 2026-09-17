import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestPatchWin32u(unittest.TestCase):
    def setUp(self):
        self.script_path = Path(__file__).resolve().parent.parent / "docker" / "patch_win32u.pl"
        self.assertTrue(self.script_path.exists(), f"Script not found: {self.script_path}")

        # Construct synthetic binary payload matching Wine 11.16 win32u layout
        self.expected_header = bytes([
            0x8b, 0x44, 0x24, 0x74, 0x8b, 0x7c, 0x24, 0x64, 0x31, 0xd2,
            0x4c, 0x8b, 0x04, 0x24, 0xc1, 0xe8, 0x02, 0xf7, 0xf7
        ])
        self.patched_header = bytes([
            0x8b, 0x7c, 0x24, 0x64, 0x8b, 0x44, 0x24, 0x68, 0x99, 0x31,
            0xd0, 0x29, 0xd0, 0x4c, 0x8b, 0x04, 0x24, 0x90, 0x90
        ])

        # Padding between header and GL instructions
        # 0x1d - 19 = 10 bytes padding
        pad1 = b"\x90" * (0x1d - len(self.expected_header))
        gl1 = b"\xba\xe1\x80\x00\x00"
        # 0x55 - (0x1d + 5) = 0x55 - 0x22 = 51 bytes padding
        pad2 = b"\x90" * (0x55 - 0x22)
        gl2 = b"\xb8\xe1\x80\x00\x00"

        self.valid_block = self.expected_header + pad1 + gl1 + pad2 + gl2

    def test_patch_fast_offset(self):
        """Test patching when pattern is at exact Wine 11.16 offset 0xce4ee."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_name = f.name
            f.write(b"\x00" * 0xce4ee)
            f.write(self.valid_block)
            f.write(b"\x00" * 1024)

        try:
            # 1. Apply patch
            res = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("Successfully applied Wine 11.x 24-bit DIB OpenGL patch", res.stdout)

            # 2. Verify bytes
            with open(temp_name, "rb") as f:
                f.seek(0xce4ee)
                header = f.read(len(self.patched_header))
                self.assertEqual(header, self.patched_header)

                f.seek(0xce4ee + 0x1d)
                gl1 = f.read(5)
                self.assertEqual(gl1, b"\xba\xe0\x80\x00\x00")

                f.seek(0xce4ee + 0x55)
                gl2 = f.read(5)
                self.assertEqual(gl2, b"\xb8\xe0\x80\x00\x00")

            # 3. Idempotency test (apply again)
            res2 = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res2.returncode, 0)
            self.assertIn("already patched", res2.stdout)

        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def test_patch_fallback_search(self):
        """Test patching when pattern is at a different offset."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_name = f.name
            f.write(b"\xaa" * 0x1000)
            f.write(self.valid_block)
            f.write(b"\xbb" * 1024)

        try:
            res = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("Successfully applied Wine 11.x 24-bit DIB OpenGL patch", res.stdout)
            self.assertIn("at 0x1000", res.stdout)

            with open(temp_name, "rb") as f:
                f.seek(0x1000)
                header = f.read(len(self.patched_header))
                self.assertEqual(header, self.patched_header)

                f.seek(0x1000 + 0x1d)
                self.assertEqual(f.read(5), b"\xba\xe0\x80\x00\x00")

                f.seek(0x1000 + 0x55)
                self.assertEqual(f.read(5), b"\xb8\xe0\x80\x00\x00")

            # Idempotency
            res2 = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res2.returncode, 0)
            self.assertIn("already patched", res2.stdout)

        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def test_nonexistent_and_unmatched_file(self):
        """Test that unknown content or missing files exit cleanly without error."""
        res1 = subprocess.run(["perl", str(self.script_path), "/tmp/nonexistent_dummy_file.so"], capture_output=True, text=True)
        self.assertEqual(res1.returncode, 0)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_name = f.name
            f.write(b"\x00" * 2048)

        try:
            res2 = subprocess.run(["perl", str(self.script_path), temp_name], capture_output=True, text=True)
            self.assertEqual(res2.returncode, 0)
            self.assertIn("not found or unsupported Wine version", res2.stdout)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


if __name__ == "__main__":
    unittest.main()
