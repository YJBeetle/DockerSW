#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DockerSW 无头批量静默导出引擎
通过 pywin32 调用 SOLIDWORKS COM API，按清单批量导出文件。

支持目标：
1. .SLDPRT / .SLDASM -> .STEP
2. .SLDDRW -> .PDF 和 .DWG
3. *.REND.SLDASM -> .GLB
4. 全流程静默（Silent），适配 CI/CD 场景
5. 智能支持 Linux 与 Wine 路径双向解析
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

# ===== SOLIDWORKS 核心枚举常量 =====
swDocPART = 1
swDocASSEMBLY = 2
swDocDRAWING = 3

swOpenDocOptions_Silent = 1       # 静默打开，禁止弹窗
swSaveAsCurrentVersion = 0        # 当前格式版本
swSaveAsOptions_Silent = 1        # 静默保存


def to_windows_path(path_str: str, wineprefix: Optional[str] = None) -> str:
    """
    将 Linux 路径转换为 Wine 可识别的 Windows 路径（例如 /workspace/a -> Z:\\workspace\\a）
    Wine prefix 的 drive_c 路径转换为原生 C:\\，避免 SOLIDWORKS 通过 Z:\\ 打开
    prefix 内文档时出现内部错误。其他绝对路径继续映射到 Z:\\。
    """
    s = str(path_str).strip()
    if not s:
        return s

    normalized = s.replace("\\", "/")
    prefix = (wineprefix or os.environ.get("WINEPREFIX") or "/root/.wine")
    prefix = prefix.replace("\\", "/").rstrip("/")
    drive_c_candidates = [f"{prefix}/drive_c"]
    if prefix.startswith("/"):
        drive_c_candidates.append(f"Z:{prefix}/drive_c")

    for drive_c in drive_c_candidates:
        normalized_folded = normalized.casefold()
        drive_c_folded = drive_c.casefold()
        if normalized_folded == drive_c_folded:
            return "C:\\"
        if normalized_folded.startswith(f"{drive_c_folded}/"):
            suffix = normalized[len(drive_c) :].replace("/", "\\")
            return f"C:{suffix}"

    # 已经是 Windows 驱动器盘符格式
    if len(s) >= 2 and s[1] == ":" and s[0].isalpha():
        return s.replace("/", "\\")

    # Linux 绝对路径映射到 Wine 的 Z: 盘
    if s.startswith("/"):
        return "Z:" + s.replace("/", "\\")

    return s.replace("/", "\\")


def infer_doc_type(path_or_str: Path | str) -> Optional[int]:
    """根据文件扩展名推导 SOLIDWORKS 文档类型"""
    p = Path(path_or_str)
    ext = p.suffix.upper()
    if ext == ".SLDPRT":
        return swDocPART
    if ext == ".SLDASM":
        return swDocASSEMBLY
    if ext == ".SLDDRW":
        return swDocDRAWING
    return None


def determine_export_targets(src_path: Path, outdir: Path) -> List[Tuple[str, Path]]:
    """
    根据文件命名规则决定需要导出的目标文件列表。
    返回: [(格式名称, 导出目标路径)]
    """
    stem = src_path.stem
    name_upper = src_path.name.upper()
    ext_upper = src_path.suffix.upper()

    targets: List[Tuple[str, Path]] = []

    if name_upper.endswith(".REND.SLDASM"):
        targets.append(("GLB", outdir / f"{stem}.GLB"))
    elif ext_upper in {".SLDPRT", ".SLDASM"}:
        targets.append(("STEP", outdir / f"{stem}.STEP"))
    elif ext_upper == ".SLDDRW":
        targets.append(("PDF", outdir / f"{stem}.PDF"))
        targets.append(("DWG", outdir / f"{stem}.DWG"))

    return targets


def parse_list_line(raw_line: str) -> Optional[str]:
    """解析清单单行，移除注释与首尾空格"""
    line = raw_line.split("#", 1)[0].strip()
    return line if line else None


def _write_line(stream, text: str) -> None:
    msg = str(text)
    encoding = getattr(stream, "encoding", None) or "utf-8"
    data = (msg + "\n").encode(encoding, errors="replace")
    if hasattr(stream, "buffer"):
        stream.buffer.write(data)
        stream.flush()
    else:
        stream.write(data.decode(encoding, errors="replace"))
        stream.flush()


def log(msg: str) -> None:
    _write_line(sys.stdout, msg)


def log_err(msg: str) -> None:
    _write_line(sys.stderr, msg)


def log_exception() -> None:
    log_err(traceback.format_exc().rstrip())


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DockerSW 无头批量静默导出 STEP/PDF/DWG/GLB 工具"
    )
    parser.add_argument(
        "--list",
        required=True,
        help="待导出文件相对或绝对路径清单文本文件",
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="工作区根目录绝对路径（用于拼接清单中的相对路径）",
    )
    parser.add_argument(
        "--outdir",
        required=True,
        help="导出文件输出目录",
    )
    return parser.parse_args()


# ===== COM 交互层（仅在 Windows/Wine 运行时导入与调用） =====

