import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ImageLayeringTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def test_all_base_and_delivery_targets_are_named(self) -> None:
        runtime_base = self.read("runtime/Dockerfile.base")
        runtime = self.read("runtime/Dockerfile")
        preinstall_base = self.read("preinstall/Dockerfile.base")
        preinstall = self.read("preinstall/Dockerfile")
        executable_base = self.read("smoke-test/Dockerfile.base")
        executable = self.read("smoke-test/Dockerfile")

        self.assertIn("FROM ubuntu:22.04 AS sw-runtime-base", runtime_base)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-runtime", runtime)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-preinstalled-base", preinstall_base)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-preinstalled", preinstall)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-executable-base", executable_base)
        self.assertIn("FROM ${BASE_IMAGE} AS sw-executable", executable)

    def test_swcli_payload_is_only_linked_into_delivery_targets(self) -> None:
        self.assertNotIn("/opt/swcli/", self.read("runtime/Dockerfile.base"))

        for relative_path in (
            "runtime/Dockerfile",
            "preinstall/Dockerfile",
            "smoke-test/Dockerfile",
        ):
            dockerfile = self.read(relative_path)
            self.assertIn("/opt/swcli/", dockerfile)
            self.assertNotIn("install_swcli.sh", dockerfile)

        for relative_path in ("preinstall/Dockerfile", "smoke-test/Dockerfile"):
            dockerfile = self.read(relative_path)
            self.assertIn(
                "COPY --link --from=current-app /opt/swcli/ /opt/swcli/",
                dockerfile,
            )
            self.assertIn(
                "COPY --link --from=current-app \\\n"
                "    /usr/local/bin/sw-cli \\\n"
                "    /usr/local/bin/linux-to-wine-path \\\n"
                "    /usr/local/bin/",
                dockerfile,
            )

    def test_sw_install_stays_in_runtime_base(self) -> None:
        base = self.read("runtime/Dockerfile.base")
        delivery = self.read("runtime/Dockerfile")

        self.assertIn(
            "COPY --chmod=755 runtime/bin/sw-install /usr/local/bin/sw-install",
            base,
        )
        self.assertNotIn("runtime/bin/ /usr/local/bin/", delivery)
        self.assertNotIn("runtime/bin/sw-install", delivery)
        self.assertIn("runtime/bin/sw-cli", delivery)
        self.assertIn("runtime/bin/linux-to-wine-path", delivery)

        for relative_path in ("preinstall/Dockerfile", "smoke-test/Dockerfile"):
            self.assertNotIn(
                "COPY --link --from=current-app /usr/local/bin/sw-install",
                self.read(relative_path),
            )

        workflow = self.read(".github/workflows/build.yml")
        self.assertIn("file: runtime/Dockerfile.base", workflow)
        self.assertIn("BASE_IMAGE=${{ env.SW_RUNTIME_BASE_IMAGE }}", workflow)

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

    def test_real_export_smoke_test_covers_protocol_and_concurrency_gates(self) -> None:
        export_script = self.read("smoke-test/export.sh")
        verification_script = self.read("smoke-test/verify-swcli.sh")

        self.assertIn("verify-swcli.sh", export_script)
        self.assertIn("sw-cli capabilities --json", verification_script)
        self.assertIn(".document.update_stamp != null", verification_script)
        self.assertIn("document lease acquire", verification_script)
        self.assertIn('"DocumentLeaseConflict"', verification_script)
        self.assertIn("document lease release", verification_script)
        self.assertIn("document list --json", verification_script)
        self.assertIn("swcli-smoke-multi-document.STEP", verification_script)

        workflow = self.read(".github/workflows/build.yml")
        self.assertIn("smoke-test/verify-swcli.sh", workflow)
        expected_outputs = workflow.split("expected_outputs=(", maxsplit=1)[1].split(
            ")", maxsplit=1
        )[0]
        self.assertEqual(expected_outputs.count('"'), 12)
        self.assertNotIn("swcli-smoke-", expected_outputs)

    def test_ci_builds_six_sha_images_in_three_packages(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        for repository in (
            "ghcr.io/yjbeetle/sw-runtime",
            "ghcr.io/yjbeetle/sw-preinstalled",
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
            self.assertIn(f'${{{image}}}', workflow)

        for image in (
            "SW_RUNTIME_BASE_IMAGE",
            "SW_RUNTIME_IMAGE",
            "SW_PREINSTALLED_IMAGE",
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

    def test_localized_images_are_layered_on_the_installed_base(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        language_dockerfile = self.read("preinstall/Dockerfile.language")

        self.assertIn("FROM ${BASE_IMAGE} AS sw-language-base", language_dockerfile)
        self.assertIn("from=sw-language", language_dockerfile)
        self.assertIn("wine msiexec /i", language_dockerfile)
        self.assertIn("/qb", language_dockerfile)
        self.assertIn("localedef -i", language_dockerfile)
        self.assertIn("LANG=${SW_POSIX_LOCALE}.UTF-8", language_dockerfile)
        self.assertNotIn("ADDLOCAL", language_dockerfile)
        self.assertIn(
            '--build-context "sw-language=preinstall/media/swwi/lang/${media_directory}"',
            workflow,
        )
        self.assertIn("${SW_IMAGE_SHA_TAG}-${language_tag}-base", workflow)
        self.assertIn("${SW_IMAGE_SHA_TAG}-${language_tag}", workflow)
        self.assertIn(":latest-${language_tag}", workflow)

    def test_supported_language_tags_are_unique(self) -> None:
        rows = []
        for line in self.read("preinstall/languages.tsv").splitlines():
            if line and not line.startswith("#"):
                rows.append(line.split("\t"))

        self.assertEqual(13, len(rows))
        self.assertTrue(all(len(row) == 6 for row in rows))
        for column in range(6):
            values = [row[column] for row in rows]
            self.assertEqual(len(values), len(set(values)))
        self.assertIn(
            [
                "zh-cn",
                "chinese-simplified",
                "chinese-simplified.msi",
                "2052",
                "zh_CN",
                "chinese-simplified",
            ],
            rows,
        )

    def test_cached_base_images_stay_in_the_registry(self) -> None:
        workflow = self.read(".github/workflows/build.yml")

        self.assertIn(
            'docker buildx imagetools inspect "${SW_RUNTIME_BASE_IMAGE}"', workflow
        )
        self.assertNotIn('docker pull "${SW_RUNTIME_BASE_IMAGE}"', workflow)
        self.assertNotIn('docker pull "${SW_PREINSTALLED_REUSABLE_IMAGE}"', workflow)
        self.assertNotIn('docker pull "${language_reusable_image}"', workflow)
        self.assertIn('--tag "${SW_PREINSTALLED_BASE_IMAGE}"', workflow)
        self.assertIn('"${SW_PREINSTALLED_REUSABLE_IMAGE}"', workflow)
        self.assertIn('--tag "${preinstalled_language_base}"', workflow)
        self.assertIn('"${language_reusable_image}"', workflow)
        self.assertIn("docker buildx build --push", workflow)


if __name__ == "__main__":
    unittest.main()
