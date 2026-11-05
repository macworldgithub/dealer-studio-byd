import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from dealerstudio_session import ROOT
from run_hourly import run, remove_previous, CommandFailure, execute


class HourlyTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / '.runtime'
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='hourly-test-', dir=root)
        self.path = Path(self.temp.name)
        self.backend = self.path / 'backend'
        importer = self.backend / 'scripts/import_dealerstudio.py'
        importer.parent.mkdir(parents=True)
        importer.write_text('# fixture')
        python = self.backend / ('venv/Scripts/python.exe' if os.name == 'nt' else 'venv/bin/python')
        python.parent.mkdir(parents=True)
        python.write_text('fixture')
        self.runtime = self.path / 'sync'
        self.runtime.mkdir()
        self.data = self.runtime / 'data'
        self.data.mkdir()
        (self.data / 'COMPLETE_DATA_MANIFEST.json').write_text(json.dumps({'old': True}))

    def tearDown(self):
        self.assertTrue(self.path.resolve().is_relative_to(ROOT / '.runtime'))
        self.temp.cleanup()

    def test_complete_snapshot_is_imported_and_verified_before_publish(self):
        calls = []
        def command(args, env):
            calls.append(args)
            self.assertTrue(json.loads((self.data / 'COMPLETE_DATA_MANIFEST.json').read_text()).get('old'))
            if args[1].endswith('fetch_complete_data.py'):
                pending = Path(env['DEALERSTUDIO_OUTPUT_DIR'])
                pending.mkdir()
                (pending / 'COMPLETE_DATA_MANIFEST.json').write_text(json.dumps({'complete': True, 'statistics': {'total_historic_leads': 1}}))
                return ''
            if '--dry-run' in args:
                return json.dumps({'conflicts': []})
            self.assertIn('--require-fresh', args)
            self.assertIn('--backup', args)
            return json.dumps({'verified': True, 'second_run_changes': 0, 'modified_clients': 1})
        result = run(self.backend, self.runtime, command)
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(len(calls), 2)
        self.assertTrue(json.loads((self.data / 'COMPLETE_DATA_MANIFEST.json').read_text())['complete'])
        self.assertTrue((self.runtime / 'data.previous/COMPLETE_DATA_MANIFEST.json').is_file())

    def test_failed_import_preserves_last_successful_export(self):
        def command(args, env):
            if args[1].endswith('fetch_complete_data.py'):
                pending = Path(env['DEALERSTUDIO_OUTPUT_DIR'])
                pending.mkdir()
                (pending / 'COMPLETE_DATA_MANIFEST.json').write_text(json.dumps({'complete': True}))
                return ''
            raise RuntimeError('fixture importer failed')
        with self.assertRaises(RuntimeError): run(self.backend, self.runtime, command)
        self.assertTrue(json.loads((self.data / 'COMPLETE_DATA_MANIFEST.json').read_text())['old'])
        self.assertEqual(json.loads((self.runtime / 'last-run.json').read_text())['status'], 'failed')

    def test_incomplete_snapshot_cannot_reach_the_database_importer(self):
        calls = []
        def command(args, env):
            calls.append(args)
            pending = Path(env['DEALERSTUDIO_OUTPUT_DIR'])
            pending.mkdir()
            (pending / 'COMPLETE_DATA_MANIFEST.json').write_text(json.dumps({'complete': False}))
            return ''
        with self.assertRaises(RuntimeError): run(self.backend, self.runtime, command)
        self.assertEqual(len(calls), 1)

    def test_rotation_refuses_paths_outside_owned_generated_snapshot(self):
        with self.assertRaises(RuntimeError): remove_previous(ROOT / 'api_data', self.runtime)

    def test_transient_database_failure_replans_with_a_new_backup_then_publishes(self):
        attempts, backups, delays = [], [], []
        def command(args, env):
            if args[1].endswith('fetch_complete_data.py'):
                pending = Path(env['DEALERSTUDIO_OUTPUT_DIR'])
                pending.mkdir()
                (pending / 'COMPLETE_DATA_MANIFEST.json').write_text(json.dumps({'complete': True, 'statistics': {}}))
                return ''
            attempts.append(args)
            backups.append(args[args.index('--backup') + 1])
            self.assertNotIn('--dry-run', args)
            self.assertIn('--progress', args)
            if len(attempts) == 1:
                raise CommandFailure('fixture network timeout', retryable=True)
            return json.dumps({'verified': True, 'second_run_changes': 0})
        result = run(self.backend, self.runtime, command, sleep=delays.append)
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['attempt'], 2)
        self.assertNotEqual(backups[0], backups[1])
        self.assertEqual(delays, [5])

    def test_validation_failures_are_not_retried_or_published(self):
        attempts = []
        def command(args, env):
            if args[1].endswith('fetch_complete_data.py'):
                pending = Path(env['DEALERSTUDIO_OUTPUT_DIR'])
                pending.mkdir()
                (pending / 'COMPLETE_DATA_MANIFEST.json').write_text(json.dumps({'complete': True}))
                return ''
            attempts.append(args)
            raise CommandFailure('fixture validation failure')
        with self.assertRaises(CommandFailure): run(self.backend, self.runtime, command)
        self.assertEqual(len(attempts), 1)
        self.assertTrue(json.loads((self.data / 'COMPLETE_DATA_MANIFEST.json').read_text())['old'])

    def test_execute_retries_only_recognized_database_connection_errors(self):
        for error, retryable in [('NetworkTimeout', True), ('AutoReconnect', True), ('ValueError', False), ('BulkWriteError', False)]:
            result = SimpleNamespace(returncode=1, stdout=json.dumps({'error': error}), stderr='')
            with self.subTest(error=error), patch('run_hourly.subprocess.run', return_value=result), patch('run_hourly.atomic_json'):
                with self.assertRaises(CommandFailure) as caught:
                    execute(['python', 'import_dealerstudio.py'], {})
                self.assertEqual(caught.exception.retryable, retryable)


if __name__ == '__main__':
    unittest.main()