def open_doc_silent(sw_app, file_path_win: str, doc_type: int):
    import pythoncom
    import win32com.client

    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

    model = sw_app.OpenDoc6(
        file_path_win,
        doc_type,
        swOpenDocOptions_Silent,
        "",
        errors,
        warnings,
    )

    if model is None:
        raise RuntimeError(
            f"OpenDoc6 失败: file={file_path_win}, errors={errors.value}, warnings={warnings.value}"
        )

    return model


def save_as_silent(model, output_path_win: str) -> None:
    import pythoncom
    import win32com.client

    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    dispatch_opts = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
    pdf_export_data = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)

    ext = None
    try:
        ext = model.Extension
        ok = ext.SaveAs3(
            output_path_win,
            swSaveAsCurrentVersion,
            swSaveAsOptions_Silent,
            dispatch_opts,
            pdf_export_data,
            errors,
            warnings,
        )
        if not ok:
            raise RuntimeError(
                f"SaveAs3 失败: out={output_path_win}, errors={errors.value}, warnings={warnings.value}"
            )
    finally:
        del dispatch_opts, pdf_export_data, errors, warnings
        if ext is not None:
            del ext


def process_item(sw_app, workspace: Path, outdir: Path, raw_line: str) -> bool:
    line = parse_list_line(raw_line)
    if not line:
        return True

    rel_p = Path(line)
    if rel_p.is_absolute():
        src_path = rel_p.resolve()
    else:
        src_path = (workspace / rel_p).resolve()

    if not src_path.exists():
        log(f"[WARN] 文件未找到，跳过: {src_path}")
        return False

    doc_type = infer_doc_type(src_path)
    if doc_type is None:
        log(f"[INFO] 非 SolidWorks 目标扩展名，跳过: {src_path}")
        return True

    export_targets = determine_export_targets(src_path, outdir)
    if not export_targets:
        log(f"[INFO] 无匹配导出规则，跳过: {src_path}")
        return True

    model = None
    model_title = None
    src_win_path = to_windows_path(str(src_path))

    try:
        log(f"[INFO] 正在打开: {src_path} (Wine: {src_win_path})")
        model = open_doc_silent(sw_app, src_win_path, doc_type)
        try:
            model_title = model.GetTitle()
        except Exception:
            model_title = None

        for fmt, target_path in export_targets:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_win_path = to_windows_path(str(target_path))
            save_as_silent(model, target_win_path)
            log(f"[OK] 导出 {fmt}: {target_path}")
            # 同一文档连续导出多种格式（如 .SLDDRW 连续导出 PDF 和 DWG）时，
            # 及时释放局部 COM 包装对象并触发垃圾回收，给底层工作线程短暂缓冲时间
            gc.collect()
            time.sleep(0.1)

        return True

    except Exception:
        log_err(f"[ERROR] 处理失败: {src_path}")
        log_exception()
        return False

    finally:
        if model is not None and sw_app is not None:
            closed = False
            if model_title:
                try:
                    sw_app.CloseDoc(model_title)
                    closed = True
                except Exception:
                    closed = False

            if not closed:
                try:
                    sw_app.CloseAllDocuments(True)
                except Exception:
                    log_err(f"[WARN] 关闭文档失败: {src_path}")

            del model
            gc.collect()


def main() -> int:
    configure_stdio()
    args = parse_args()

    list_file = Path(args.list).resolve()
    workspace = Path(args.workspace).resolve()
    outdir = Path(args.outdir).resolve()

    if not list_file.exists():
        log_err(f"[FATAL] 清单文件不存在: {list_file}")
        return 1

    if not workspace.exists() or not workspace.is_dir():
        log_err(f"[FATAL] workspace 目录不存在: {workspace}")
        return 1

    outdir.mkdir(parents=True, exist_ok=True)

    # 延迟导入 Windows pywin32 模块
    try:
        import pythoncom
        import win32com.client
    except ImportError as e:
        log_err("[FATAL] 无法导入 pywin32 库，请确保在 Windows/Wine 环境下执行！")
        log_err(str(e))
        return 1

    pythoncom.CoInitialize()
    sw_app = None

    try:
        log("[INFO] 正在连接 SOLIDWORKS COM 服务 (DispatchEx)...")
        sw_app = win32com.client.DispatchEx("SldWorks.Application")

        # 核心静默属性设置
        sw_app.UserControl = False
        sw_app.Visible = False

        ok_count = 0
        fail_count = 0

        # 支持 utf-8-sig 兼容带 BOM 的清单文件
        with list_file.open("r", encoding="utf-8-sig") as f:
            for raw_line in f:
                try:
                    success = process_item(sw_app, workspace, outdir, raw_line)
                    if success:
                        ok_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1
                    log_err("[ERROR] 条目处理抛出异常")
                    log_exception()

        log("=" * 60)
        log(f"[DockerSW SUMMARY] 成功: {ok_count}, 失败: {fail_count}")

        return 0 if fail_count == 0 else 1

    except Exception:
        log_err("[FATAL] SolidWorks 初始化或执行发生严重错误")
        log_exception()
        return 1

    finally:
        if sw_app is not None:
            try:
                sw_app.ExitApp()
                log("[INFO] SOLIDWORKS 进程已安全退出")
            except Exception:
                log_err("[WARN] swApp.ExitApp() 调用失败")

        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
