#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for batch exporter module (runtime/scripts/utils/sw_exporter.py).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Ensure runtime/scripts/utils and runtime/scripts/lib are in path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
UTILS_DIR = os.path.join(SCRIPTS_DIR, "utils")
LIB_DIR = os.path.join(SCRIPTS_DIR, "lib")
for d in (UTILS_DIR, LIB_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

from sw_exporter import (
    determine_export_targets,
    infer_doc_type,
    parse_list_line,
    run_batch_export,
    swDocASSEMBLY,
    swDocDRAWING,
    swDocPART,
)


class TestSwExporter(unittest.TestCase):
    def test_infer_doc_type(self):
        self.assertEqual(infer_doc_type(Path("box.SLDPRT")), swDocPART)
        self.assertEqual(infer_doc_type(Path("box.sldprt")), swDocPART)
        self.assertEqual(infer_doc_type(Path("assembly.SLDASM")), swDocASSEMBLY)
        self.assertEqual(infer_doc_type(Path("assembly.sldasm")), swDocASSEMBLY)
        self.assertEqual(infer_doc_type(Path("drawing.SLDDRW")), swDocDRAWING)
        self.assertEqual(infer_doc_type(Path("drawing.slddrw")), swDocDRAWING)
        self.assertIsNone(infer_doc_type(Path("readme.txt")))
        self.assertIsNone(infer_doc_type(Path("model.step")))

    def test_determine_export_targets(self):
        outdir = Path("/out")
        targets_part = determine_export_targets(Path("/ws/p.SLDPRT"), outdir)
        self.assertEqual(targets_part, [("STEP", Path("/out/p.STEP"))])

        targets_drw = determine_export_targets(Path("/ws/d.SLDDRW"), outdir)
        self.assertEqual(
            targets_drw,
            [("PDF", Path("/out/d.PDF")), ("DWG", Path("/out/d.DWG"))],
        )

        targets_rend = determine_export_targets(Path("/ws/model.REND.SLDASM"), outdir)
        self.assertEqual(targets_rend, [("GLB", Path("/out/model.REND.GLB"))])

    def test_parse_list_line(self):
        self.assertEqual(parse_list_line("  file.SLDPRT  "), "file.SLDPRT")
        self.assertEqual(parse_list_line("file.SLDPRT # comment"), "file.SLDPRT")
        self.assertIsNone(parse_list_line("# only comment"))
        self.assertIsNone(parse_list_line("   \n"))

    def test_run_batch_export_mocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir) / "workspace"
            ws.mkdir()
            out = Path(tmpdir) / "out"

            # Create sample files
            f1 = ws / "part1.SLDPRT"
            f1.touch()
            f2 = ws / "nonexistent.SLDPRT"

            mock_app = MagicMock()
            mock_model = MagicMock()
            mock_model.GetTitle.return_value = "part1"
            mock_ext = MagicMock()
            mock_ext.SaveAs3.return_value = True
            mock_model.Extension = mock_ext

            # Mock OpenDoc6
            mock_app.OpenDoc6.return_value = mock_model

            lines = ["part1.SLDPRT", "nonexistent.SLDPRT", "# comment line"]
            from unittest.mock import patch
            with patch("sw_exporter.open_doc_silent", return_value=mock_model) as mock_open, \
                 patch("sw_exporter.save_as_silent") as mock_save:
                res = run_batch_export(
                    sw_app=mock_app,
                    lines=lines,
                    workspace=ws,
                    outdir=out,
                )

                self.assertFalse(res["success"])  # nonexistent failed
                self.assertEqual(res["ok_count"], 1)
                self.assertEqual(res["fail_count"], 1)
                self.assertEqual(res["total"], 2)
                mock_open.assert_called_once()
                mock_save.assert_called_once()

    def test_main_cli_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir) / "workspace"
            ws.mkdir()
            out = Path(tmpdir) / "out"
            f1 = ws / "part1.SLDPRT"
            f1.touch()
            list_file = Path(tmpdir) / "items.list"
            list_file.write_text("part1.SLDPRT\n")

            mock_app = MagicMock()
            from unittest.mock import patch
            import sw_exporter

            with patch("sw_exporter.run_batch_export") as mock_run:
                mock_run.return_value = {
                    "success": True,
                    "ok_count": 1,
                    "fail_count": 0,
                    "total": 1,
                    "results": [],
                }
                # When swApp is injected into globals (by daemon)
                with patch.dict(sw_exporter.__dict__, {"swApp": mock_app}):
                    exit_code = sw_exporter.main([
                        "--list", str(list_file),
                        "--workspace", str(ws),
                        "--outdir", str(out),
                    ])
                    self.assertEqual(exit_code, 0)
                    mock_run.assert_called_once()

    def test_process_export_item_windows_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir) / "workspace"
            sub = ws / "sub" / "folder"
            sub.mkdir(parents=True)
            f1 = sub / "test.SLDPRT"
            f1.touch()
            out = Path(tmpdir) / "out"

            mock_app = MagicMock()
            mock_model = MagicMock()
            mock_model.GetTitle.return_value = "test"
            from unittest.mock import patch
            from sw_exporter import process_export_item
            with patch("sw_exporter.open_doc_silent", return_value=mock_model), \
                 patch("sw_exporter.save_as_silent"):
                # Test Windows backslash relative path
                ok, msg, targets = process_export_item(
                    sw_app=mock_app,
                    workspace=ws,
                    outdir=out,
                    raw_line="sub\\folder\\test.SLDPRT",
                )
                self.assertTrue(ok, msg)
                self.assertEqual(len(targets), 1)
                self.assertTrue(targets[0].endswith(".STEP"))


if __name__ == "__main__":
    unittest.main()
