"""Fetch and verify Denza data, then run the guarded delivery backend upsert."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from dealerstudio_session import ROOT, atomic_json


class CommandFailure(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def execute(args, env):
    result = subprocess.run(args, cwd=ROOT, env=env, text=True, encoding='utf8', capture_output=True)
    if result.returncode:
        # Detailed output stays in a private file rather than the public status receipt.
        atomic_json(ROOT / '.runtime/last-command-error.json', {'script': Path(args[1]).name, 'exit': result.returncode,
                    'stdout': result.stdout, 'stderr': result.stderr})
        try:
            failure = json.loads(result.stdout.strip())
        except ValueError:
            failure = {}
        retryable = Path(args[1]).name == 'import_dealerstudio.py' and failure.get('error') in {
            'NetworkTimeout', 'AutoReconnect', 'ConnectionFailure', 'ServerSelectionTimeoutError', 'CursorNotFound'}
        raise CommandFailure(f'{Path(args[1]).name} failed (exit {result.returncode}); see .runtime/last-command-error.json. Previous published data was retained.', retryable)
    return result.stdout


def remove_previous(previous, runtime):
    target = previous.resolve()
    if not target.is_relative_to(runtime.resolve()) or target.name != 'data.previous':
        raise RuntimeError('Refusing to remove a directory outside the generated snapshot area.')
    if target.exists():
        if not (target / 'COMPLETE_DATA_MANIFEST.json').is_file():
            raise RuntimeError('The previous directory is not a generated Dealer Studio snapshot.')
        shutil.rmtree(target)


def run(backend, runtime, command=execute, env=None, sleep=time.sleep):
    backend, runtime = Path(backend).resolve(), Path(runtime).resolve()
    if not runtime.is_relative_to(ROOT / '.runtime'):
        raise ValueError('The sync runtime must remain inside the project .runtime directory.')
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    backups = runtime / 'backups'
    backups.mkdir(exist_ok=True, mode=0o700)
    started = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex
    pending, snapshot, previous = runtime / ('pending-' + stamp), runtime / 'data', runtime / 'data.previous'
    backup = backups / ('dealerstudio-before-' + stamp + '.ejson.gz')
    status_file = runtime / 'last-run.json'
    status = {'status': 'running', 'startedAt': started, 'snapshot': str(snapshot), 'pending': str(pending), 'backup': str(backup)}
    atomic_json(status_file, status)
    config = {k: str(v) for k, v in {**os.environ, **(env or {}), 'DEALERSTUDIO_OUTPUT_DIR': str(pending), 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}.items() if v is not None}
    try:
        importer = backend / 'scripts/import_dealerstudio.py'
        python = backend / ('venv/Scripts/python.exe' if os.name == 'nt' else 'venv/bin/python')
        if not importer.is_file() or not python.is_file():
            raise RuntimeError('The guarded importer or backend Python environment is not installed.')
        command([sys.executable, str(ROOT / 'fetch_complete_data.py')], config)
        manifest = json.loads((pending / 'COMPLETE_DATA_MANIFEST.json').read_text(encoding='utf8'))
        if manifest.get('complete') is not True:
            raise RuntimeError('The harvester did not verify a complete snapshot.')
        args = [str(python), str(importer), '--input', str(pending), '--require-fresh', '--progress', str(runtime / 'database-progress.json')]
        # The importer validates the complete plan and conflicts before backing up
        # or writing. Avoid downloading the same collections in a second dry run.
        for attempt in range(1, 4):
            if attempt > 1:
                backup = backups / ('dealerstudio-before-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex + '.ejson.gz')
            status.update(phase='database_import', attempt=attempt, backup=str(backup))
            atomic_json(status_file, status)
            try:
                result = json.loads(command([*args, '--backup', str(backup)], config).strip())
                break
            except CommandFailure as error:
                if not error.retryable or attempt == 3:
                    raise
                status.update(phase='retrying_database', lastTransientError=str(error))
                atomic_json(status_file, status)
                sleep(5 * attempt)
        if not result.get('verified') or result.get('second_run_changes') != 0:
            raise RuntimeError('The database upsert did not pass verification.')
        if snapshot.exists():
            remove_previous(previous, runtime)
            snapshot.rename(previous)
        try:
            pending.rename(snapshot)
        except Exception:
            if previous.exists() and not snapshot.exists():
                previous.rename(snapshot)
            raise
        receipt = {**status, 'status': 'succeeded', 'finishedAt': datetime.now(timezone.utc).isoformat(),
                   'statistics': manifest['statistics'], 'database': result}
        atomic_json(status_file, receipt)
        # Retain seven days of this job's generated compressed backups only.
        cutoff = time.time() - 7 * 86400
        for file in backups.iterdir():
            if re.fullmatch(r'dealerstudio-before-\d{8}T\d{6}Z-[a-f0-9]{32}\.ejson\.gz', file.name) and file.is_file() and not file.is_symlink() and file.stat().st_mtime < cutoff:
                file.unlink()
        return receipt
    except Exception as error:
        atomic_json(status_file, {**status, 'status': 'failed', 'finishedAt': datetime.now(timezone.utc).isoformat(), 'message': str(error)})
        raise


def main():
    config = {**dotenv_values(ROOT / '.env'), **os.environ}
    backend = config.get('DEALERSTUDIO_BACKEND_ROOT') or ROOT.parent / 'shaun-backend'
    return run(backend, ROOT / '.runtime/sync', env=config)


if __name__ == '__main__':
    try:
        print(json.dumps(main()))
    except Exception as error:
        print(json.dumps({'status': 'failed', 'message': str(error)}))
        raise SystemExit(1)
