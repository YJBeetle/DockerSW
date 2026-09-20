import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ImageLayeringTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def test_all_base_and_delivery_targets_are_named(self) -> None:
        runtime = self.read("runtime/Dockerfile")
        preinstall_base = self.read("preinstall/Dockerfile.base")
        preinstall = self.read("preinstall/Dockerfile")
        executable_base = self.read("smoke-test/Dockerfile.base")
        executable = self.read("smoke-test/Dockerfile")

        self.assertIn("FROM ubuntu:22.04 AS sw-runtime-base", runtime)
        self.assertIn("FROM sw-runtime-base AS sw-runtime", runtime)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-preinstalled-base", preinstall_base)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-preinstalled", preinstall)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-executable-base", executable_base)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-executable", executable)

    def test_swcli_is_only_added_to_delivery_targets(self) -> None:
        for relative_path, final_target in (
            ("runtime/Dockerfile", "FROM sw-runtime-base AS sw-runtime"),
            ("preinstall/Dockerfile", "FROM ${BASE_IMAGE} AS sw-preinstalled"),
            ("smoke-test/Dockerfile", "FROM ${BASE_IMAGE} AS sw-executable"),
        ):
            dockerfile = self.read(relative_path)
            base, delivery = dockerfile.split(final_target, maxsplit=1)
            self.assertNotIn("/opt/swcli/", base)
            self.assertIn("/opt/swcli/", delivery)
            self.assertIn("install_swcli.sh /opt/swcli", delivery)

    def test_delivery_images_do_not_copy_removed_swclid_wrapper(self) -> None:
        for relative_path in (
            "preinstall/Dockerfile",
            "preinstall/Dockerfile.base",
            "smoke-test/Dockerfile",
            "smoke-test/Dockerfile.base",
        ):
            self.assertNotIn("/usr/local/bin/swclid", self.read(relative_path))

        export_script = self.read("smoke-test/export.sh")
        self.assertIn("sw-cli daemon stop --json", export_script)
        self.assertNotIn("\nswclid ", export_script)

    def test_ci_builds_six_sha_images_in_three_packages(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        for repository in (
            "ghcr.io/yjbeetle/sw-runtime",
            "ghcr.io/yjbeetle/sw-preinstalled",
            "ghcr.io/yjbeetle/sw-executable",
        ):
            self.assertIn(repository, workflow)

        for removed_repository in (
            "ghcr.io/yjbeetle/sw-runtime-base",
            "ghcr.io/yjbeetle/sw-preinstalled-base",
            "ghcr.io/yjbeetle/sw-executable-base",
        ):
            self.assertNotIn(removed_repository, workflow)

        for target in ("sw-runtime-base", "sw-runtime"):
            self.assertIn(f"target: {target}", workflow)
        for target in (
            "sw-preinstalled-base",
            "sw-preinstalled",
            "sw-executable-base",
            "sw-executable",
        ):
            self.assertIn(f"--target {target}", workflow)

        for image in (
            "SW_RUNTIME_BASE_IMAGE",
            "SW_RUNTIME_IMAGE",
            "SW_PREINSTALLED_BASE_IMAGE",
            "SW_PREINSTALLED_IMAGE",
            "SW_EXECUTABLE_BASE_IMAGE",
            "SW_EXECUTABLE_IMAGE",
        ):
            self.assertIn(f'push "${{{image}}}"', workflow)

    def test_only_delivery_tags_are_mutable(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        for repository_variable in (
            "SW_RUNTIME_REPO",
            "SW_PREINSTALLED_REPO",
            "SW_EXECUTABLE_REPO",
        ):
            self.assertIn(f'${{{repository_variable}}}:latest', workflow)

        self.assertNotIn(":latest-base", workflow)
        self.assertNotIn(":main-base", workflow)
        self.assertIn(
            'SW_RUNTIME_BASE_IMAGE=${SW_RUNTIME_REPO}:sha-${commit_sha}-base',
            workflow,
        )
        self.assertIn(
            'SW_PREINSTALLED_BASE_IMAGE=${SW_PREINSTALLED_REPO}:sha-${commit_sha}-base',
            workflow,
        )
        self.assertIn(
            'SW_EXECUTABLE_BASE_IMAGE=${SW_EXECUTABLE_REPO}:sha-${commit_sha}-base',
            workflow,
        )
        self.assertIn(":buildcache-base", workflow)
        self.assertIn(":buildcache-delivery", workflow)

    def test_disk_cleanup_only_runs_below_the_required_capacity(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        self.assertIn("Inspect runner disk capacity", workflow)
        self.assertIn("Verify runner disk capacity", workflow)
        self.assertIn("required_kib=$((40 * 1024 * 1024))", workflow)
        self.assertIn("steps.runner-disk.outputs.cleanup_required == 'true'", workflow)
        self.assertIn("jlumbroso/free-disk-space", workflow)

    def test_cached_installation_base_does_not_scan_iso(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        dockerignore = self.read(".dockerignore")
        installer = self.read("preinstall/Dockerfile.base")

        self.assertIn("preinstall/media", dockerignore)
        for context_name, relative_path in (
            ("sw-data", "preinstall/media/swwi/data"),
            ("sw-toolbox", "preinstall/media/Toolbox"),
            ("sw-login", "preinstall/media/swloginmgr"),
            ("sw-vcredist", "preinstall/media/PreReqs/VCRedist17"),
            ("sw-dotnet", "preinstall/media/PreReqs/dotNetFx"),
        ):
            self.assertIn(f"from={context_name}", installer)
            self.assertIn(
                f'--build-context "{context_name}={relative_path}"', workflow
            )
        self.assertNotIn("sw-media=preinstall/media", workflow)
        self.assertIn("SW_PREINSTALLED_REUSABLE_IMAGE", workflow)
        self.assertIn("steps.check-installed-base.outputs.exists != 'true'", workflow)
        self.assertIn("-f preinstall/Dockerfile.base", workflow)
        self.assertIn("-f preinstall/Dockerfile", workflow)

    def test_executable_delivery_does_not_read_private_assets(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        dockerignore = self.read(".dockerignore")
        executable_base = self.read("smoke-test/Dockerfile.base")
        executable = self.read("smoke-test/Dockerfile")

        self.assertIn("smoke-test/assets", dockerignore)
        self.assertIn("from=smoke-assets", executable_base)
        self.assertNotIn("smoke-assets", executable)
        self.assertIn('--build-context "smoke-assets=smoke-test/assets"', workflow)
        self.assertIn("-f smoke-test/Dockerfile.base", workflow)
        self.assertIn("-f smoke-test/Dockerfile", workflow)


if __name__ == "__main__":
    unittest.main()
