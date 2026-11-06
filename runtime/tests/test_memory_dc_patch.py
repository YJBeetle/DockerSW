"""Compile the actual patch helper against a mock GL driver and DIB converter."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class MemoryDCPatchTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("cc"), "C compiler required")
    def test_pixel_layout_and_gl_state(self):
        patch = (ROOT / "runtime/wine-patches/0000-win32u-fix-24bit-memory-dc.patch").read_text()
        helper = "\n".join(line[1:] for line in patch.splitlines()
                           if line.startswith("+") and not line.startswith("+++"))
        helper = helper[:helper.index("            ret = sync_bitmap_framebuffer")]
        fixture = (ROOT / "runtime/tests/native/memory_dc_transfer_test.c").read_text()
        source = fixture.replace("/* PATCH_HELPER */", helper)
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "memory_dc.c"
            executable = Path(directory) / "memory_dc"
            source_path.write_text(source)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Werror", str(source_path),
                            "-o", str(executable)], check=True, capture_output=True)
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
