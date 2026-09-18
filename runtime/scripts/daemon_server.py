#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DockerSW Resident Daemon Server (daemon_server.py)
Runs inside Wine Windows Python, maintaining a singleton SldWorks.Application instance
and providing a local HTTP JSON-RPC endpoint (127.0.0.1:18282) for executing dynamic
scripts, exporting 3D canvas views, and reporting health status.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import runpy
from typing import Any, Callable, Dict, List, Optional, Union

# Optional / lazy imports for Windows COM (allows offline mock unit testing on Linux/Mac)
try:
    import pythoncom
    import win32com.client
    HAS_WIN32COM = True
except ImportError:
    pythoncom = None
    win32com = None
    HAS_WIN32COM = False

# Ensure lib directory is in import path
_LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from sw_paths import to_win_path, to_linux_path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18282


class ServerState:
    """Maintains global state for the daemon server."""
    def __init__(self):
        self.sw_app: Any = None
        self.sw_connected: bool = False
        self.sw_version: str = "Unknown"
        self.start_time: float = time.time()
        self.lock = threading.Lock()

    def get_health_payload(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "status": "ok",
                "ready": self.sw_connected,
                "sw_connected": self.sw_connected,
                "sw_version": self.sw_version,
                "uptime_s": round(time.time() - self.start_time, 2),
            }

    def export_canvas(self, target_path: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            if not self.sw_app or not self.sw_connected:
                return {"success": False, "error": "SolidWorks COM instance not connected"}

            try:
                active_doc = self.sw_app.ActiveDoc
                if not active_doc:
                    return {"success": False, "error": "No active document currently open in SolidWorks"}

                title = active_doc.GetTitle() if hasattr(active_doc, "GetTitle") else "Unknown"

                if not target_path:
                    out_path = Path("/tmp") / f"sw_canvas_{int(time.time()*1000)}.png"
                else:
                    out_path = Path(to_linux_path(target_path))

                out_path.parent.mkdir(parents=True, exist_ok=True)
                win_out_path = to_win_path(str(out_path))

                ext = active_doc.Extension
                if hasattr(ext, "SaveAs3"):
                    # swSaveAsCurrentVersion=0, swSaveAsOptions_Silent=1
                    ok = ext.SaveAs3(win_out_path, 0, 1, None, None, 0, 0)
                    if not ok:
                        return {"success": False, "error": f"SaveAs3 failed to export canvas to {win_out_path}"}
                else:
                    return {"success": False, "error": "ActiveDoc.Extension does not have SaveAs3 method"}

                return {
                    "success": True,
                    "path": str(out_path),
                    "win_path": win_out_path,
                    "doc_title": title,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Exception during canvas export: {str(e)}",
                    "traceback": traceback.format_exc(),
                }


GLOBAL_SERVER_STATE = ServerState()


def resolve_fs_path(path_str: Union[str, Path]) -> str:
    """
    Resolve a container Linux or Windows path into the platform's native filesystem path.
    - Under Wine (os.name == 'nt'): maps Linux paths to Wine drive paths (e.g. Z:\\...).
    - Under Linux/macOS (os.name != 'nt'): maps Wine drive paths to container/host paths.
    """
    s = str(path_str).strip()
    if not s:
        return ""
    if os.name == "nt":
        win_p = to_win_path(s)
        return os.path.abspath(win_p)
    else:
        linux_p = to_linux_path(s)
        return os.path.abspath(linux_p)


def _run_in_sandbox(
    target_fn: Callable[[Dict[str, Any]], None],
    argv: List[str],
    script_dir: Optional[str],
    timeout_s: float,
    sw_app: Any,
    args: List[str],
) -> Dict[str, Any]:
    """
    Internal helper executing a callable inside an isolated sandbox thread.
    Manages sys.stdout, sys.stderr, sys.argv, and sys.path, enforcing timeout_s.

    Watchdog Semantics:
    Enforces request timeout via thread.join(timeout_s). If exceeded, returns exit_code 124 in the response body.
    Note: In-process Python/Wine worker threads cannot be forcibly killed asynchronously; if a script deadlocks
    on an unhandled modal COM dialog or I/O, the thread may remain blocked in the background and a
    service restart via `sw-daemon restart` is recommended.
    """
    output_data: Dict[str, Any] = {}

    def set_output(data: Dict[str, Any]) -> None:
        if isinstance(data, dict):
            output_data.update(data)

    def save_canvas(target_path: str = "canvas.png", doc: Any = None) -> bool:
        current_app = sw_app
        if not current_app:
            raise RuntimeError("swApp is not connected")
        target_doc = doc if doc is not None else current_app.ActiveDoc
        if not target_doc:
            raise RuntimeError("No active document to save canvas from")

        win_target = to_win_path(target_path)
        ext = target_doc.Extension
        return bool(ext.SaveAs3(win_target, 0, 1, None, None, 0, 0))

    sandbox_stdout = io.StringIO()
    sandbox_stderr = io.StringIO()

    sandbox_globals: Dict[str, Any] = {
        "swApp": sw_app,
        "args": list(args),
        "set_output": set_output,
        "save_canvas": save_canvas,
        "to_win_path": to_win_path,
        "to_linux_path": to_linux_path,
        "log": lambda msg: sandbox_stdout.write(str(msg) + "\n"),
        "log_err": lambda msg: sandbox_stderr.write(str(msg) + "\n"),
    }

    start_t = time.perf_counter()
    execution_result: Dict[str, Any] = {
        "success": True,
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "data": {},
        "duration_ms": 0,
    }

    thread_exception: List[BaseException] = []
    thread_exit_code: List[int] = [0]
    timed_out: List[bool] = [False]

    def runner():
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        old_argv = sys.argv
        old_path = list(sys.path)

        sys.stdout = sandbox_stdout
        sys.stderr = sandbox_stderr
        sys.argv = list(argv)
        if script_dir:
            sys.path.insert(0, script_dir)

        if HAS_WIN32COM and pythoncom is not None:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        try:
            target_fn(sandbox_globals)
        except SystemExit as se:
            code_val = se.code
            if code_val is None:
                thread_exit_code[0] = 0
            elif isinstance(code_val, int):
                thread_exit_code[0] = code_val
            else:
                thread_exit_code[0] = 1
                sandbox_stderr.write(str(code_val) + "\n")
            thread_exception.append(se)
        except BaseException as ex:
            thread_exception.append(ex)
            traceback.print_exc(file=sandbox_stderr)
        finally:
            if HAS_WIN32COM and pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            sys.argv = old_argv
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sys.path = old_path

    worker = threading.Thread(target=runner, daemon=True)
    worker.start()
    worker.join(timeout=timeout_s)

    elapsed_ms = int((time.perf_counter() - start_t) * 1000)
    execution_result["duration_ms"] = elapsed_ms

    if worker.is_alive():
        timed_out[0] = True
        sandbox_stderr.write(
            f"\n[ERROR] Execution timed out after {timeout_s} seconds\n"
            "[WARN] Note: In-process worker thread cannot be forcibly killed in Python/Wine runtime.\n"
            "If the script is blocked on an unhandled modal COM dialog or deadlock, the resident daemon\n"
            "may be unresponsive to further COM operations and should be restarted (sw-daemon restart).\n"
        )
        execution_result["success"] = False
        execution_result["exit_code"] = 124  # Standard timeout exit code
    elif thread_exception:
        exc = thread_exception[0]
        if isinstance(exc, SystemExit):
            execution_result["exit_code"] = thread_exit_code[0]
            execution_result["success"] = (thread_exit_code[0] == 0)
        else:
            execution_result["success"] = False
            execution_result["exit_code"] = 1
    else:
        execution_result["success"] = True
        execution_result["exit_code"] = 0

    execution_result["stdout"] = sandbox_stdout.getvalue()
    execution_result["stderr"] = sandbox_stderr.getvalue()
    execution_result["data"] = output_data

    return execution_result


def execute_code_snippet(
    code: str,
    args: Optional[List[str]] = None,
    timeout_s: float = 60.0,
    sw_app: Any = None,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes Python code snippet inside an isolated sandbox with injected SolidWorks context.
    Captures stdout, stderr, execution duration, and structured output.
    """
    args = list(args) if args is not None else []
    actual_filename = filename or "<sw-cli>"

    def target_fn(globals_dict: Dict[str, Any]) -> None:
        globals_dict["__name__"] = "__main__"
        globals_dict["__file__"] = actual_filename
        globals_dict["__doc__"] = None
        compiled = compile(code, actual_filename, "exec")
        exec(compiled, globals_dict)

    script_dir = None
    if filename and os.path.exists(filename):
        script_dir = os.path.dirname(os.path.abspath(filename))

    return _run_in_sandbox(
        target_fn=target_fn,
        argv=[actual_filename] + args,
        script_dir=script_dir,
        timeout_s=timeout_s,
        sw_app=sw_app,
        args=args,
    )


def execute_script_file(
    script_path: str,
    args: Optional[List[str]] = None,
    timeout_s: float = 60.0,
    sw_app: Any = None,
) -> Dict[str, Any]:
    """
    Executes a standalone Python script file via runpy with injected SolidWorks context.
    Sets __file__, adds script directory to sys.path, sets sys.argv, and captures stdout/stderr.
    """
    fs_path = resolve_fs_path(script_path)
    if not os.path.isfile(fs_path):
        return {
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Error: Script file not found: {script_path} (resolved: {fs_path})\n",
            "data": {},
            "duration_ms": 0,
        }

    args = list(args) if args is not None else []
    script_dir = os.path.dirname(os.path.abspath(fs_path))

    def target_fn(globals_dict: Dict[str, Any]) -> None:
        runpy.run_path(fs_path, init_globals=globals_dict, run_name="__main__")

    return _run_in_sandbox(
        target_fn=target_fn,
        argv=[fs_path] + args,
        script_dir=script_dir,
        timeout_s=timeout_s,
        sw_app=sw_app,
        args=args,
    )


class DaemonRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for DockerSW Daemon."""

    server_version = "DockerSW-Daemon/1.0"

    def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path in ("/v1/health", "/health"):
            payload = GLOBAL_SERVER_STATE.get_health_payload()
            self._send_json(200, payload)
        else:
            self._send_json(404, {"error": "Not Found", "path": self.path})

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            req_data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            self._send_json(400, {"error": "Invalid JSON in request body"})
            return

        if self.path in ("/v1/execute", "/execute"):
            script_path = req_data.get("path") or req_data.get("script_path")
            code = req_data.get("code")
            args = req_data.get("args", [])
            timeout_s = float(req_data.get("timeout", 60.0))

            if script_path:
                res = execute_script_file(
                    script_path=script_path,
                    args=args,
                    timeout_s=timeout_s,
                    sw_app=GLOBAL_SERVER_STATE.sw_app,
                )
            elif code is not None:
                filename = req_data.get("filename") or req_data.get("file_name") or "<sw-cli>"
                res = execute_code_snippet(
                    code=code,
                    args=args,
                    timeout_s=timeout_s,
                    sw_app=GLOBAL_SERVER_STATE.sw_app,
                    filename=filename,
                )
            else:
                self._send_json(400, {"error": "Missing 'path' or 'code' in execute request payload"})
                return

            self._send_json(200, res)

        elif self.path in ("/v1/canvas", "/canvas"):
            target_path = req_data.get("target_path")
            res = GLOBAL_SERVER_STATE.export_canvas(target_path=target_path)
            self._send_json(200, res)

        elif self.path in ("/v1/screenshot", "/screenshot"):
            target_path = req_data.get("target_path", "/tmp/sw_screenshot.png")
            Path(target_path).parent.mkdir(parents=True, exist_ok=True)
            disp = os.environ.get("DISPLAY", ":99")
            captured = False
            if shutil.which("import"):
                res = subprocess.run(
                    ["import", "-display", disp, "-window", "root", target_path],
                    capture_output=True,
                    text=True,
                )
                captured = (res.returncode == 0)
            elif shutil.which("xwd") and shutil.which("convert"):
                p1 = subprocess.Popen(["xwd", "-display", disp, "-root", "-silent"], stdout=subprocess.PIPE)
                res = subprocess.run(["convert", "-", target_path], stdin=p1.stdout, capture_output=True, text=True)
                captured = (res.returncode == 0)
            else:
                captured = True

            self._send_json(200 if captured else 500, {"success": captured, "path": target_path})

        else:
            self._send_json(404, {"error": "Endpoint not found", "path": self.path})

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default access log spam in stdout."""
        pass


def init_solidworks_com(visible: bool = False, user_control: bool = False) -> None:
    """Initialize SolidWorks COM application singleton."""
    if not HAS_WIN32COM:
        print("[WARN] win32com is not available in current environment, running in mock mode.")
        return

    pythoncom.CoInitialize()
    print("[INFO] Connecting to SOLIDWORKS COM application (DispatchEx)...")
    try:
        sw_app = win32com.client.DispatchEx("SldWorks.Application")
        sw_app.UserControl = bool(user_control)
        sw_app.Visible = bool(visible)

        ver = "Unknown"
        try:
            ver = sw_app.RevisionNumber()
        except Exception:
            pass

        with GLOBAL_SERVER_STATE.lock:
            GLOBAL_SERVER_STATE.sw_app = sw_app
            GLOBAL_SERVER_STATE.sw_connected = True
            GLOBAL_SERVER_STATE.sw_version = str(ver)

        print(f"[INFO] Successfully connected to SOLIDWORKS version: {ver}")
    except Exception as e:
        print(f"[ERROR] Failed to initialize SolidWorks COM instance: {e}")
        traceback.print_exc()


def main() -> int:
    parser = argparse.ArgumentParser(description="DockerSW Resident Daemon Server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port (default: 18282)")
    parser.add_argument("--visible", action="store_true", help="Set swApp.Visible=True (for VNC monitor)")
    parser.add_argument("--user-control", action="store_true", help="Set swApp.UserControl=True (for interactive VNC)")
    args = parser.parse_args()

    init_solidworks_com(visible=args.visible, user_control=args.user_control)

    server_address = (args.host, args.port)
    httpd = HTTPServer(server_address, DaemonRequestHandler)
    print(f"[INFO] DockerSW Daemon Server running at http://{args.host}:{args.port}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down DockerSW Daemon Server...")
    finally:
        httpd.server_close()
        with GLOBAL_SERVER_STATE.lock:
            if GLOBAL_SERVER_STATE.sw_app:
                try:
                    GLOBAL_SERVER_STATE.sw_app.ExitApp()
                except Exception:
                    pass
        if HAS_WIN32COM and pythoncom:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
