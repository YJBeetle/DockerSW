"""Static build-context contracts, not a Docker engine inclusion proof."""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SWCLI_ROOT = "swcli/SWCLI"


class SwcliPayloadContextTests(unittest.TestCase):
    def setUp(self) -> None:
        ignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.patterns = {
            line.strip().rstrip("/")
            for line in ignore.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

    def test_local_swcli_outputs_and_environments_are_explicitly_excluded(self) -> None:
        for directory in ("dist", "build", ".venv", ".pytest_cache"):
            with self.subTest(directory=directory):
                pattern = f"{SWCLI_ROOT}/{directory}"
                self.assertIn(pattern, self.patterns)
                self.assertNotIn("!" + pattern, self.patterns)

    def test_package_metadata_is_excluded_at_every_swcli_source_depth(self) -> None:
        self.assertIn(f"{SWCLI_ROOT}/**/*.egg-info", self.patterns)
        self.assertNotIn(f"!{SWCLI_ROOT}/**/*.egg-info", self.patterns)

    def test_source_scripts_docs_and_skills_are_not_blanket_excluded(self) -> None:
        for directory in (
            "swcli",
            SWCLI_ROOT,
            f"{SWCLI_ROOT}/src",
            f"{SWCLI_ROOT}/scripts",
            f"{SWCLI_ROOT}/docs",
            f"{SWCLI_ROOT}/skills",
            f"{SWCLI_ROOT}/src/swcli/skills",
        ):
            for suffix in ("", "/*", "/**"):
                with self.subTest(directory=directory, suffix=suffix):
                    self.assertNotIn(directory + suffix, self.patterns)

    def test_whole_checkout_payload_copy_uses_this_context_contract(self) -> None:
        dockerfile = (PROJECT_ROOT / "swcli/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY --link swcli/SWCLI/ /opt/swcli/", dockerfile)


if __name__ == "__main__":
    unittest.main()
