import argparse
import types
import sys
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "SWCLI" / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT / "runtime" / "scripts"))

import swcli_docker_export


class DockerExportRunnerTests(unittest.TestCase):
    def _args(self) -> argparse.Namespace:
        return argparse.Namespace(
            manifest="C:\\list.txt",
            workspace="C:\\workspace",
            outdir="C:\\output",
            overwrite=False,
            as_json=False,
        )

    @mock.patch.object(swcli_docker_export, "batch_export_windows")
    def test_dispatch_owned_host_is_used_and_stopped_after_success(self, batch):
        app = mock.Mock()
        app.ActiveDoc = None
        app.RevisionNumber = "33.5"
        app.GetProcessID = 123
        app.Visible = False
        exit_app = mock.Mock()
        app.ExitApp = lambda: exit_app()
        fake_client = types.ModuleType("win32com.client")
        fake_client.DispatchEx = mock.Mock(return_value=app)
        fake_client.GetActiveObject = mock.Mock()
        fake_win32com = types.ModuleType("win32com")
        fake_win32com.client = fake_client
        fake_pythoncom = types.ModuleType("pythoncom")
        fake_pythoncom.CoInitialize = mock.Mock()
        fake_pythoncom.CoUninitialize = mock.Mock()
        batch.return_value = {"ok": True, "ok_count": 1, "failed_count": 0}

        with mock.patch.dict(
            sys.modules,
            {
                "pythoncom": fake_pythoncom,
                "win32com": fake_win32com,
                "win32com.client": fake_client,
            },
        ):
            result = swcli_docker_export.run_export(self._args())

        self.assertTrue(result["ok"])
        fake_client.DispatchEx.assert_called_once_with("SldWorks.Application")
        batch.assert_called_once_with(
            "C:\\list.txt",
            workspace="C:\\workspace",
            outdir="C:\\output",
            overwrite=False,
        )
        exit_app.assert_called_once_with()
        fake_pythoncom.CoInitialize.assert_called_once_with()
        fake_pythoncom.CoUninitialize.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
