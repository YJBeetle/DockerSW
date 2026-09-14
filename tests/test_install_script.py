import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "sw-install"
VERSION_HELPER = ROOT / "scripts" / "lib" / "solidworks_version.sh"


class InstallScriptValidationTests(unittest.TestCase):
    def derive_release(self, product_version: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "bash",
                "-c",
                '. "$1"; solidworks_release_from_product_version "$2"',
                "bash",
                str(VERSION_HELPER),
                product_version,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

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
        self.assertIn('append_default_msi_property "INSTALLLEVEL" "100"', script)
        self.assertIn(
            'append_default_msi_property "ADDLOCAL" "SolidWorks,ProgramFiles,'
            'i386_ProgramFiles,i386_ThirdPtyFiles,i386_DCubeFiles,i386_SWFiles,'
            'i386_VistaFiles"',
            script,
        )
        self.assertIn("msiexec /i \"${MSI_PATH}\" /qb /norestart", script)
        self.assertIn(
            'msiexec /i "${LOGIN_MANAGER_INSTALLER}" /qn /norestart', script
        )
        self.assertLess(
            script.index('msiexec /i "${LOGIN_MANAGER_INSTALLER}"'),
            script.index('Importing private installer registry file:'),
        )
        self.assertLess(
            script.index('Importing private installer registry file:'),
            script.index('msiexec /i "${MSI_PATH}"'),
        )
        self.assertIn("sldLoginManager.LoginManager", script)
        self.assertIn("mscoree.dll", script)
        self.assertNotIn("RegAsm compatibility stub", script)
        self.assertIn(
            'find "${WINEPREFIX}/drive_c" -type f -iname SLDWORKS.exe', script
        )
        self.assertIn('info "Stopping background Wine helpers', script)
        self.assertIn("wineserver -k || true", script)

    def test_eula_acceptance_is_explicit_and_not_preseeded(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        tweaks = (ROOT / "docker" / "registry" / "headless_tweaks.reg").read_text(
            encoding="utf-8"
        )
        self.assertIn("--accept-eula", script)
        self.assertIn("ACCEPT_EULA=false", script)
        self.assertIn('msiinfo export "${MSI_PATH}" Property', script)
        self.assertIn("solidworks_release_from_product_version", script)
        self.assertIn(
            'eula_value="EULA Accepted SP${service_pack_major}.${service_pack_minor}"',
            script,
        )
        self.assertNotIn("EULA Accepted", tweaks)
        self.assertNotIn("EnableSldLoginManager", tweaks)

    def test_product_version_maps_internal_update_code_to_service_pack(self) -> None:
        cases = {
            "32.100.5048": "2024\t0\t0\n",
            "33.150.0053": "2025\t5\t0\n",
            "34.132.0140": "2026\t3\t2\n",
        }
        for product_version, expected in cases.items():
            with self.subTest(product_version=product_version):
                result = self.derive_release(product_version)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_product_version_rejects_non_core_msi_update_codes(self) -> None:
        for product_version in ("33.50.0053", "33.200.0001", "invalid"):
            with self.subTest(product_version=product_version):
                result = self.derive_release(product_version)
                self.assertNotEqual(result.returncode, 0)

    def test_solidworks_com_registration_comes_from_the_official_msi(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        init_script = (ROOT / "docker" / "init_wineprefix.sh").read_text(
            encoding="utf-8"
        )
        entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text(
            encoding="utf-8"
        )
        self.assertFalse((ROOT / "docker" / "registry" / "sw_com_classes.reg").exists())
        self.assertNotIn("sw_com_classes.reg", dockerfile)
        self.assertNotIn("sw_com_classes.reg", init_script)
        self.assertNotIn("sw_com_classes.reg", entrypoint)
        self.assertIn("HKCR\\SldWorks.Application\\CLSID", script)
        self.assertIn("LocalServer32", script)
        self.assertIn("VersionIndependentProgID", script)
        self.assertIn("TypeLib", script)

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
