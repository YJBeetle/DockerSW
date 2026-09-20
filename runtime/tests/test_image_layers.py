import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ImageLayeringTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def test_all_base_and_delivery_targets_are_named(self) -> None:
        runtime = self.read("runtime/Dockerfile")
        preinstall = self.read("preinstall/Dockerfile")
        executable = self.read("smoke-test/Dockerfile")

        self.assertIn("FROM ubuntu:22.04 AS sw-runtime-base", runtime)
        self.assertIn("FROM sw-runtime-base AS sw-runtime", runtime)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-preinstalled-base", preinstall)
        self.assertIn("FROM sw-preinstalled-base AS sw-preinstalled", preinstall)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-executable-base", executable)
        self.assertIn("FROM sw-executable-base AS sw-executable", executable)

    def test_swcli_is_only_added_to_delivery_targets(self) -> None:
        for relative_path, final_target in (
            ("runtime/Dockerfile", "FROM sw-runtime-base AS sw-runtime"),
            ("preinstall/Dockerfile", "FROM sw-preinstalled-base AS sw-preinstalled"),
            ("smoke-test/Dockerfile", "FROM sw-executable-base AS sw-executable"),
        ):
            dockerfile = self.read(relative_path)
            base, delivery = dockerfile.split(final_target, maxsplit=1)
            self.assertNotIn("/opt/swcli/", base)
            self.assertIn("/opt/swcli/", delivery)
            self.assertIn("install_swcli.sh /opt/swcli", delivery)

    def test_ci_builds_and_publishes_all_six_sha_images(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        for repository in (
            "ghcr.io/yjbeetle/sw-runtime-base",
            "ghcr.io/yjbeetle/sw-runtime",
            "ghcr.io/yjbeetle/sw-preinstalled-base",
            "ghcr.io/yjbeetle/sw-preinstalled",
            "ghcr.io/yjbeetle/sw-executable-base",
            "ghcr.io/yjbeetle/sw-executable",
        ):
            self.assertIn(repository, workflow)

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

    def test_only_delivery_repositories_receive_latest_tags(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        for repository_variable in (
            "SW_RUNTIME_REPO",
            "SW_PREINSTALLED_REPO",
            "SW_EXECUTABLE_REPO",
        ):
            self.assertIn(f'${{{repository_variable}}}:latest', workflow)

        for base_repository_variable in (
            "SW_RUNTIME_BASE_REPO",
            "SW_PREINSTALLED_BASE_REPO",
            "SW_EXECUTABLE_BASE_REPO",
        ):
            self.assertNotIn(f'${{{base_repository_variable}}}:latest', workflow)


if __name__ == "__main__":
    unittest.main()
