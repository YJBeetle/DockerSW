import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent


class SharedMonoTests(unittest.TestCase):
    def test_shared_release_and_all_assets_are_hash_pinned(self):
        config = (ROOT / 'managed_com.env').read_text()
        fetch = (ROOT / 'fetch_managed_com.sh').read_text()
        prepare = (ROOT / 'prepare_managed_com.sh').read_text()
        self.assertIn('wine-mono-11.3.0-X86StdcallFix-ComRegistration-CCWFix', config)
        for key, filename in (
            ('MONO_PATCH_SHA256', 'libmono-2.0-x86.dll'),
            ('MONO_X64_SHA256', 'libmono-2.0-x86_64.dll'),
            ('MONO_MSCORLIB_SHA256', 'mscorlib.dll'),
            ('MONO_REGASM_X86_SHA256', 'regasm-x86.exe'),
            ('MONO_REGASM_X64_SHA256', 'regasm-x86_64.exe'),
        ):
            self.assertRegex(config, key + r'="[0-9a-f]{64}"')
            self.assertIn(filename, fetch)
            self.assertIn('${' + key + '}', fetch)
            self.assertIn(filename, prepare)
            self.assertIn('${' + key + '}', prepare)
        self.assertIn('SOURCE.txt', fetch)
        self.assertIn('${MONO_SOURCE_SHA256}', fetch)

    def test_local_binary_patch_is_removed_and_native_gate_is_build_only(self):
        self.assertFalse((ROOT / 'patch_wine_mono.pl').exists())
        for file in ('Dockerfile', 'init_wineprefix.sh', 'entrypoint.sh', 'bin/sw-install'):
            self.assertNotIn('patch_wine_mono', (ROOT / file).read_text())
        workflow = (PROJECT / '.github/workflows/build.yml').read_text()
        self.assertNotIn('perl -c runtime/patch_wine_mono', workflow)
        self.assertIn('bash -n runtime/verify_mono_ccw.sh', workflow)
        dockerfile = (ROOT / 'Dockerfile').read_text()
        self.assertIn('source=runtime/verify_mono_ccw.sh', dockerfile)
        self.assertIn('source=runtime/tests/native/mono_ccw_release_probe.cs', dockerfile)
        self.assertIn('bash /mnt/mono-gates/verify.sh', dockerfile)
        self.assertNotIn('COPY runtime/tests/native/mono_ccw', dockerfile)
        self.assertNotIn('verify_mono_ccw', (ROOT / 'entrypoint.sh').read_text())

    def test_prepare_installs_both_engines_idempotently_and_rejects_bad_x64(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'assets'
            assets.mkdir()
            prefix = root / 'prefix'
            mono = prefix / 'drive_c/windows/mono/mono-2.0'
            mono.mkdir(parents=True)
            lines = ['WINE_VERSION=11.16', 'WINE_MONO_VERSION=11.3.0']
            files = (
                ('libmono-2.0-x86.dll', 'MONO_PATCH_SHA256'),
                ('libmono-2.0-x86_64.dll', 'MONO_X64_SHA256'),
                ('mscorlib.dll', 'MONO_MSCORLIB_SHA256'),
                ('regasm-x86.exe', 'MONO_REGASM_X86_SHA256'),
                ('regasm-x86_64.exe', 'MONO_REGASM_X64_SHA256'),
                ('stdole.dll', 'STDOLE_DLL_SHA256'),
            )
            for name, key in files:
                data = ('fixture:' + name).encode()
                (assets / name).write_bytes(data)
                lines.append(key + '=' + hashlib.sha256(data).hexdigest())
            config = root / 'config.env'
            config.write_text('\n'.join(lines))
            env = dict(os.environ, WINEPREFIX=str(prefix), DOCKERSW_MANAGED_COM_DIR=str(assets),
                       DOCKERSW_MANAGED_COM_CONFIG=str(config))
            def run():
                return subprocess.run(['bash', str(ROOT / 'prepare_managed_com.sh')], env=env,
                                      capture_output=True, text=True, timeout=30)
            for _ in range(2):
                result = run()
                self.assertEqual(result.returncode, 0, result.stderr)
                for architecture in ('x86', 'x86_64'):
                    name = 'libmono-2.0-' + architecture + '.dll'
                    self.assertEqual((mono / 'bin' / name).read_bytes(), (assets / name).read_bytes())
            previous = (mono / 'bin/libmono-2.0-x86_64.dll').read_bytes()
            (assets / 'libmono-2.0-x86_64.dll').write_bytes(b'corrupt')
            result = run()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('SHA256 mismatch', result.stderr)
            self.assertEqual((mono / 'bin/libmono-2.0-x86_64.dll').read_bytes(), previous)

    def test_native_gate_requires_success_marker_and_rejects_assertions(self):
        # Fake Wine exercises only gate control flow; it is not runtime evidence.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wine = root / 'wine'
            wine.write_text('#!' + sys.executable + '\n' + '''
import os, sys
if any('mcs.exe' in argument for argument in sys.argv):
    raise SystemExit(0)
kind = os.environ.get('PROBE_FAKE_KIND', 'pass')
for index in range(7): print('check=' + str(index))
if kind != 'missing': print('CCW_RELEASE_PROBE_PASS')
if kind == 'assert': print('Assertion at ccw_release')
if kind == 'exception': print('Unhandled Exception')
raise SystemExit(2 if kind == 'nonzero' else 0)
''')
            wine.chmod(0o755)
            winepath = root / 'winepath'
            winepath.write_text('#!/bin/sh\nprintf "%s\\n" "$2"\n')
            winepath.chmod(0o755)
            for kind in ('pass', 'missing', 'assert', 'exception', 'nonzero'):
                with self.subTest(kind=kind):
                    env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                               WINEPREFIX=str(root / 'prefix'), PROBE_FAKE_KIND=kind)
                    result = subprocess.run(['bash', str(ROOT / 'verify_mono_ccw.sh'), 'fixture.cs'],
                                            env=env, capture_output=True, text=True, timeout=30)
                    if kind == 'pass':
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout.count('CCW_RELEASE_PROBE_PASS'), 4)
                        self.assertIn('CCW_SHARED_RUNTIME_PASS', result.stdout)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertNotIn('CCW_SHARED_RUNTIME_PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
