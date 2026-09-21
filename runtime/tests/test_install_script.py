import os
import subprocess
import tempfile
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = RUNTIME_ROOT / "bin" / "sw-install"


class InstallScriptValidationTests(unittest.TestCase):
    def derive_release(self, product_version: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "bash",
                "-c",
                """
                function_source="$(sed -n \
                    '/^solidworks_release_from_product_version()/,/^}/p' "$1")"
                eval "${function_source}"
                solidworks_release_from_product_version "$2"
                """,
                "bash",
                str(INSTALLER),
                product_version,
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def create_media(
        self,
        root: Path,
        include_vc: bool = True,
        include_login_manager: bool = True,
        include_dotnet: bool = True,
        include_toolbox: bool = True,
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
        if include_dotnet:
            dotnet = root / "PreReqs" / "dotNetFx" / "ndp48-x86-x64-allos-enu.exe"
            dotnet.parent.mkdir(parents=True)
            dotnet.write_bytes(b"test-dotnet")
        if include_toolbox:
            toolbox = root / "Toolbox" / "ToolboxUpdates.zip"
            toolbox.parent.mkdir(parents=True)
            toolbox.write_bytes(b"test-toolbox")

    def run_validation(
        self, media: Path, *, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        environment = {
            **os.environ,
            "LC_ALL": "C",
        }
        if extra_env:
            environment.update(extra_env)
        return subprocess.run(
            ["bash", str(INSTALLER), "--media", str(media), "--validate-only"],
            cwd=PROJECT_ROOT,
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

    def test_rejects_media_without_dotnet_prerequisite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)
            self.create_media(media, include_dotnet=False)
            result = self.run_validation(media)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(".NET 4.8 prerequisite is missing", result.stderr)

    def test_rejects_media_without_toolbox_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)
            self.create_media(media, include_toolbox=False)
            result = self.run_validation(media)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Toolbox payload is missing", result.stderr)

    def test_rejects_non_directory_media_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "solidworks-media.iso"
            archive.write_bytes(b"fake-iso")
            result = self.run_validation(archive)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--media must be a mounted or extracted directory", result.stderr)

    def test_installer_uses_documented_silent_deployment_defaults(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('if [ -n "${TARGET_INSTALL_DIR}" ]; then', script)
        self.assertIn('normalized_install_dir="${normalized_install_dir//Program Files/PROGRA~1}"', script)
        self.assertIn('append_default_msi_property "INSTALLDIR" "${normalized_install_dir}"', script)
        self.assertIn('ln -sfn "Program Files" "${WINEPREFIX}/drive_c/PROGRA~1"', script)
        self.assertIn('append_default_msi_property "OFFICEOPTION" "3"', script)
        self.assertIn('append_default_msi_property "INSTALLLEVEL" "100"', script)
        self.assertIn(
            'append_default_msi_property "ADDLOCAL" "SolidWorks,ProgramFiles,'
            'i386_ProgramFiles,i386_ThirdPtyFiles,i386_DCubeFiles,i386_SWFiles,'
            'i386_VistaFiles"',
            script,
        )
        self.assertIn(
            'append_default_msi_property "TOOLBOXFOLDER" "C:\\\\SWData"', script
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
        self.assertIn("timeout --foreground 30 wineserver -w", script)
        self.assertIn("SW MESSAGE\\|ERROR\\|", script)
        self.assertNotIn("Tail of ${LOG_DIR}/solidworks-msi.log", script)

    def test_eula_acceptance_is_explicit_and_not_preseeded(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        tweaks = (RUNTIME_ROOT / "registry" / "headless_tweaks.reg").read_text(
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
        dockerfile = (RUNTIME_ROOT / "Dockerfile.base").read_text(
            encoding="utf-8"
        )
        init_script = (RUNTIME_ROOT / "init_wineprefix.sh").read_text(
            encoding="utf-8"
        )
        entrypoint = (RUNTIME_ROOT / "entrypoint.sh").read_text(
            encoding="utf-8"
        )
        self.assertFalse((RUNTIME_ROOT / "registry" / "sw_com_classes.reg").exists())
        self.assertNotIn("sw_com_classes.reg", dockerfile)
        self.assertNotIn("sw_com_classes.reg", init_script)
        self.assertNotIn("sw_com_classes.reg", entrypoint)
        self.assertIn("HKCR\\SldWorks.Application\\CLSID", script)
        self.assertIn("LocalServer32", script)
        self.assertIn("VersionIndependentProgID", script)
        self.assertIn("TypeLib", script)

    def test_runtime_versions_and_both_mono_patches_are_pinned(self) -> None:
        config = (RUNTIME_ROOT / "managed_com.env").read_text(encoding="utf-8")
        dockerfile = (RUNTIME_ROOT / "Dockerfile.base").read_text(
            encoding="utf-8"
        )
        prepare = (RUNTIME_ROOT / "prepare_managed_com.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('WINE_VERSION="11.16"', config)
        self.assertIn('WINE_MONO_VERSION="11.3.0"', config)
        self.assertIn(
            'MONO_PATCH_RELEASE="wine-mono-11.3.0-X86StdcallFix-ComRegistration-v3"',
            config,
        )
        self.assertIn(
            'MONO_PATCH_SHA256="950509a51c72ab9347ad49548f297d7dc81c98a56609f102b26fb30fa3e9f7ea"',
            config,
        )
        self.assertIn(
            'MONO_MSCORLIB_SHA256="dbf8fe45f524f5ac0ca87af8d70d08bcbb0fa46e2048a8780d577fb246542eba"',
            config,
        )
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

    def test_runtime_includes_json_processing_tool(self) -> None:
        dockerfile = (RUNTIME_ROOT / "Dockerfile.base").read_text(
            encoding="utf-8"
        )
        self.assertIn("        jq \\", dockerfile.splitlines())

    def test_optional_vnc_monitoring_is_owned_by_the_runtime_entrypoint(self) -> None:
        dockerfile = (RUNTIME_ROOT / "Dockerfile.base").read_text(
            encoding="utf-8"
        )
        entrypoint = (RUNTIME_ROOT / "entrypoint.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("        openbox \\\n", dockerfile)
        self.assertIn("        x11vnc \\\n", dockerfile)
        self.assertIn('export VNC_ENABLE="${VNC_ENABLE:-false}"', entrypoint)
        self.assertIn('export VNC_VIEW_ONLY="${VNC_VIEW_ONLY:-true}"', entrypoint)
        self.assertIn('if is_enabled "${VNC_ENABLE}"; then', entrypoint)
        self.assertIn('VNC_ARGS+=(-viewonly)', entrypoint)
        self.assertIn('x11vnc "${VNC_ARGS[@]}"', entrypoint)

    def test_serial_number_cli_and_msi_properties(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("--serial-solidworks", script)
        self.assertIn("--serial-simulation", script)
        self.assertIn("--serial-motion", script)
        self.assertIn("--serial-mbd", script)
        self.assertIn("--license-server", script)
        self.assertIn("--install-dir", script)
        self.assertIn('SW_TARGET_INSTALL_DIR', script)
        self.assertIn('SW_SERIAL_SOLIDWORKS', script)
        self.assertIn('SW_SERIAL_SIMULATION', script)
        self.assertIn('SW_SERIAL_MOTION', script)
        self.assertIn('SW_SERIAL_MBD', script)
        self.assertIn('SW_LICENSE_SERVER', script)
        self.assertIn('append_default_msi_property "SOLIDWORKSSERIALNUMBER"', script)
        self.assertIn('append_default_msi_property "SIMULATIONSERIALNUMBER"', script)
        self.assertIn('append_default_msi_property "MOTIONSERIALNUMBER"', script)
        self.assertIn('append_default_msi_property "MBDSERIALNUMBER"', script)
        self.assertIn('append_default_msi_property "SERVERLIST"', script)
        # Ensure we do NOT touch registry manually for serials (MSI writes them natively)
        self.assertNotIn('wine reg add "HKLM\\SOFTWARE\\SolidWorks\\Licenses\\Serial Numbers"', script)


if __name__ == "__main__":
    unittest.main()
