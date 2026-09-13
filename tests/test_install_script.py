import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_solidworks.sh"


class InstallScriptValidationTests(unittest.TestCase):
    def create_media(
        self, root: Path, include_vc: bool = True, include_login_manager: bool = True
    ) -> None:
        msi = root / "swwi" / "data" / "solidworks.msi"
        msi.parent.mkdir(parents=True)
        msi.write_bytes(b"test-msi")
        if include_vc:
            vc = root / "PreReqs" / "VCRedist17" / "VC_redist.x64.exe"
            vc.parent.mkdir(parents=True)
            vc.write_bytes(b"test-vc")
        if include_login_manager:
            login_manager = root / "swloginmgr" / "SOLIDWORKS Login Manager.msi"
            login_manager.parent.mkdir(parents=True)
            login_manager.write_bytes(b"test-login-manager")

    def run_validation(
        self, media: Path, *, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        environment = {**os.environ, "LC_ALL": "C"}
        if extra_env:
            environment.update(extra_env)
        return subprocess.run(
            ["bash", str(INSTALLER), "--media", str(media), "--validate-only"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_accepts_complete_official_media_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)
            self.create_media(media)
            result = self.run_validation(media)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Validated complete media layout", result.stdout)

    def test_rejects_media_without_official_vc_prerequisite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)
            self.create_media(media, include_vc=False)
            result = self.run_validation(media)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("VC++ x64 prerequisite is missing", result.stderr)

    def test_rejects_media_without_login_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)
            self.create_media(media, include_login_manager=False)
            result = self.run_validation(media)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SOLIDWORKS Login Manager MSI is missing", result.stderr)

    def test_archive_uses_7z_before_a_false_positive_tar_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "solidworks-media"
            archive.write_bytes(b"fake-iso")
            fake_bin = root / "bin"
            fake_bin.mkdir()

            tar = fake_bin / "tar"
            tar.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
            tar.chmod(0o755)

            seven_zip = fake_bin / "7z"
            seven_zip.write_text(
                """#!/bin/sh
set -eu
case "$1" in
    t) exit 0 ;;
    x)
        destination=""
        for argument in "$@"; do
            case "$argument" in
                -o*) destination="${argument#-o}" ;;
            esac
        done
        test -n "$destination"
        mkdir -p "$destination/swwi/data" "$destination/PreReqs/VCRedist17" "$destination/swloginmgr"
        printf msi >"$destination/swwi/data/solidworks.msi"
        printf vc >"$destination/PreReqs/VCRedist17/VC_redist.x64.exe"
        printf login >"$destination/swloginmgr/SOLIDWORKS Login Manager.msi"
        ;;
    *) exit 2 ;;
esac
""",
                encoding="utf-8",
            )
            seven_zip.chmod(0o755)

            result = self.run_validation(
                archive, extra_env={"PATH": f"{fake_bin}:{os.environ['PATH']}"}
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Validated complete media layout", result.stdout)

    def test_installer_uses_documented_silent_deployment_defaults(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        # Keep the package's own default installation path. Older Wine releases
        # can turn a property containing spaces into MSI error 1639.
        self.assertNotIn('append_default_msi_property "INSTALLDIR"', script)
        self.assertIn('append_default_msi_property "OFFICEOPTION" "3"', script)
        self.assertIn('append_default_msi_property "ADDLOCAL" "SolidWorks"', script)
        self.assertIn("msiexec /i \"${MSI_PATH}\" /qb /norestart", script)
        self.assertIn(
            'msiexec /i "${LOGIN_MANAGER_INSTALLER}" /qn /norestart', script
        )
        self.assertLess(
            script.index('msiexec /i "${LOGIN_MANAGER_INSTALLER}"'),
            script.index('msiexec /i "${MSI_PATH}"'),
        )
        self.assertIn("sldLoginManager.LoginManager", script)
        self.assertIn("mscoree.dll", script)
        self.assertNotIn("RegAsm compatibility stub", script)
        self.assertIn(
            'find "${WINEPREFIX}/drive_c" -type f -iname SLDWORKS.exe', script
        )

    def test_runtime_versions_and_both_mono_patches_are_pinned(self) -> None:
        config = (ROOT / "docker" / "managed_com.env").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        prepare = (ROOT / "docker" / "prepare_managed_com.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('WINE_VERSION="11.16"', config)
        self.assertIn('WINE_MONO_VERSION="11.3.0"', config)
        # Pin every package in the WineHQ dependency chain. Otherwise apt picks
        # the newest wine-devel candidate and rejects the older meta-package.
        self.assertIn('"wine-devel-amd64=${WINE_PACKAGE_VERSION}"', dockerfile)
        self.assertIn('"wine-devel-i386:i386=${WINE_PACKAGE_VERSION}"', dockerfile)
        self.assertIn('"wine-devel=${WINE_PACKAGE_VERSION}"', dockerfile)
        self.assertIn('"winehq-devel=${WINE_PACKAGE_VERSION}"', dockerfile)
        self.assertIn("libmono-2.0-x86.dll", prepare)
        self.assertIn("mscorlib.dll", prepare)
        self.assertIn("regasm-x86.exe", prepare)
        self.assertIn("regasm-x86_64.exe", prepare)


if __name__ == "__main__":
    unittest.main()
