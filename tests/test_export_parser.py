#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.export_sw import (
    determine_export_targets,
    infer_doc_type,
    parse_list_line,
    swDocASSEMBLY,
    swDocDRAWING,
    swDocPART,
    to_windows_path,
)


class TestExportParser(unittest.TestCase):
    def test_to_windows_path(self):
        # Linux 绝对路径转换为 Wine Z: 驱动器
        self.assertEqual(
            to_windows_path("/workspace/project/part.SLDPRT"),
            "Z:\\workspace\\project\\part.SLDPRT",
        )
        self.assertEqual(
            to_windows_path("/tmp/out"),
            "Z:\\tmp\\out",
        )
        # Windows 路径保持盘符并转反斜杠
        self.assertEqual(
            to_windows_path("C:/Program Files/SW/SLDWORKS.exe"),
            "C:\\Program Files\\SW\\SLDWORKS.exe",
        )
        self.assertEqual(
            to_windows_path("D:\\CAD\\part.SLDPRT"),
            "D:\\CAD\\part.SLDPRT",
        )
        # 相对路径转反斜杠
        self.assertEqual(
            to_windows_path("sub/folder/file.ext"),
            "sub\\folder\\file.ext",
        )
        # 空字符串
        self.assertEqual(to_windows_path(""), "")

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
        outdir = Path("/workspace/dist")

        # 零件导出 STEP
        targets = determine_export_targets(Path("motor.SLDPRT"), outdir)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0][0], "STEP")
        self.assertEqual(targets[0][1], outdir / "motor.STEP")

        # 装配体导出 STEP
        targets = determine_export_targets(Path("robot.SLDASM"), outdir)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0][0], "STEP")
        self.assertEqual(targets[0][1], outdir / "robot.STEP")

        # 特殊渲染装配体导出 GLB
        targets = determine_export_targets(Path("display.REND.SLDASM"), outdir)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0][0], "GLB")
        self.assertEqual(targets[0][1], outdir / "display.REND.GLB")

        # 工程图同时导出 PDF 和 DWG
        targets = determine_export_targets(Path("layout.SLDDRW"), outdir)
        self.assertEqual(len(targets), 2)
        formats = [t[0] for t in targets]
        self.assertIn("PDF", formats)
        self.assertIn("DWG", formats)
        self.assertEqual(targets[0][1], outdir / "layout.PDF")
        self.assertEqual(targets[1][1], outdir / "layout.DWG")

    def test_parse_list_line(self):
        # 常规有效行
        self.assertEqual(
            parse_list_line("COT[N]/Main/N_MainAssembly.SLDDRW"),
            "COT[N]/Main/N_MainAssembly.SLDDRW",
        )
        # 带前后空白
        self.assertEqual(
            parse_list_line("   Universal/WindowCover.SLDPRT   "),
            "Universal/WindowCover.SLDPRT",
        )
        # 全行注释
        self.assertIsNone(parse_list_line("# 这是一个注释行"))
        # 空行
        self.assertIsNone(parse_list_line(""))
        self.assertIsNone(parse_list_line("   "))
        # 行尾注释
        self.assertEqual(
            parse_list_line("COT[N]/Main/N_Antenna.SLDPRT # 主天线零件"),
            "COT[N]/Main/N_Antenna.SLDPRT",
        )


if __name__ == "__main__":
    unittest.main()
