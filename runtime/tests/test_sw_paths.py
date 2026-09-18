#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for common path conversion utilities (runtime/scripts/lib/sw_paths.py).
"""

import os
import sys
import unittest
from pathlib import Path

# Ensure runtime/scripts/lib is in path
LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "lib"))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from sw_paths import to_linux_path, to_win_path, to_windows_path


class TestSwPaths(unittest.TestCase):
    def test_to_win_path_linux_absolute(self):
        self.assertEqual(to_win_path("/workspace/model.SLDPRT"), "Z:\\workspace\\model.SLDPRT")
        self.assertEqual(to_win_path("/tmp/test.png"), "Z:\\tmp\\test.png")

    def test_to_win_path_wineprefix_drive_c(self):
        # Native C: drive mapping for Wineprefix files
        res = to_win_path("/root/.wine/drive_c/users/Public/test.SLDPRT", wineprefix="/root/.wine")
        self.assertEqual(res, "C:\\users\\Public\\test.SLDPRT")

        # Case-insensitive check
        res2 = to_win_path("/ROOT/.WINE/DRIVE_C/test.SLDPRT", wineprefix="/root/.wine")
        self.assertEqual(res2, "C:\\test.SLDPRT")

    def test_to_win_path_windows_native(self):
        self.assertEqual(to_win_path("C:/Program Files/SW/app.exe"), "C:\\Program Files\\SW\\app.exe")
        self.assertEqual(to_win_path("D:\\CAD\\file.SLDPRT"), "D:\\CAD\\file.SLDPRT")

    def test_to_win_path_relative(self):
        self.assertEqual(to_win_path("sub/folder/file.ext"), "sub\\folder\\file.ext")

    def test_to_windows_path_alias(self):
        self.assertEqual(to_windows_path("/a/b"), to_win_path("/a/b"))

    def test_to_linux_path(self):
        self.assertEqual(to_linux_path("Z:\\workspace\\model.SLDPRT"), "/workspace/model.SLDPRT")
        self.assertEqual(to_linux_path("Z:/workspace/model.SLDPRT"), "/workspace/model.SLDPRT")
        self.assertEqual(
            to_linux_path("C:\\Program Files\\SW", wineprefix="/root/.wine"),
            "/root/.wine/drive_c/Program Files/SW",
        )
        self.assertEqual(to_linux_path(""), "")


if __name__ == "__main__":
    unittest.main()
