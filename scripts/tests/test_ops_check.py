import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location('ops_check', Path(__file__).resolve().parents[1] / 'ops_check.py')
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import backup_cycle
finally:
    sys.path.pop(0)


class OpsCheckTests(unittest.TestCase):
    def test_cycle_refuses_overlap_and_keeps_existing_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local, remote = root / 'local', root / 'remote'
            local.mkdir()
            remote.mkdir()
            lock = local / '.backup-cycle.lock'
            lock.mkdir()
            with patch.object(backup_cycle.subprocess, 'run') as run:
                result = backup_cycle.cycle(root / 'explicit.env', local, remote, root, 'http://127.0.0.1/api/health/', root / 'status.json')
            self.assertFalse(result['ok'])
            run.assert_not_called()
            self.assertTrue(lock.exists())

    def test_cycle_copies_verified_archive_and_persists_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local, remote = root / 'local', root / 'remote'
            local.mkdir()
            remote.mkdir()
            status = root / 'status.json'

            def fake_backup(command, **kwargs):
                Path(command[-1]).write_bytes(b'isolated backup fixture')

            with (
                patch.object(backup_cycle.subprocess, 'run', side_effect=fake_backup),
                patch.object(backup_cycle, 'inspect', return_value={'ok': True}),
            ):
                result = backup_cycle.cycle(
                    root / 'explicit.env', local, remote, root, 'http://127.0.0.1/api/health/', status
                )
            self.assertTrue(result['ok'])
            self.assertEqual(Path(result['archive']).read_bytes(), Path(result['offsite']).read_bytes())
            with patch.object(backup_cycle.subprocess, 'run', side_effect=RuntimeError('backup failed')):
                failure = backup_cycle.cycle(
                    root / 'explicit.env', local, remote, root, 'http://127.0.0.1/api/health/', status
                )
            self.assertFalse(failure['ok'])
            self.assertFalse(json.loads(status.read_text())['ok'])
            self.assertEqual(len(list(remote.glob('*.zip'))), 1)

    def test_backup_integrity_freshness_and_disk_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(ops.inspect(root, root)['ok'])
            archive = root / 'backup.zip'
            payloads = {'database.dump': b'database fixture', 'uploads.tar': b'attachment fixture'}
            with ZipFile(archive, 'w') as bundle:
                bundle.writestr(
                    'manifest.json',
                    json.dumps(
                        {'sha256': {name: hashlib.sha256(value).hexdigest() for name, value in payloads.items()}}
                    ),
                )
                for name, value in payloads.items():
                    bundle.writestr(name, value)
            self.assertTrue(ops.inspect(root, root, min_free_gb=0)['ok'])
            self.assertFalse(ops.inspect(root, root, min_free_gb=10**9)['ok'])
            old = time.time() - 27 * 3600
            os.utime(archive, (old, old))
            self.assertFalse(ops.inspect(root, root, min_free_gb=0)['ok'])
            (root / 'new-partial.zip').write_bytes(b'incomplete archive')
            result = ops.inspect(root, root, min_free_gb=0)
            self.assertFalse(result['ok'])
            self.assertTrue(any('不完整' in message for message in result['failures']))


if __name__ == '__main__':
    unittest.main()
