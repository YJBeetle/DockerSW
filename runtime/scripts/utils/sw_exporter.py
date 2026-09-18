#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DockerSW SolidWorks Headless Batch Export Engine (sw_exporter.py)
Core COM document loading, conversion, and silent export routines for STEP, PDF, DWG, and GLB.
Designed to be invoked either by resident daemon_server or standalone CLI.
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

# Optional COM imports for standalone execution outside daemon
try:
    import pythoncom
    import win32com.client
    HAS_WIN32COM = True
except ImportError:
    pythoncom = None
    win32com = None
    HAS_WIN32COM = False

# Import DockerSW core path utilities (pre-injected in daemon sys.path, or fallback to relative lib)
try:
    from sw_paths import to_win_path, to_linux_path
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    from sw_paths import to_win_path, to_linux_path

# SOLIDWORKS Core Enums & Flags
swDocPART = 1
swDocASSEMBLY = 2
swDocDRAWING = 3

swOpenDocOptions_Silent = 1
swSaveAsCurrentVersion = 0
swSaveAsOptions_Silent = 1


def infer_doc_type(path_or_str: Union[Path, str]) -> Optional[int]:
    """Infer SOLIDWORKS document type based on file extension."""
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
    """Determine list of export target files based on file extension and naming convention."""
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
    """Parse a single line from a file list, ignoring comments and whitespace."""
    line = raw_line.split("#", 1)[0].strip()
    return line if line else None


def open_doc_silent(sw_app: Any, file_path_win: str, doc_type: int):
    """Open document silently via SolidWorks OpenDoc6 COM API."""
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
            f"OpenDoc6 failed: file={file_path_win}, errors={errors.value}, warnings={warnings.value}"
        )

    return model


def save_as_silent(model: Any, output_path_win: str) -> None:
    """Save document silently via SolidWorks SaveAs3 COM API."""
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
                f"SaveAs3 failed: out={output_path_win}, errors={errors.value}, warnings={warnings.value}"
            )
    finally:
        del dispatch_opts, pdf_export_data, errors, warnings
        if ext is not None:
            del ext


def process_export_item(
    sw_app: Any,
    workspace: Path,
    outdir: Path,
    raw_line: str,
    log_fn: Optional[Callable[[str], None]] = None,
    log_err_fn: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str, List[str]]:
    """
    Process a single line/file item for export.
    Returns: (success, message, list_of_exported_files)
    """
    _log = log_fn or (lambda msg: None)
    _err = log_err_fn or (lambda msg: None)

    line = parse_list_line(raw_line)
    if not line:
        return True, "empty or comment line", []

    # Normalize backslashes (support manifests with Windows path separators)
    normalized = line.replace("\\", "/")
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        src_path = Path(to_linux_path(normalized)).resolve()
    else:
        rel_p = Path(normalized)
        if rel_p.is_absolute():
            src_path = rel_p.resolve()
        else:
            src_path = (workspace / rel_p).resolve()

    if not src_path.exists():
        _err(f"[WARN] File not found, skipping: {src_path}")
        return False, f"file not found: {src_path}", []

    doc_type = infer_doc_type(src_path)
    if doc_type is None:
        _log(f"[INFO] Not a SolidWorks target extension, skipping: {src_path}")
        return True, "skipped non-sw extension", []

    export_targets = determine_export_targets(src_path, outdir)
    if not export_targets:
        _log(f"[INFO] No matching export rule, skipping: {src_path}")
        return True, "skipped no matching rule", []

    model = None
    model_title = None
    src_win_path = to_win_path(str(src_path))
    exported_files: List[str] = []

    try:
        _log(f"[INFO] Opening: {src_path} (Wine: {src_win_path})")
        model = open_doc_silent(sw_app, src_win_path, doc_type)
        try:
            model_title = model.GetTitle()
        except Exception:
            model_title = None

        for fmt, target_path in export_targets:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_win_path = to_win_path(str(target_path))
            save_as_silent(model, target_win_path)
            exported_files.append(str(target_path))
            _log(f"[OK] Exported {fmt}: {target_path}")
            gc.collect()
            time.sleep(0.1)

        return True, "success", exported_files

    except Exception as e:
        err_msg = f"Failed to process: {src_path} - {str(e)}"
        _err(f"[ERROR] {err_msg}")
        return False, err_msg, exported_files

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
                    _err(f"[WARN] Failed to close document: {src_path}")

            del model
            gc.collect()


