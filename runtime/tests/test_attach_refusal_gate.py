"""Portable harness contracts; actual Wine evidence is produced separately."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('attach_refusal_gate', ROOT / 'smoke-test/verify-attach-refusal.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class AttachRefusalHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cli = self.root / 'fake cli'
        self.trace = self.root / 'calls.jsonl'
        self.cli.write_text(f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
with Path(os.environ['ATTACH_TEST_TRACE']).open('a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\\n')
print(json.dumps({'success': False, 'error': {'code': (
    os.environ.get('ATTACH_TEST_ERROR', 'ExistingHostNotFound') if 'start' in sys.argv else 'ConnectionRefusedError')}}))
print('original native diagnostic', file=sys.stderr)
sys.exit(7 if 'start' in sys.argv else 1)
''')
        self.cli.chmod(0o755)
        self.env = mock.patch.dict(os.environ, {'ATTACH_TEST_TRACE': str(self.trace)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.inventory = mock.patch.object(gate, 'inventory', return_value={'raw': 'PID PPID COMMAND\n', 'relevant': []})
        self.inventory.start()
        self.addCleanup(self.inventory.stop)

    def test_one_start_preserves_original_json_stderr_exit_and_does_not_stop(self):
        directory = self.root / 'proof'
        proof = gate.verify(directory, str(self.cli), '127.0.0.1:19496')
        self.assertTrue(proof['success'])
        self.assertEqual(proof['startup_calls'], 1)
        self.assertEqual([row['exit_code'] for row in proof['events']], [1, 7, 1])
        self.assertIn('original native diagnostic', (directory / 'attach-existing.stderr').read_text())
        self.assertEqual(json.loads((directory / 'attach-existing.stdout').read_text())['error']['code'], 'ExistingHostNotFound')
        calls = [json.loads(line) for line in self.trace.read_text().splitlines()]
        self.assertEqual(sum('start' in args for args in calls), 1)
        self.assertFalse(any('stop' in args or 'restart' in args for args in calls))
        with self.assertRaises(FileExistsError):
            gate.verify(directory, str(self.cli), '127.0.0.1:19496')
        self.assertEqual(len(self.trace.read_text().splitlines()), 3)

    def test_wrong_native_error_is_failed_and_persisted_without_retry(self):
        directory = self.root / 'failed'
        with mock.patch.dict(os.environ, {'ATTACH_TEST_ERROR': 'WorkerStartupError'}), self.assertRaises(AssertionError):
            gate.verify(directory, str(self.cli), '127.0.0.1:19496')
        proof = json.loads((directory / 'attach-refusal.json').read_text())
        self.assertTrue(proof['completed'])
        self.assertFalse(proof['success'])
        self.assertEqual(proof['startup_calls'], 1)
        self.assertEqual([row['name'] for row in proof['events']], ['status-before', 'attach-existing'])

    def test_preexisting_host_is_not_touched(self):
        with mock.patch.object(gate, 'inventory', return_value={'raw': 'existing', 'relevant': [{'name': 'SLDWORKS.exe'}]}), self.assertRaises(AssertionError):
            gate.verify(self.root / 'occupied', str(self.cli), '127.0.0.1:19496')
        proof = json.loads((self.root / 'occupied/attach-refusal.json').read_text())
        self.assertEqual(proof['startup_calls'], 0)
        self.assertIn('Pre-existing', proof['first_failure']['message'])
        self.assertFalse(self.trace.exists())
