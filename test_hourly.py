import json
import os
import tempfile
import unittest
from pathlib import Path
from dealerstudio_session import ROOT
from run_hourly import run, remove_previous


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
        self.assertEqual(len(calls), 3)
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


if __name__ == '__main__':
    unittest.main()
