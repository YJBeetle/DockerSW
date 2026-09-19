"""DockerSW lifecycle adapter for SWCLI's typed batch exporter."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional, Sequence

from swcli.hosts.windows import wait_windows_host_ready
from swcli.utils.export import batch_export_windows


PROG_ID = "SldWorks.Application"
DEFAULT_STARTUP_TIMEOUT_SECONDS = 120.0


def _error(exc: BaseException) -> Dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _com_value(obj: Any, name: str) -> Any:
    value = getattr(obj, name)
    if hasattr(value, "_oleobj_"):
        return value
    return value() if callable(value) else value


def _describe_app(app: Any) -> Dict[str, Any]:
    return {
        "attached": True,
        "revision": str(_com_value(app, "RevisionNumber")),
        "process_id": int(_com_value(app, "GetProcessID")),
        "visible": bool(_com_value(app, "Visible")),
        "active_document": None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sw-export",
        description="Export a manifest through the SWCLI Windows/Wine worker",
    )
    parser.add_argument("--list", required=True, dest="manifest")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--outdir")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def run_export(args: argparse.Namespace) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ok": False,
        "action": "docker.batch_export",
    }
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        result["error"] = {
            "type": "PyWin32Unavailable",
            "message": str(exc),
        }
        return result

    pythoncom.CoInitialize()
    app = None
    original_get_active_object = win32com.client.GetActiveObject
    try:
        try:
            # Wine does not reliably publish a directly launched LocalServer32
            # process through GetActiveObject. DispatchEx is the proven DockerSW
            # activation path and also gives this worker clear lifecycle ownership.
            app = win32com.client.DispatchEx(PROG_ID)
            app.UserControl = False
            app.Visible = False
            startup_timeout = float(
                os.environ.get(
                    "SWCLI_HOST_START_TIMEOUT", DEFAULT_STARTUP_TIMEOUT_SECONDS
                )
            )
            print(
                "[DockerSW] Waiting for SOLIDWORKS startup to complete...",
                file=sys.stderr,
                flush=True,
            )
            startup_wait_seconds = wait_windows_host_ready(
                app, timeout_seconds=startup_timeout
            )
            print(
                f"[DockerSW] SOLIDWORKS startup is ready "
                f"({startup_wait_seconds:.1f}s).",
                file=sys.stderr,
                flush=True,
            )
            result["host"] = {
                "ok": True,
                "started": True,
                "startup_wait_seconds": startup_wait_seconds,
                "com": _describe_app(app),
            }
        except Exception as exc:
            result["host"] = {"ok": False, "started": False, "error": _error(exc)}
            result["error"] = {
                "type": "HostStartFailed",
                "message": "SOLIDWORKS COM activation through DispatchEx failed",
            }
            return result

        # Typed SWCLI operations deliberately attach through GetActiveObject.
        # Keep that core policy intact while binding all calls in this Wine worker
        # to the single DispatchEx-owned instance above.
        win32com.client.GetActiveObject = lambda prog_id: app
        batch = batch_export_windows(
            args.manifest,
            workspace=args.workspace,
            outdir=args.outdir,
            overwrite=args.overwrite,
        )
        result["batch"] = batch
        result["ok"] = bool(batch.get("ok"))
        if not result["ok"]:
            result["error"] = batch.get("error") or {
                "type": "BatchExportFailed",
                "message": "SWCLI batch export failed",
            }
    finally:
        win32com.client.GetActiveObject = original_get_active_object
        if app is not None:
            try:
                if _com_value(app, "ActiveDoc") is not None:
                    raise RuntimeError("refusing to stop while a document remains open")
                _com_value(app, "ExitApp")
                result["host_stop"] = {"ok": True, "stopped": True}
            except Exception as exc:
                result["host_stop"] = {"ok": False, "stopped": False, "error": _error(exc)}
                result["ok"] = False
                result["error"] = {
                    "type": "HostStopFailed",
                    "message": "the Docker-owned SOLIDWORKS host did not stop safely",
                }
        pythoncom.CoUninitialize()
    return result


def _print_human(result: Dict[str, Any]) -> None:
    batch = result.get("batch") or {}
    for artifact in batch.get("artifacts", []):
        print(f"[OK] {artifact['format']}: {artifact['path']} ({artifact['size']} bytes)")
    print(
        "[SWCLI SUMMARY] "
        f"success: {batch.get('ok_count', 0)}, "
        f"failed: {batch.get('failed_count', 0)}"
    )
    if not result.get("ok"):
        error = result.get("error") or {}
        print(
            f"[ERROR] {error.get('type', 'ExportFailed')}: "
            f"{error.get('message', 'unknown error')}",
            file=sys.stderr,
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_export(args)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
