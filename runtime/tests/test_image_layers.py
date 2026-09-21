import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ImageLayeringTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def test_image_and_cli_delivery_targets_are_named_consistently(self) -> None:
        runtime = self.read("runtime/Dockerfile")
        payload = self.read("swcli/Dockerfile")
        delivery = self.read("swcli/Dockerfile.delivery")
        preinstalled = self.read("preinstall/Dockerfile")
        localized = self.read("preinstall/Dockerfile.language")
        executable = self.read("smoke-test/Dockerfile")

        self.assertIn("FROM ubuntu:22.04 AS sw-runtime", runtime)
        self.assertIn("FROM scratch AS swcli-payload", payload)
        self.assertIn("ARG IMAGE=sw-runtime:local", delivery)
        self.assertIn("ARG PAYLOAD_IMAGE=swcli-payload:local", delivery)
        self.assertIn("FROM ${PAYLOAD_IMAGE} AS swcli-payload", delivery)
        self.assertIn("FROM ${IMAGE} AS swcli-delivery", delivery)
        self.assertIn("FROM ${RUNTIME_IMAGE} AS sw-preinstalled", preinstalled)
        self.assertIn(
            "FROM ${PREINSTALLED_IMAGE} AS sw-preinstalled-language", localized
        )
        self.assertIn("FROM ${PREINSTALLED_IMAGE} AS sw-executable", executable)

    def test_swcli_payload_is_built_once_and_linked_into_all_cli_images(self) -> None:
        for relative_path in (
            "runtime/Dockerfile",
            "preinstall/Dockerfile",
            "preinstall/Dockerfile.language",
            "smoke-test/Dockerfile",
        ):
            self.assertNotIn("/opt/swcli/", self.read(relative_path))

        payload = self.read("swcli/Dockerfile")
        self.assertIn("COPY --link swcli/SWCLI/ /opt/swcli/", payload)
        self.assertIn("swcli/bin/sw-cli", payload)
        self.assertIn("swcli/bin/linux-to-wine-path", payload)
        self.assertIn("swcli/entrypoint-cli.sh", payload)
        self.assertNotIn("runtime/entrypoint.sh", payload)
        self.assertNotIn("install_swcli.sh", payload)

        delivery = self.read("swcli/Dockerfile.delivery")
        self.assertIn("COPY --link --from=swcli-payload / /", delivery)
        self.assertIn(
            'ENTRYPOINT ["/usr/local/bin/entrypoint.sh", '
            '"/usr/local/bin/entrypoint-cli.sh"]',
            delivery,
        )
        for removed_path in (
            "runtime/Dockerfile.base",
            "preinstall/Dockerfile.base",
            "smoke-test/Dockerfile.base",
        ):
            self.assertFalse((PROJECT_ROOT / removed_path).exists())

    def test_sw_install_stays_in_runtime_image(self) -> None:
        runtime = self.read("runtime/Dockerfile")
        payload = self.read("swcli/Dockerfile")
        delivery = self.read("swcli/Dockerfile.delivery")

        self.assertIn(
            "COPY --chmod=755 runtime/bin/sw-install /usr/local/bin/sw-install",
            runtime,
        )
        self.assertIn(
            "COPY --chmod=755 runtime/entrypoint.sh /usr/local/bin/entrypoint.sh",
            runtime,
        )
        self.assertNotIn("runtime/bin/sw-install", payload)
        self.assertNotIn("runtime/bin/sw-cli", payload)
        self.assertNotIn("runtime/bin/linux-to-wine-path", payload)
        self.assertNotIn("sw-install", delivery)

        workflow = self.read(".github/workflows/build.yml")
        self.assertIn("file: runtime/Dockerfile", workflow)
        self.assertIn("file: swcli/Dockerfile", workflow)
        self.assertIn("file: swcli/Dockerfile.delivery", workflow)
        self.assertIn("IMAGE=${{ env.SW_RUNTIME_IMAGE }}", workflow)
        self.assertIn("PAYLOAD_IMAGE=${{ env.SW_RUNTIME_PAYLOAD_IMAGE }}", workflow)

    def test_delivery_images_do_not_copy_removed_swclid_wrapper(self) -> None:
        for relative_path in (
            "swcli/Dockerfile",
            "swcli/Dockerfile.delivery",
            "preinstall/Dockerfile",
            "smoke-test/Dockerfile",
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

    def test_ci_builds_default_and_cli_images_from_one_payload(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        for repository in (
            "ghcr.io/yjbeetle/sw-runtime",
            "ghcr.io/yjbeetle/sw-preinstalled",
            "ghcr.io/yjbeetle/sw-executable",
        ):
            self.assertIn(repository, workflow)

        for target in ("sw-runtime", "swcli-payload", "swcli-delivery"):
            self.assertIn(f"target: {target}", workflow)
        for target in (
            "sw-preinstalled",
            "sw-preinstalled-language",
            "sw-executable",
            "swcli-delivery",
        ):
            self.assertIn(f"--target {target}", workflow)

        for image in (
            "SW_RUNTIME_IMAGE",
            "SW_RUNTIME_PAYLOAD_IMAGE",
            "SW_RUNTIME_CLI_IMAGE",
            "SW_PREINSTALLED_IMAGE",
            "SW_PREINSTALLED_CLI_IMAGE",
            "SW_EXECUTABLE_IMAGE",
            "SW_EXECUTABLE_CLI_IMAGE",
        ):
            self.assertIn(f'${{{image}}}', workflow)

    def test_default_and_cli_tag_contract_is_complete(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        for repository_variable in (
            "SW_RUNTIME_REPO",
            "SW_PREINSTALLED_REPO",
            "SW_EXECUTABLE_REPO",
        ):
            self.assertIn(f'${{{repository_variable}}}:latest', workflow)
            self.assertIn(f'${{{repository_variable}}}:latest-cli', workflow)
            self.assertIn(f'${{{repository_variable}}}:${{target_tag}}', workflow)
            self.assertIn(f'${{{repository_variable}}}:${{target_tag}}-cli', workflow)

        for assignment in (
            'SW_RUNTIME_IMAGE=${SW_RUNTIME_REPO}:sha-${commit_sha}',
            'SW_RUNTIME_CLI_IMAGE=${SW_RUNTIME_REPO}:sha-${commit_sha}-cli',
            'SW_PREINSTALLED_IMAGE=${SW_PREINSTALLED_REPO}:sha-${commit_sha}',
            'SW_PREINSTALLED_CLI_IMAGE=${SW_PREINSTALLED_REPO}:sha-${commit_sha}-cli',
            'SW_EXECUTABLE_IMAGE=${SW_EXECUTABLE_REPO}:sha-${commit_sha}',
            'SW_EXECUTABLE_CLI_IMAGE=${SW_EXECUTABLE_REPO}:sha-${commit_sha}-cli',
        ):
            self.assertIn(assignment, workflow)
        self.assertNotIn("-base", workflow)
        self.assertNotIn("BASE_IMAGE", workflow)

    def test_cli_publish_reuses_buildkit_layers_and_combines_promotions(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        publish_step = workflow.split(
            "- name: Publish verified CLI images & promote atomically", maxsplit=1
        )[1].split("- name: Show storage usage", maxsplit=1)[0]

        self.assertIn("publish_cli_image()", publish_step)
        self.assertIn("docker buildx build --push", publish_step)
        self.assertIn('--build-arg "IMAGE=${source_image}"', publish_step)
        self.assertIn('--build-arg "PAYLOAD_IMAGE=${SW_RUNTIME_PAYLOAD_IMAGE}"', publish_step)
        self.assertNotIn('docker push "${SW_PREINSTALLED_CLI_IMAGE}"', workflow)
        self.assertNotIn('docker push "${SW_EXECUTABLE_CLI_IMAGE}"', workflow)
        self.assertEqual(workflow.count("promote_image()"), 2)
        self.assertEqual(workflow.count('tags+=(--tag "${latest_tag}")'), 2)

    def test_disk_cleanup_only_runs_below_the_required_capacity(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        self.assertIn("Inspect runner disk capacity", workflow)
        self.assertIn("Verify runner disk capacity", workflow)
        self.assertIn("required_kib=$((50 * 1024 * 1024))", workflow)
        self.assertIn("steps.runner-disk.outputs.cleanup_required == 'true'", workflow)
        self.assertIn("jlumbroso/free-disk-space", workflow)

    def test_runtime_and_solidworks_builds_share_one_runner(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        self.assertNotIn("\n  build-runtime:\n", workflow)
        image_job = workflow.split("\n  build-and-smoke-test:\n", maxsplit=1)[1]
        self.assertIn("needs: unit-tests", image_job)
        self.assertEqual(image_job.count("uses: docker/setup-buildx-action@"), 1)
        self.assertEqual(image_job.count("uses: docker/login-action@"), 1)
        self.assertLess(
            image_job.index("Build and load sw-runtime image"),
            image_job.index("Build vanilla preinstalled image"),
        )

    def test_cached_installation_does_not_scan_iso(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        dockerignore = self.read(".dockerignore")
        installer = self.read("preinstall/Dockerfile")

        self.assertIn("preinstall/media", dockerignore)
        for context_name, relative_path in (
            ("sw-data", "preinstall/media/swwi/data"),
            ("sw-toolbox", "preinstall/media/Toolbox"),
            ("sw-login", "preinstall/media/swloginmgr"),
            ("sw-vcredist", "preinstall/media/PreReqs/VCRedist17"),
            ("sw-dotnet", "preinstall/media/PreReqs/dotNetFx"),
        ):
            self.assertIn(f"from={context_name}", installer)
            self.assertIn(f'--build-context "{context_name}={relative_path}"', workflow)
        self.assertNotIn("sw-media=preinstall/media", workflow)
        self.assertIn("SW_PREINSTALLED_REUSABLE_IMAGE", workflow)
        self.assertIn("steps.check-installed.outputs.exists != 'true'", workflow)
        self.assertIn("-f preinstall/Dockerfile", workflow)

    def test_preinstall_accepts_only_the_core_solidworks_serial(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        dockerfile = self.read("preinstall/Dockerfile")

        self.assertIn("SW_SERIAL_SOLIDWORKS", workflow)
        self.assertIn("SW_SERIAL_SOLIDWORKS", dockerfile)
        for product in ("SIMULATION", "MOTION", "MBD"):
            self.assertNotIn(f"SW_SERIAL_{product}", workflow)
            self.assertNotIn(f"SW_SERIAL_{product}", dockerfile)

    def test_executable_cli_delivery_does_not_read_private_assets(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        dockerignore = self.read(".dockerignore")
        executable = self.read("smoke-test/Dockerfile")
        delivery = self.read("swcli/Dockerfile.delivery")

        self.assertIn("smoke-test/assets", dockerignore)
        self.assertIn("from=smoke-assets", executable)
        self.assertNotIn("smoke-assets", delivery)
        self.assertIn('--build-context "smoke-assets=smoke-test/assets"', workflow)
        self.assertIn("-f smoke-test/Dockerfile", workflow)
        self.assertIn("-f swcli/Dockerfile.delivery", workflow)

    def test_localized_default_and_cli_images_are_built(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        language_dockerfile = self.read("preinstall/Dockerfile.language")

        self.assertIn(
            "FROM ${PREINSTALLED_IMAGE} AS sw-preinstalled-language",
            language_dockerfile,
        )
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
        self.assertIn("${SW_IMAGE_SHA_TAG}-${language_tag}", workflow)
        self.assertIn("${SW_IMAGE_SHA_TAG}-${language_tag}-cli", workflow)
        self.assertIn(":latest-${language_tag}", workflow)
        self.assertIn(":latest-${language_tag}-cli", workflow)

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

    def test_reusable_images_stay_in_the_registry(self) -> None:
        workflow = self.read(".github/workflows/build.yml")
        self.assertIn(
            'docker buildx imagetools inspect "${SW_RUNTIME_IMAGE}"', workflow
        )
        self.assertNotIn('docker pull "${SW_RUNTIME_IMAGE}"', workflow)
        self.assertNotIn('docker pull "${SW_PREINSTALLED_REUSABLE_IMAGE}"', workflow)
        self.assertNotIn('docker pull "${language_reusable_image}"', workflow)
        self.assertIn('--tag "${SW_PREINSTALLED_IMAGE}"', workflow)
        self.assertIn('"${SW_PREINSTALLED_REUSABLE_IMAGE}"', workflow)
        self.assertIn('--tag "${preinstalled_language_image}"', workflow)
        self.assertIn('"${language_reusable_image}"', workflow)
        self.assertIn("docker buildx build --push", workflow)


if __name__ == "__main__":
    unittest.main()
