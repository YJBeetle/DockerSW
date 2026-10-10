import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = RUNTIME_ROOT / "bin" / "sw-install"


class InstallScriptValidationTests(unittest.TestCase):
    def create_media(
        self,
        root: Path,
        include_vc: bool = True,
        include_vba: bool = True,
        include_vba_english: bool = True,
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
        for include, filename in (
            (include_vba, "vba71.msi"),
            (include_vba_english, "vba71_1033.msi"),
        ):
            if include:
                package = root / "PreReqs" / "VBA" / filename
                package.parent.mkdir(parents=True, exist_ok=True)
                package.write_bytes(b"test-vba")
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

    def test_rejects_media_without_either_official_vba_package(self) -> None:
        for filename, options in (
            ("vba71.msi", {"include_vba": False}),
            ("vba71_1033.msi", {"include_vba_english": False}),
        ):
            with self.subTest(package=filename), tempfile.TemporaryDirectory() as temporary:
                media = Path(temporary)
                self.create_media(media, **options)
                result = self.run_validation(media)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"PreReqs/VBA/{filename}", result.stderr)

    def test_rejects_empty_official_vba_packages(self) -> None:
        for filename in ("vba71.msi", "vba71_1033.msi"):
            with self.subTest(package=filename), tempfile.TemporaryDirectory() as temporary:
                media = Path(temporary)
                self.create_media(media)
                (media / "PreReqs" / "VBA" / filename).write_bytes(b"")
                result = self.run_validation(media)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"PreReqs/VBA/{filename}", result.stderr)

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
        self.assertIn("disable_solidworks_resource_monitor", script)
        self.assertIn("-iname 'sldProcMon.exe'", script)
        self.assertIn(
            'mv -- "${resource_monitor}" "${disabled_resource_monitor}"', script
        )
        self.assertLess(
            script.index("validate_solidworks_com_registration\n"),
            script.index("disable_solidworks_resource_monitor\n"),
        )
        self.assertIn('info "Stopping background Wine helpers', script)
        self.assertIn("wineserver -k || true", script)
        self.assertIn("timeout --foreground 30 wineserver -w", script)
        self.assertIn("SW MESSAGE\\|ERROR\\|", script)
        self.assertNotIn("Tail of ${LOG_DIR}/solidworks-msi.log", script)

    def test_vba_installation_precedes_login_manager_and_core_msi(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        self.assertLess(
            script.index('run_installer "Microsoft VC++ x64 prerequisite"'),
            script.index("\ninstall_vba_prerequisites\n"),
        )
        self.assertLess(
            script.index("\ninstall_vba_prerequisites\n"),
            script.index('msiexec /i "${LOGIN_MANAGER_INSTALLER}"'),
        )
        self.assertLess(
            script.index('msiexec /i "${LOGIN_MANAGER_INSTALLER}"'),
            script.index('msiexec /i "${MSI_PATH}"'),
        )
        vba_function = self.extract_function("install_vba_prerequisites")
        self.assertIn('"${VBA_INSTALLER}" "${VBA_LANGUAGE_INSTALLER}"', vba_function)
        self.assertNotIn("reg add", vba_function)
        self.assertNotRegex(vba_function, r"\bcp\b")
        self.assertNotIn(".msp", vba_function)

    def test_vba_media_context_matches_ci_and_is_read_only(self) -> None:
        dockerfile = (PROJECT_ROOT / "preinstall" / "Dockerfile").read_text(encoding="utf-8")
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
        self.assertIn(
            "--mount=type=bind,from=sw-vba,target=/mnt/sw-media/PreReqs/VBA,ro",
            dockerfile,
        )
        self.assertIn('--build-context "sw-vba=preinstall/media/PreReqs/VBA"', workflow)
        media_checks = workflow.split('sudo mount -o loop,ro,noatime', 1)[1].split(
            "- name: Fetch test activation assets", 1
        )[0]
        self.assertIn("for package in vba71.msi vba71_1033.msi", media_checks)
        self.assertIn('test -s "${SW_MEDIA_MOUNT}/PreReqs/VBA/${package}"', media_checks)
        self.assertIn("Missing official VBA prerequisite: PreReqs/VBA/${package}", media_checks)
        self.assertIn('steps.check-installed.outputs.exists }}" != "true"', media_checks)
        # The new mounted prerequisite changes the installation recipe digest;
        # the runtime digest also tracks changes to sw-install.
        self.assertIn('recipe_digest="$(sha256sum preinstall/Dockerfile', workflow)
        self.assertIn('"${runtime_digest}" \\\n              "${recipe_digest}"', workflow)

    @staticmethod
    def extract_function(name: str) -> str:
        script = INSTALLER.read_text(encoding="utf-8")
        match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", script, re.MULTILINE | re.DOTALL)
        if match is None:
            raise AssertionError(f"Installer function not found: {name}")
        return match.group(0)

    def run_vba_installation(
        self,
        root: Path,
        *,
        missing_dll: str | None = None,
        empty_dll: str | None = None,
        x86_only: bool = False,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], list[dict[str, object]]]:
        media = root / "media with spaces"
        self.create_media(media)
        prefix = root / "wine-prefix"
        program_files = "Program Files (x86)" if x86_only else "Program Files"
        # Use mixed case to model Windows' case-insensitive installation paths.
        runtime_directory = (
            prefix / "drive_c" / program_files / "Common Files" /
            "microsoft shared" / "VBA" / "VBA7.1"
        )
        for relative in ("VBE7.DLL", "1033/VBE7INTL.DLL"):
            if relative != missing_dll:
                dll = runtime_directory / relative.lower()
                dll.parent.mkdir(parents=True, exist_ok=True)
                dll.write_bytes(b"" if relative == empty_dll else b"test-dll")
        log_directory = root / "private logs"
        log_directory.mkdir()
        binaries = root / "bin"
        binaries.mkdir()
        command_log = root / "calls.jsonl"
        shim = f"#!{sys.executable}\n" + '''
import json
import os
import subprocess
import sys
from pathlib import Path

program = Path(sys.argv[0]).name
arguments = sys.argv[1:]
log_path = Path(os.environ["VBA_TEST_COMMAND_LOG"])
with log_path.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"program": program, "arguments": arguments}) + "\\n")
if program == "timeout":
    if os.environ.get("VBA_TEST_TIMEOUT_PACKAGE") and any(
        Path(argument).name == os.environ["VBA_TEST_TIMEOUT_PACKAGE"]
        for argument in arguments
    ):
        sys.exit(124)
    sys.exit(subprocess.run(arguments[2:], check=False).returncode)
if program == "winepath":
    print("Z:" + arguments[1].replace("/", "\\\\"))
elif program == "wine":
    if Path(arguments[2]).name == os.environ.get("VBA_TEST_FAILED_PACKAGE"):
        sys.exit(1)
elif program == "wineserver":
    calls = [json.loads(line) for line in log_path.read_text().splitlines()]
    package = next(call["arguments"][2] for call in reversed(calls) if call["program"] == "wine")
    if Path(package).name == os.environ.get("VBA_TEST_UNSETTLED_PACKAGE"):
        sys.exit(1)
'''
        for name in ("wine", "winepath", "wineserver", "timeout"):
            binary = binaries / name
            binary.write_text(shim, encoding="utf-8")
            binary.chmod(0o755)
        script = "set -Eeuo pipefail\n" + "\n".join(
            self.extract_function(name)
            for name in ("die", "info", "run_installer", "install_vba_prerequisites")
        ) + "\ninstall_vba_prerequisites\n"
        environment = {
            **os.environ,
            "PATH": f"{binaries}:{os.environ['PATH']}",
            "LC_ALL": "C",
            "WINEPREFIX": str(prefix),
            "VBA_INSTALLER": str(media / "PreReqs" / "VBA" / "vba71.msi"),
            "VBA_LANGUAGE_INSTALLER": str(media / "PreReqs" / "VBA" / "vba71_1033.msi"),
            "LOG_DIR": str(log_directory),
            "INSTALL_TIMEOUT": "17",
            "VBA_TEST_COMMAND_LOG": str(command_log),
        }
        environment.update(extra_env or {})
        completed = subprocess.run(
            ["bash", "-c", script], env=environment,
            text=True, capture_output=True, check=False, timeout=10,
        )
        calls = [json.loads(line) for line in command_log.read_text().splitlines()]
        return completed, calls

    def test_runs_both_vba_packages_with_protected_logs_and_settles_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result, calls = self.run_vba_installation(Path(temporary))
            self.assertEqual(result.returncode, 0, result.stderr)
            commands = [call for call in calls if call["program"] in ("wine", "wineserver")]
            self.assertEqual([call["program"] for call in commands], ["wine", "wineserver"] * 2)
            for index, package in enumerate(("vba71.msi", "vba71_1033.msi")):
                arguments = commands[index * 2]["arguments"]
                self.assertEqual(arguments[:2], ["msiexec", "/i"])
                self.assertTrue(arguments[2].endswith(f"/PreReqs/VBA/{package}"))
                self.assertEqual(arguments[3:6], ["/qn", "/norestart", "/l*v"])
                self.assertTrue(arguments[6].endswith(f"{package[:-4]}-install.log"))
                self.assertIn("private logs", arguments[6])
                self.assertEqual(commands[index * 2 + 1]["arguments"], ["-w"])
            timeouts = [call["arguments"] for call in calls if call["program"] == "timeout"]
            self.assertEqual([arguments[:2] for arguments in timeouts], [
                ["--foreground", "17"], ["--foreground", "300"],
                ["--foreground", "17"], ["--foreground", "300"],
            ])
            self.assertIn("Verified official VBA 7.1", result.stdout)

    def test_vba_failure_or_timeout_stops_before_next_package(self) -> None:
        for environment, expected_error in (
            ({"VBA_TEST_FAILED_PACKAGE": "vba71.msi"}, "failed with exit status 1"),
            ({"VBA_TEST_TIMEOUT_PACKAGE": "vba71.msi"}, "timed out after 17 seconds"),
            ({"VBA_TEST_UNSETTLED_PACKAGE": "vba71.msi"}, "did not settle after VBA prerequisite vba71.msi"),
        ):
            with self.subTest(environment=environment), tempfile.TemporaryDirectory() as temporary:
                result, calls = self.run_vba_installation(Path(temporary), extra_env=environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr)
                self.assertFalse(any(
                    any(Path(argument).name == "vba71_1033.msi" for argument in call["arguments"])
                    for call in calls
                ))
                self.assertNotIn("Verified official VBA 7.1", result.stdout)

    def test_vba_runtime_gate_rejects_missing_or_empty_native_dlls(self) -> None:
        for relative in ("VBE7.DLL", "1033/VBE7INTL.DLL"):
            for condition in ("missing_dll", "empty_dll"):
                with self.subTest(relative=relative, condition=condition), tempfile.TemporaryDirectory() as temporary:
                    result, _ = self.run_vba_installation(Path(temporary), **{condition: relative})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(f"required native runtime DLL is missing: {relative}", result.stderr)
                    self.assertNotIn("Verified official VBA 7.1", result.stdout)

    def test_vba_runtime_gate_does_not_accept_only_x86_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result, _ = self.run_vba_installation(Path(temporary), x86_only=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("native Common Files is missing", result.stderr)

    def test_solidworks_com_registration_comes_from_the_official_msi(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        dockerfile = (RUNTIME_ROOT / "Dockerfile").read_text(
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

    def test_runtime_versions_and_shared_mono_engines_are_pinned(self) -> None:
        config = (RUNTIME_ROOT / "managed_com.env").read_text(encoding="utf-8")
        dockerfile = (RUNTIME_ROOT / "Dockerfile").read_text(
            encoding="utf-8"
        )
        prepare = (RUNTIME_ROOT / "prepare_managed_com.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('WINE_VERSION="11.16"', config)
        self.assertIn('WINE_PACKAGE_VERSION="11.16~jammy-1"', config)
        self.assertIn(
            'WINE_SOURCE_SHA256="c66e2090343dcd727f7f7fd2f87ee0bfb0b118790c1d745ab7b8a4c3a4197f2f"',
            config,
        )
        self.assertIn('WINE_MONO_VERSION="11.3.0"', config)
        self.assertIn(
            'MONO_PATCH_RELEASE="wine-mono-11.3.0-X86StdcallFix-ComRegistration-CCWFix"',
            config,
        )
        self.assertIn(
            'MONO_PATCH_SHA256="d22ce0075cf56a0102455f435d4328da4e6c54a62504c51793f623faf58f989c"',
            config,
        )
        self.assertIn(
            'MONO_MSCORLIB_SHA256="dd81a8c4d651c35f03387cf8ecef46cb5a171c072b19f23332c4adfb9980cea3"',
            config,
        )
        # Pin every package in the WineHQ dependency chain. Otherwise apt picks
        # the newest wine-devel candidate and rejects the older meta-package.
        self.assertIn('"wine-devel-amd64=${WINE_PACKAGE_VERSION}"', dockerfile)
        self.assertIn('"wine-devel-i386:i386=${WINE_PACKAGE_VERSION}"', dockerfile)
        self.assertIn('"wine-devel=${WINE_PACKAGE_VERSION}"', dockerfile)
        self.assertIn('"winehq-devel=${WINE_PACKAGE_VERSION}"', dockerfile)
        self.assertIn("libmono-2.0-x86.dll", prepare)
        self.assertIn("libmono-2.0-x86_64.dll", prepare)
        self.assertIn('${MONO_X64_SHA256}', prepare)
        self.assertIn("mscorlib.dll", prepare)
        self.assertIn("regasm-x86.exe", prepare)
        self.assertIn("regasm-x86_64.exe", prepare)

    def test_runtime_includes_json_processing_tool(self) -> None:
        dockerfile = (RUNTIME_ROOT / "Dockerfile").read_text(
            encoding="utf-8"
        )
        self.assertIn("        jq \\", dockerfile.splitlines())

    def test_runtime_configures_noto_for_ui_without_replacing_drawing_fonts(self) -> None:
        dockerfile = (RUNTIME_ROOT / "Dockerfile").read_text(encoding="utf-8")
        init_script = (RUNTIME_ROOT / "init_wineprefix.sh").read_text(
            encoding="utf-8"
        )
        font_script = (RUNTIME_ROOT / "configure_ui_fonts.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("        fonts-noto-cjk \\", dockerfile.splitlines())
        self.assertIn("configure_ui_fonts.sh", dockerfile)
        self.assertIn(
            "/usr/local/lib/sw-runtime/configure_ui_fonts.sh", init_script
        )
        entrypoint = (RUNTIME_ROOT / "entrypoint.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "/usr/local/lib/sw-runtime/configure_ui_fonts.sh", entrypoint
        )
        self.assertLess(
            entrypoint.index("/usr/local/lib/sw-runtime/configure_ui_fonts.sh"),
            entrypoint.index('C_SW_TARGET="${WINEPREFIX}/drive_c/Program Files/SOLIDWORKS"'),
        )
        self.assertIn("NotoSansCJK-Regular.ttc,Noto Sans CJK SC", font_script)
        self.assertIn("/v 'MS Shell Dlg'", font_script)
        self.assertIn("/v 'MS Shell Dlg 2'", font_script)
        for drawing_font in (
            "/v Arial",
            "/v 'Times New Roman'",
            "/v SimSun",
            "/v 'Microsoft YaHei'",
        ):
            self.assertNotIn(drawing_font, font_script)

    def test_ui_font_validation_accepts_large_registry_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wine = root / "wine"
            wine.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$*\" == *'/s' ]]; then\n"
                "  echo NotoSansCJK-Regular.ttc\n"
                "  head -c 262144 /dev/zero | tr '\\0' x\n"
                "elif [ \"$1 $2\" = 'reg query' ]; then\n"
                "  echo 'Tahoma REG_MULTI_SZ NotoSansCJK-Regular.ttc,Noto Sans CJK SC'\n"
                "fi\n"
            )
            wine.chmod(0o755)
            result = subprocess.run(
                ["bash", str(RUNTIME_ROOT / "configure_ui_fonts.sh")],
                env={**os.environ, "PATH": f"{root}:{os.environ['PATH']}"},
                text=True, capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("已配置 Noto Sans CJK SC", result.stdout)

    def test_optional_vnc_monitoring_is_owned_by_the_runtime_entrypoint(self) -> None:
        dockerfile = (RUNTIME_ROOT / "Dockerfile").read_text(
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

    def test_core_serial_number_cli_and_msi_property(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("--serial-solidworks", script)
        self.assertIn("--license-server", script)
        self.assertIn("--install-dir", script)
        self.assertIn('SW_TARGET_INSTALL_DIR', script)
        self.assertIn('SW_SERIAL_SOLIDWORKS', script)
        self.assertIn('SW_LICENSE_SERVER', script)
        self.assertIn('append_default_msi_property "SOLIDWORKSSERIALNUMBER"', script)
        self.assertIn('append_default_msi_property "SERVERLIST"', script)
        self.assertNotIn("--serial-simulation", script)
        self.assertNotIn("--serial-motion", script)
        self.assertNotIn("--serial-mbd", script)
        self.assertNotIn('SIMULATIONSERIALNUMBER', script)
        self.assertNotIn('MOTIONSERIALNUMBER', script)
        self.assertNotIn('MBDSERIALNUMBER', script)
        # Ensure we do NOT touch registry manually for serials (MSI writes them natively)
        self.assertNotIn('wine reg add "HKLM\\SOFTWARE\\SolidWorks\\Licenses\\Serial Numbers"', script)


if __name__ == "__main__":
    unittest.main()
