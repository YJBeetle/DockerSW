"""Build wiring guards; the PE probe and CAD gate supply native evidence."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "runtime/wine-patches/0014-msxml-schema-cache-namespace.patch"


class MSXMLSchemaPatchTests(unittest.TestCase):
    def test_same_number_and_scoped_schema_adoption(self):
        source = PATCH.read_text()
        for fragment in (
            "dlls/msxml3/schema.c",
            'xmlHasNsProp(root, BAD_CAST "targetNamespace", NULL)',
            "xmlGetNoNsProp", "xmlSearchNs", "adopt_schema_qnames",
            "xmlFreeDoc(new_doc)", "annotation", "memberTypes",
        ):
            self.assertIn(fragment, source)

    def test_matching_module_is_built_and_installed_before_wineboot(self):
        source = (ROOT / "runtime/Dockerfile").read_text()
        for fragment in (
            "dlls/msxml3/x86_64-windows/msxml3.dll",
            "/build/output/msxml3.dll",
            "/opt/wine-devel/lib/wine/x86_64-windows/msxml3.dll",
        ):
            self.assertIn(fragment, source)
        self.assertLess(source.index("/opt/sw-runtime/wine-unix/msxml3.dll"),
                        source.index("bash /mnt/runtime/init_wineprefix.sh"))

    def test_build_checks_native_exit_marker_and_all_cases(self):
        source = (ROOT / "runtime/Dockerfile").read_text()
        for fragment in (
            "source=/build/probes,target=/mnt/wine-probes",
            "timeout --foreground 120 wine /mnt/wine-probes/msxml-schema.exe",
            "cat /tmp/msxml-schema-probe.log >&2",
            "grep -qx 'XML_NAMESPACE_PROBE_PASS'",
            "grep -c '^case='", '" -eq 7',
        ):
            self.assertIn(fragment, source)
        # The diagnostic executable is bind-mounted, not shipped in the image.
        self.assertNotIn("COPY --from=wine-unix-builder /build/probes", source)

    def test_probe_keeps_negative_and_dom_preservation_checks(self):
        source = (ROOT / "runtime/tests/native/msxml_schema_namespace_probe.c").read_text()
        for fragment in (
            "XML_NAMESPACE_PROBE_PASS", "reject-invalid", "local-empty-namespace",
            "adopt-valid", "explicit-target", "FAIL caller DOM changed",
            "return failures ? 1 : 0;",
        ):
            self.assertIn(fragment, source)
        self.assertEqual(source.count('    test("'), 7)


if __name__ == "__main__":
    unittest.main()
