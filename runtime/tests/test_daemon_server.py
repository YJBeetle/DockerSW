#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for Wine daemon server and sandbox execution engine (daemon_server.py).
Designed to run in standard Python 3 environments without requiring Windows, Wine, or GPU.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure runtime/scripts is in import path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


class TestDaemonServerSandbox(unittest.TestCase):
    def setUp(self):
        # We will import daemon_server dynamically in tests or test functions
        import daemon_server
        self.daemon_mod = daemon_server

    def test_sandbox_executes_code_and_captures_stdout(self):
        sw_mock = MagicMock()
        code = 'print("hello world from sw sandbox")'
        result = self.daemon_mod.execute_code_snippet(
            code=code,
            args=["--test"],
            timeout_s=5,
            sw_app=sw_mock,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello world from sw sandbox", result["stdout"])
        self.assertEqual(result["stderr"], "")
        self.assertIsInstance(result["duration_ms"], (int, float))

    def test_sandbox_injected_context_variables(self):
        sw_mock = MagicMock()
        code = """
import sys
assert swApp is not None
assert args == ["arg1", "arg2"]
assert callable(to_win_path)
assert callable(to_linux_path)
assert callable(save_canvas)
assert __file__ == "<sw-cli>"
assert sys.argv[0] == "<sw-cli>"
set_output({"status": "verified", "number": 42})
"""
        result = self.daemon_mod.execute_code_snippet(
            code=code,
            args=["arg1", "arg2"],
            timeout_s=5,
            sw_app=sw_mock,
        )

        self.assertTrue(result["success"], f"Failed with stderr: {result['stderr']}")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["data"], {"status": "verified", "number": 42})

    def test_sandbox_custom_filename(self):
        sw_mock = MagicMock()
        code = """
import sys
assert __file__ == "/path/to/my_script.py"
assert sys.argv[0] == "/path/to/my_script.py"
assert sys.argv[1] == "--arg1"
"""
        result = self.daemon_mod.execute_code_snippet(
            code=code,
            args=["--arg1"],
            timeout_s=5,
            sw_app=sw_mock,
            filename="/path/to/my_script.py",
        )
        self.assertTrue(result["success"], f"Failed with stderr: {result['stderr']}")
        self.assertEqual(result["exit_code"], 0)

    def test_sandbox_save_canvas_helper(self):
        sw_mock = MagicMock()
        active_doc_mock = MagicMock()
        sw_mock.ActiveDoc = active_doc_mock
        ext_mock = MagicMock()
        active_doc_mock.Extension = ext_mock
        ext_mock.SaveAs3.return_value = True

        code = """
save_canvas("my_model.png")
"""
        result = self.daemon_mod.execute_code_snippet(
            code=code,
            args=[],
            timeout_s=5,
            sw_app=sw_mock,
        )

        self.assertTrue(result["success"], f"Failed: {result['stderr']}")
        ext_mock.SaveAs3.assert_called_once()
        call_args = ext_mock.SaveAs3.call_args[0]
        self.assertTrue(call_args[0].endswith("my_model.png") or "\\my_model.png" in call_args[0])

    def test_sandbox_captures_exceptions(self):
        sw_mock = MagicMock()
        code = "raise ValueError('intentional error for test')"
        result = self.daemon_mod.execute_code_snippet(
            code=code,
            args=[],
            timeout_s=5,
            sw_app=sw_mock,
        )

        self.assertFalse(result["success"])
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("ValueError: intentional error for test", result["stderr"])

    def test_sandbox_captures_syntax_errors(self):
        sw_mock = MagicMock()
        code = "def syntax_err("
        result = self.daemon_mod.execute_code_snippet(
            code=code,
            args=[],
            timeout_s=5,
            sw_app=sw_mock,
        )

        self.assertFalse(result["success"])
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("SyntaxError", result["stderr"])

    def test_sandbox_captures_sys_exit(self):
        sw_mock = MagicMock()
        code = "import sys; sys.exit(7)"
        result = self.daemon_mod.execute_code_snippet(
            code=code,
            args=[],
            timeout_s=5,
            sw_app=sw_mock,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["exit_code"], 7)

    def test_sandbox_timeout(self):
        sw_mock = MagicMock()
        code = "import time; time.sleep(2)"
        result = self.daemon_mod.execute_code_snippet(
            code=code,
            args=[],
            timeout_s=0.2,
            sw_app=sw_mock,
        )

        self.assertFalse(result["success"])
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("timed out", result["stderr"].lower())

    def test_sandbox_worker_thread_com_initialize(self):
        mock_pythoncom = MagicMock()
        with patch.object(self.daemon_mod, "pythoncom", mock_pythoncom), \
             patch.object(self.daemon_mod, "HAS_WIN32COM", True):
            result = self.daemon_mod.execute_code_snippet(
                code="print('running com initialized')",
                args=[],
                timeout_s=5,
            )
            self.assertTrue(result["success"])
            mock_pythoncom.CoInitialize.assert_called_once()
            mock_pythoncom.CoUninitialize.assert_called_once()

    def test_sandbox_real_com_affinity_runs_synchronously(self):
        import threading
        calling_tid = threading.get_ident()
        script_tid = []

        class MockCOMDispatch:
            def __init__(self):
                self._oleobj_ = MagicMock()

        com_sw_mock = MockCOMDispatch()

        code = """
import threading
print(f'TID:{threading.get_ident()}')
print('executed synchronously on COM thread')
"""
        mock_pythoncom = MagicMock()
        with patch.object(self.daemon_mod, "pythoncom", mock_pythoncom), \
             patch.object(self.daemon_mod, "HAS_WIN32COM", True):
            result = self.daemon_mod.execute_code_snippet(
                code=code,
                args=[],
                timeout_s=5,
                sw_app=com_sw_mock,
            )
            self.assertTrue(result["success"], f"Failed: {result['stderr']}")
            self.assertIn(f"TID:{calling_tid}", result["stdout"])
            # CoInitialize called, but CoUninitialize NOT called to keep resident STA alive
            mock_pythoncom.CoInitialize.assert_called_once()
            mock_pythoncom.CoUninitialize.assert_not_called()

    def test_path_conversion(self):
        win_path = self.daemon_mod.to_win_path("/workspace/model.SLDPRT")
        self.assertEqual(win_path, "Z:\\workspace\\model.SLDPRT")

        linux_path = self.daemon_mod.to_linux_path("Z:\\workspace\\model.SLDPRT")
        self.assertEqual(linux_path, "/workspace/model.SLDPRT")

    def test_execute_script_file_success(self):
        import tempfile
        sw_mock = MagicMock()
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("""
import sys
assert __file__.endswith(".py")
assert sys.argv[1] == "arg1"
assert args == ["arg1"]
assert swApp is not None
print("running from file successfully")
set_output({"calculated": 42})
""")
            temp_path = f.name

        try:
            result = self.daemon_mod.execute_script_file(
                script_path=temp_path,
                args=["arg1"],
                timeout_s=5,
                sw_app=sw_mock,
            )
            self.assertTrue(result["success"], f"Failed: {result['stderr']}")
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("running from file successfully", result["stdout"])
            self.assertEqual(result["data"], {"calculated": 42})
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_execute_script_file_sibling_import(self):
        import tempfile
        sw_mock = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            sibling_py = os.path.join(tmpdir, "my_sibling.py")
            with open(sibling_py, "w") as f:
                f.write("MAGIC = 9999\n")

            main_py = os.path.join(tmpdir, "main_entry.py")
            with open(main_py, "w") as f:
                f.write("""
import my_sibling
print(f"Imported sibling: {my_sibling.MAGIC}")
set_output({"magic": my_sibling.MAGIC})
""")

            result = self.daemon_mod.execute_script_file(
                script_path=main_py,
                args=[],
                timeout_s=5,
                sw_app=sw_mock,
            )
            self.assertTrue(result["success"], f"Failed: {result['stderr']}")
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("Imported sibling: 9999", result["stdout"])
            self.assertEqual(result["data"], {"magic": 9999})

    def test_execute_script_file_set_output(self):
        import tempfile
        sw_mock = MagicMock()
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("""
set_output({"auto_key": "auto_val", "code": 123})
""")
            temp_path = f.name

        try:
            result = self.daemon_mod.execute_script_file(
                script_path=temp_path,
                timeout_s=5,
                sw_app=sw_mock,
            )
            self.assertTrue(result["success"])
            self.assertEqual(result["data"], {"auto_key": "auto_val", "code": 123})
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_execute_script_file_not_found(self):
        result = self.daemon_mod.execute_script_file(
            script_path="/nonexistent/path/to/missing_script.py",
            timeout_s=5,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("Script file not found", result["stderr"])


class TestDaemonServerHandler(unittest.TestCase):
    def setUp(self):
        import daemon_server
        self.daemon_mod = daemon_server

    def test_health_check_payload(self):
        server_state = self.daemon_mod.ServerState()
        server_state.sw_connected = True
        server_state.sw_version = "33.5.0"
        payload = server_state.get_health_payload()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["ready"])
        self.assertTrue(payload["sw_connected"])
        self.assertEqual(payload["sw_version"], "33.5.0")
        self.assertIn("uptime_s", payload)

    def test_canvas_export_logic(self):
        server_state = self.daemon_mod.ServerState()
        sw_mock = MagicMock()
        doc_mock = MagicMock()
        doc_mock.GetTitle.return_value = "widget.SLDPRT"
        sw_mock.ActiveDoc = doc_mock
        server_state.sw_app = sw_mock
        server_state.sw_connected = True

        res = server_state.export_canvas(target_path="/tmp/test_view.png")
        self.assertTrue(res["success"])
        self.assertEqual(res["doc_title"], "widget.SLDPRT")

    def test_init_solidworks_com_user_control(self):
        mock_win32 = MagicMock()
        mock_sw = MagicMock()
        mock_win32.client.DispatchEx.return_value = mock_sw
        mock_sw.RevisionNumber.return_value = "33.0"

        with patch.object(self.daemon_mod, "win32com", mock_win32), \
             patch.object(self.daemon_mod, "pythoncom", MagicMock()), \
             patch.object(self.daemon_mod, "HAS_WIN32COM", True):
            self.daemon_mod.init_solidworks_com(visible=True, user_control=True)
            self.assertTrue(mock_sw.Visible)
            self.assertTrue(mock_sw.UserControl)

            self.daemon_mod.init_solidworks_com(visible=False, user_control=False)
            self.assertFalse(mock_sw.Visible)
            self.assertFalse(mock_sw.UserControl)

    def test_handler_execute_dispatch_path_and_code(self):
        import io
        handler = self.daemon_mod.DaemonRequestHandler.__new__(self.daemon_mod.DaemonRequestHandler)
        sent_jsons = []
        handler._send_json = lambda code, data: sent_jsons.append((code, data))
        handler.headers = {}
        handler.path = "/v1/execute"

        # Missing path or code -> 400
        handler.rfile = io.BytesIO(b"{}")
        handler.headers["Content-Length"] = "2"
        handler.do_POST()
        self.assertEqual(sent_jsons[-1][0], 400)

        # Code execution -> 200
        sent_jsons.clear()
        body = json.dumps({"code": "print('hello_handler')"}).encode("utf-8")
        handler.rfile = io.BytesIO(body)
        handler.headers["Content-Length"] = str(len(body))
        handler.do_POST()
        self.assertEqual(sent_jsons[-1][0], 200)
        self.assertTrue(sent_jsons[-1][1]["success"])
        self.assertIn("hello_handler", sent_jsons[-1][1]["stdout"])


if __name__ == "__main__":
    unittest.main()
