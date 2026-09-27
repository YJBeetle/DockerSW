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
        self.assertIn("patch --directory=/build/source --strip=1 --dry-run", dockerfile)
        self.assertTrue(
            (PATCH_ROOT / "0001-win32u-fix-24bit-memory-dc.patch").is_file()
        )

    def test_ntdll_and_win32u_are_built_and_installed_as_a_pair(self) -> None:
        dockerfile = (RUNTIME_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("make -j\"$(nproc)\" dlls/win32u/win32u.so", dockerfile)
        for module in ("ntdll.so", "win32u.so"):
            self.assertIn(f"dlls/{module.removesuffix('.so')}/{module}", dockerfile)
            self.assertIn(
                f"/opt/wine-devel/lib/wine/x86_64-unix/{module}", dockerfile
            )

    def test_solidworks_capture_fix_is_explicitly_scoped(self) -> None:
        patch = (
            PATCH_ROOT / "0002-win32u-no-capture-resend.patch"
        ).read_text(encoding="utf-8")
        registry = (RUNTIME_ROOT / "registry" / "headless_tweaks.reg").read_text(
            encoding="utf-8"
        )

        self.assertIn("previous != hwnd || !compat_no_capture_resend", patch)
        self.assertIn("WINE_NOCAPTURERESEND", patch)
        self.assertIn('"sldworks.exe"="WINE_NOCAPTURERESEND"', registry)

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
