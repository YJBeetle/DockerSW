"""Exercise candidate/publication policy using the workflow's actual Bash blocks."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESOLVE = "Resolve image names"
CHECK = "Check if images are already verified and built for this commit"
PUBLISH = "Publish verified CLI images & promote atomically"
SHA_TAG = "sha-1234567"
REPOSITORIES = {
    "runtime": "ghcr.io/yjbeetle/sw-runtime",
    "preinstalled": "ghcr.io/yjbeetle/sw-preinstalled",
    "executable": "ghcr.io/yjbeetle/sw-executable",
}


@unittest.skipUnless(shutil.which("bash"), "Bash is required for image policy tests")
class ImageCandidateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dockersw-image-candidate-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.runner = self.directory / "runner"
        self.runner.mkdir()
        self.fake_bin = self.directory / "bin"
        self.fake_bin.mkdir()
        self.trace = self.directory / "commands.jsonl"
        self.github_env = self.directory / "github-env"
        self.github_output = self.directory / "github-output"
        self.workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.languages = [
            line.split("\t")[0]
            for line in (ROOT / "preinstall/languages.tsv").read_text().splitlines()
            if line and not line.startswith("#")
        ]
        executable = f"#!{sys.executable}\n" + textwrap.dedent("""
            import json, os, sys
            from pathlib import Path

            role = Path(sys.argv[0]).name
            args = sys.argv[1:]
            with Path(os.environ['FAKE_TRACE']).open('a', encoding='utf-8') as stream:
                stream.write(json.dumps([role, *args]) + '\\n')
            if role == 'git' and args == ['rev-parse', '--short=7', 'HEAD']:
                print('1234567')
                sys.exit(0)
            if role != 'docker':
                sys.exit(98)
            if args[:2] == ['manifest', 'inspect']:
                missing = args[2] == os.environ.get('FAKE_MISSING_IMAGE')
                sys.exit(0 if os.environ['FAKE_IMAGES_EXIST'] == 'true' and not missing else 1)
            if args[:2] == ['buildx', 'build'] and '--push' in args:
                sys.exit(23 if os.environ.get('FAKE_BUILD_FAILURE') == 'true' else 0)
            if args[:3] == ['buildx', 'imagetools', 'create']:
                sys.exit(0)
            if args[:1] == ['push']:
                sys.exit(0)
            print('Unexpected Docker fixture command: ' + repr(args), file=sys.stderr)
            sys.exit(99)
        """)
        for name in ("git", "docker"):
            path = self.fake_bin / name
            path.write_text(executable, encoding="utf-8")
            path.chmod(0o755)
        self.base_environment = {
            **os.environ,
            "PATH": str(self.fake_bin) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_TRACE": str(self.trace),
            "FAKE_IMAGES_EXIST": "true",
            "GITHUB_ENV": str(self.github_env),
            "GITHUB_OUTPUT": str(self.github_output),
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF_NAME": "codex/a12-candidate",
            "GITHUB_REF_TYPE": "branch",
            "RUNNER_TEMP": str(self.runner),
            "SW_REQUEST_PROMOTION": "false",
            "SW_LANGUAGES": "zh-cn,ja",
            **{f"SW_{name.upper()}_REPO": value for name, value in REPOSITORIES.items()},
        }
        self.environment = dict(self.base_environment)

    def step(self, name):
        return self.workflow.split("      - name: " + name + "\n", 1)[1].split(
            "\n      - name:", 1
        )[0]

    def run_step(self, name, *, force_rebuild=False, **environment):
        body = textwrap.dedent(self.step(name).split("        run: |\n", 1)[1])
        body = body.replace(
            "${{ inputs.force_rebuild || 'false' }}",
            "true" if force_rebuild else "false",
        )
        self.assertNotIn("${{", body, "Fixture must explicitly resolve every workflow expression")
        return subprocess.run(
            ["bash", "-c", body],
            cwd=ROOT,
            env={**self.environment, **environment},
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    @staticmethod
    def values(path):
        if not path.exists():
            return {}
        return dict(line.split("=", 1) for line in path.read_text().splitlines())

    def resolve(self, **environment):
        for path in (self.trace, self.github_env, self.github_output):
            path.unlink(missing_ok=True)
        self.environment = {**self.base_environment, **environment}
        result = self.run_step(RESOLVE)
        if result.returncode == 0:
            self.environment.update(self.values(self.github_env))
            # Publication consumes only the tag column of the richer build plan.
            self.environment["SW_LANGUAGE_BUILD_PLAN"] = self.environment["SW_LANGUAGE_PLAN"]
        return result

    def calls(self):
        if not self.trace.exists():
            return []
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def docker_calls(self):
        return [call[1:] for call in self.calls() if call[0] == "docker"]

    def promotions(self):
        return [
            call for call in self.docker_calls()
            if call[:3] == ["buildx", "imagetools", "create"]
        ]

    def published_sha_targets(self):
        return [
            call[call.index("-t") + 1]
            for call in self.docker_calls()
            if call[:2] == ["buildx", "build"]
        ]

    def assert_success(self, result):
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def assert_promoted_aliases(self, branch, languages):
        expected = {}
        for repository in REPOSITORIES.values():
            for suffix in ("", "-cli"):
                tags = {f"{repository}:{branch}{suffix}"}
                if branch == "main":
                    tags.add(f"{repository}:latest{suffix}")
                expected[f"{repository}:{SHA_TAG}{suffix}"] = tags
        for language in languages:
            for repository in (REPOSITORIES["preinstalled"], REPOSITORIES["executable"]):
                for suffix in ("", "-cli"):
                    tags = {f"{repository}:{branch}-{language}{suffix}"}
                    if branch == "main":
                        tags.add(f"{repository}:latest-{language}{suffix}")
                    expected[f"{repository}:{SHA_TAG}-{language}{suffix}"] = tags
        actual = {}
        for call in self.promotions():
            self.assertIn("--prefer-index=false", call)
            source = call[-1]
            self.assertNotIn(source, actual, "Each source must be promoted only once")
            actual[source] = {call[index + 1] for index, arg in enumerate(call) if arg == "--tag"}
        self.assertEqual(expected, actual)

    def test_manual_default_is_non_promoting_even_on_release_refs(self):
        option = self.workflow.split("      promote_images:\n", 1)[1].split(
            "      force_rebuild:", 1
        )[0]
        self.assertIn("type: boolean", option)
        self.assertIn("default: false", option)
        self.assertIn("SW_REQUEST_PROMOTION: ${{ inputs.promote_images || 'false' }}", self.step(RESOLVE))
        for branch in ("main", "2025", "codex/a12-candidate"):
            with self.subTest(branch=branch):
                self.assert_success(self.resolve(GITHUB_REF_NAME=branch))
                self.assertEqual("false", self.environment["SW_PROMOTE_IMAGES"])
                self.assert_success(self.run_step(CHECK))
                self.assertEqual("false", self.values(self.github_output)["already_verified"])
                self.assert_success(self.run_step(PUBLISH))
                self.assertEqual([], self.promotions())

    def test_candidate_runs_cad_even_when_all_images_already_exist(self):
        for images_exist in ("true", "false"):
            with self.subTest(images_exist=images_exist):
                self.assert_success(self.resolve(FAKE_IMAGES_EXIST=images_exist))
                self.assert_success(self.run_step(CHECK))
                self.assertEqual("false", self.values(self.github_output)["already_verified"])
                self.assertEqual([], self.promotions())

    def test_candidate_retains_sha_outputs_for_every_localization(self):
        marker = self.directory / "unexpected-ref-execution"
        ref = "codex/$(touch " + str(marker) + ")"
        self.assert_success(self.resolve(GITHUB_REF_NAME=ref, SW_LANGUAGES="all"))
        self.assert_success(self.run_step("Push verified sw-runtime image"))
        self.assert_success(self.run_step("Push verified sw-runtime CLI image"))
        self.assert_success(self.run_step(PUBLISH))
        expected = {
            f"{repository}:{SHA_TAG}{suffix}-cli"
            for repository in (REPOSITORIES["preinstalled"], REPOSITORIES["executable"])
            for suffix in ("", *("-" + language for language in self.languages))
        }
        self.assertEqual(expected, set(self.published_sha_targets()))
        self.assertEqual(len(expected), len(self.published_sha_targets()))
        self.assertEqual(
            [["push", f"{REPOSITORIES['runtime']}:{SHA_TAG}"],
             ["push", f"{REPOSITORIES['runtime']}:{SHA_TAG}-cli"]],
            [call for call in self.docker_calls() if call[:1] == ["push"]],
        )
        self.assertEqual([], self.promotions())
        self.assertFalse(marker.exists(), "A ref name must remain data, never shell source")

    def test_release_push_fast_path_promotes_only_expected_aliases(self):
        for branch in ("2025", "main"):
            with self.subTest(branch=branch):
                self.assert_success(self.resolve(GITHUB_EVENT_NAME="push", GITHUB_REF_NAME=branch))
                self.assertEqual("true", self.environment["SW_PROMOTE_IMAGES"])
                self.assert_success(self.run_step(CHECK))
                self.assertEqual("true", self.values(self.github_output)["already_verified"])
                self.assert_promoted_aliases(branch, ["zh-cn", "ja"])
                self.assertEqual([], self.published_sha_targets())

    def test_release_push_full_path_promotes_all_localizations(self):
        for branch in ("2025", "main"):
            with self.subTest(branch=branch):
                self.assert_success(self.resolve(
                    GITHUB_EVENT_NAME="push", GITHUB_REF_NAME=branch, SW_LANGUAGES="all"
                ))
                self.assert_success(self.run_step(PUBLISH))
                self.assert_promoted_aliases(branch, self.languages)
                self.assertEqual(2 * (1 + len(self.languages)), len(self.published_sha_targets()))

    def test_manual_promotion_requires_explicit_opt_in(self):
        for branch in ("2025", "main"):
            with self.subTest(branch=branch):
                self.assert_success(self.resolve(GITHUB_REF_NAME=branch, SW_REQUEST_PROMOTION="true"))
                self.assertEqual("true", self.environment["SW_PROMOTE_IMAGES"])
                self.assert_success(self.run_step(CHECK))
                self.assertEqual("true", self.values(self.github_output)["already_verified"])
                self.assert_promoted_aliases(branch, ["zh-cn", "ja"])

    def test_invalid_publication_refs_fail_before_any_registry_calls(self):
        for branch, ref_type, event, requested in (
            ("codex/a12-candidate", "branch", "workflow_dispatch", "true"),
            ("codex/a12-candidate", "branch", "push", "false"),
            ("2025-candidate", "branch", "workflow_dispatch", "true"),
            ("20250", "branch", "workflow_dispatch", "true"),
            ("main", "tag", "workflow_dispatch", "true"),
            ("2025", "tag", "workflow_dispatch", "true"),
        ):
            with self.subTest(branch=branch, ref_type=ref_type, event=event):
                result = self.resolve(
                    GITHUB_REF_NAME=branch, GITHUB_REF_TYPE=ref_type,
                    GITHUB_EVENT_NAME=event, SW_REQUEST_PROMOTION=requested,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertEqual([], self.docker_calls())
                self.assertNotIn("SW_IMAGE_SHA_TAG", self.values(self.github_env))

    def test_force_rebuild_does_not_grant_candidate_promotion(self):
        self.assert_success(self.resolve(GITHUB_REF_NAME="2025"))
        self.assert_success(self.run_step(CHECK, force_rebuild=True))
        self.assertEqual("false", self.values(self.github_output)["already_verified"])
        self.assert_success(self.run_step(PUBLISH))
        self.assertEqual([], self.promotions())
        self.assertTrue(self.published_sha_targets())

    def test_force_rebuild_bypasses_release_fast_path(self):
        self.assert_success(self.resolve(GITHUB_EVENT_NAME="push", GITHUB_REF_NAME="2025"))
        self.assert_success(self.run_step(CHECK, force_rebuild=True))
        self.assertEqual("false", self.values(self.github_output)["already_verified"])
        self.assertEqual([], self.promotions())

    def test_missing_localized_cli_image_cannot_use_release_fast_path(self):
        self.assert_success(self.resolve(GITHUB_EVENT_NAME="push", GITHUB_REF_NAME="main"))
        missing = f"{REPOSITORIES['executable']}:{SHA_TAG}-ja-cli"
        self.assert_success(self.run_step(CHECK, FAKE_MISSING_IMAGE=missing))
        self.assertEqual("false", self.values(self.github_output)["already_verified"])
        self.assertEqual([], self.promotions())

    def test_failed_sha_publish_aborts_before_release_aliases(self):
        self.assert_success(self.resolve(GITHUB_EVENT_NAME="push", GITHUB_REF_NAME="main"))
        result = self.run_step(PUBLISH, FAKE_BUILD_FAILURE="true")
        self.assertEqual(23, result.returncode)
        self.assertEqual([], self.promotions())
        self.assertEqual(1, len(self.published_sha_targets()))


if __name__ == "__main__":
    unittest.main()