def run_batch_export(
    sw_app: Any,
    lines: Iterable[str],
    workspace: Union[Path, str],
    outdir: Union[Path, str],
    log_fn: Optional[Callable[[str], None]] = None,
    log_err_fn: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Run batch export across an iterable of lines (e.g. from file list).
    Returns structured results dict.
    """
    _workspace = Path(workspace).resolve()
    _outdir = Path(outdir).resolve()
    _outdir.mkdir(parents=True, exist_ok=True)

    ok_count = 0
    fail_count = 0
    results: List[Dict[str, Any]] = []

    for raw_line in lines:
        line_clean = parse_list_line(raw_line)
        if not line_clean:
            continue
        success, msg, targets = process_export_item(
            sw_app=sw_app,
            workspace=_workspace,
            outdir=_outdir,
            raw_line=raw_line,
            log_fn=log_fn,
            log_err_fn=log_err_fn,
        )
        if success:
            ok_count += 1
        else:
            fail_count += 1
        results.append({
            "item": line_clean,
            "success": success,
            "message": msg,
            "targets": targets,
        })

    return {
        "success": fail_count == 0,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "total": ok_count + fail_count,
        "results": results,
    }


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments for sw_exporter."""
    parser = argparse.ArgumentParser(
        prog="sw-export",
        description="DockerSW SolidWorks Headless Batch Exporter",
    )
    parser.add_argument("--list", required=True, help="待导出文件清单文件路径 (txt / list)")
    parser.add_argument("--workspace", default="/workspace", help="工作区根目录绝对路径 (默认: /workspace)")
    parser.add_argument("--outdir", default=None, help="导出文件输出目录 (默认: <workspace>/export)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for batch export.
    Can be run directly or executed inside resident daemon via sw-cli run.
    """
    raw_args = argv
    if raw_args is None:
        if "args" in globals() and isinstance(globals()["args"], list) and globals()["args"]:
            raw_args = globals()["args"]
        else:
            raw_args = sys.argv[1:]

    args = parse_args(raw_args)

    list_path = Path(args.list).resolve()
    if not list_path.exists():
        print(f"[FATAL] 清单文件不存在: {list_path}", file=sys.stderr)
        return 1

    workspace_path = Path(args.workspace).resolve()
    if not workspace_path.exists() or not workspace_path.is_dir():
        print(f"[FATAL] 工作区目录不存在: {workspace_path}", file=sys.stderr)
        return 1

    outdir_path = Path(args.outdir).resolve() if args.outdir else (workspace_path / "export")

    # 优先复用 resident daemon 注入的全局 swApp 单例
    sw_app = globals().get("swApp")
    need_cleanup_com = False

    if sw_app is None:
        if not HAS_WIN32COM:
            print("[FATAL] swApp 未注入且无法加载 win32com 模块，请在 Windows/Wine 或 sw-daemon 下运行！", file=sys.stderr)
            return 1
        pythoncom.CoInitialize()
        need_cleanup_com = True
        try:
            print("[INFO] 正在连接 SOLIDWORKS COM 服务 (DispatchEx)...")
            sw_app = win32com.client.DispatchEx("SldWorks.Application")
            sw_app.UserControl = False
            sw_app.Visible = False
        except Exception as e:
            print(f"[FATAL] SolidWorks COM 初始化失败: {e}", file=sys.stderr)
            return 1

    try:
        with list_path.open("r", encoding="utf-8-sig") as f:
            lines = [line.strip() for line in f if line.strip()]

        res = run_batch_export(
            sw_app=sw_app,
            lines=lines,
            workspace=workspace_path,
            outdir=outdir_path,
            log_fn=lambda msg: print(msg),
            log_err_fn=lambda msg: print(msg, file=sys.stderr),
        )

        print("=" * 60)
        print(f"[DockerSW SUMMARY] 成功: {res['ok_count']}, 失败: {res['fail_count']}")

        set_out = globals().get("set_output")
        if callable(set_out):
            set_out(res)

        return 0 if res["success"] else 1
    finally:
        if need_cleanup_com and sw_app is not None:
            try:
                sw_app.ExitApp()
            except Exception:
                pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())

