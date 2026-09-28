import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PROJECT_ROOT / "runtime"
PATCH_ROOT = RUNTIME_ROOT / "wine-patches"


class WinePatchBuildTests(unittest.TestCase):
    def test_wine_source_and_patch_are_pinned(self) -> None:
        dockerfile = (RUNTIME_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("ARG WINE_VERSION=11.16", dockerfile)
        self.assertIn(
            "ARG WINE_SOURCE_SHA256="
            "c66e2090343dcd727f7f7fd2f87ee0bfb0b118790c1d745ab7b8a4c3a4197f2f",
            dockerfile,
        )
        self.assertIn("COPY runtime/wine-patches/*.patch /patches/", dockerfile)
        self.assertIn("        gcc-mingw-w64-x86-64 \\", dockerfile.splitlines())
        self.assertIn("patch --directory=/build/source --strip=1 --dry-run", dockerfile)
        self.assertTrue(
            (PATCH_ROOT / "0000-win32u-fix-24bit-memory-dc.patch").is_file()
        )

    def test_wine_unix_modules_are_built_and_installed_as_one_abi_set(self) -> None:
        dockerfile = (RUNTIME_ROOT / "Dockerfile").read_text(encoding="utf-8")

        build_outputs = {
            "ntdll.so": "dlls/ntdll/ntdll.so",
            "win32u.so": "dlls/win32u/win32u.so",
            "winex11.so": "dlls/winex11.drv/winex11.so",
            "opengl32.so": "dlls/opengl32/opengl32.so",
        }
        self.assertIn("make -j\"$(nproc)\" dlls/win32u/win32u.so", dockerfile)
        for module, build_output in build_outputs.items():
            self.assertIn(build_output, dockerfile)
            self.assertIn(
                f"/opt/wine-devel/lib/wine/x86_64-unix/{module}", dockerfile
            )

    def test_solidworks_capture_fix_is_explicitly_scoped(self) -> None:
        patch = (
            PATCH_ROOT / "0003-win32u-no-capture-resend.patch"
        ).read_text(encoding="utf-8")
        registry = (RUNTIME_ROOT / "registry" / "headless_tweaks.reg").read_text(
            encoding="utf-8"
        )

        self.assertIn("previous != hwnd || !compat_no_capture_resend", patch)
        self.assertIn("WINE_NOCAPTURERESEND", patch)
        self.assertIn('"sldworks.exe"="WINE_NOCAPTURERESEND"', registry)

    def test_solidworks_uses_glx_for_front_buffer_rendering(self) -> None:
        patch = (
            PATCH_ROOT / "0004-winex11-flush-front-buffer.patch"
        ).read_text(encoding="utf-8")
        registry = (RUNTIME_ROOT / "registry" / "headless_tweaks.reg").read_text(
            encoding="utf-8"
        )

        self.assertIn('has_extension( glxExtensions, "GLX_OML_swap_method" )', patch)
        self.assertIn("swap_method == GLX_SWAP_COPY_OML", patch)
        self.assertIn("for(run=0; run < 3; run++)", patch)
        self.assertIn("if (!(flags & GL_FLUSH_FINISHED)) funcs->p_glFinish();", patch)
        self.assertIn("XFlush( gdi_display );", patch)
        self.assertIn(
            "[HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\"
            "SLDWORKS.exe\\X11 Driver]",
            registry,
        )
        self.assertIn('"UseEGL"="N"', registry)

    def test_real_child_topmost_fix_preserves_desktop_combo_windows(self) -> None:
        patch = (
            PATCH_ROOT / "0005-win32u-ignore-child-topmost.patch"
        ).read_text(encoding="utf-8")

        self.assertIn("after == HWND_TOPMOST || after == HWND_NOTOPMOST", patch)
        self.assertIn("WS_CHILD | WS_POPUP", patch)
        self.assertIn("parent != get_desktop_window()", patch)
        self.assertIn("flags & SWP_NOZORDER", patch)

    def test_runtime_binary_rewriter_is_removed(self) -> None:
        self.assertFalse((RUNTIME_ROOT / "patch_win32u.pl").exists())
        for relative_path in (
            "runtime/Dockerfile",
            "runtime/init_wineprefix.sh",
            "runtime/entrypoint.sh",
            "runtime/bin/sw-install",
            ".github/workflows/build.yml",
        ):
            content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
            if relative_path == ".github/workflows/build.yml":
                self.assertIn("test ! -e /usr/local/lib/sw-runtime/patch_win32u.pl", content)
            else:
                self.assertNotIn("patch_win32u.pl", content)

    def test_wine_derived_patches_have_separate_license_notice(self) -> None:
        notice = (PATCH_ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GNU Lesser General Public License", notice)
        self.assertIn("Wine-derived patches", notice)


if __name__ == "__main__":
    unittest.main()
