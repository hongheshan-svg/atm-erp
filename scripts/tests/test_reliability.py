import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).parents[2]


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReliabilityTests(unittest.TestCase):
    def test_native_backup_expands_path_and_refuses_missing_uploads(self):
        ota = load(ROOT / 'scripts/ota_runner.py')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            uploads = root / 'data/uploads'
            uploads.mkdir(parents=True)
            (uploads / 'evidence.txt').write_text('evidence')
            backup = root / 'backup'
            backup.mkdir()
            runner = object.__new__(ota.Runner)
            runner.config = root / 'config.json'
            runner.config.write_text('{}')
            runner.values = dict(DATA_DIR='~/data', DB_PASSWORD='test', DB_HOST='test', DB_PORT='5432', DB_USER='test', DB_NAME='test')
            runner.command = lambda *args, **kwargs: (backup / 'database.dump').write_bytes(b'fake pg dump')
            with patch.object(Path, 'expanduser', return_value=root / 'data'):
                runner.native_backup(backup, None)
            with tarfile.open(backup / 'uploads.tar') as archive:
                self.assertEqual(archive.extractfile('evidence.txt').read(), b'evidence')
            runner.values['DATA_DIR'] = str(root / 'missing')
            with self.assertRaises(ValueError):
                runner.native_backup(backup, None)

    def test_upload_restore_is_retryable_and_never_overwrites_other_files(self):
        restore = load(ROOT / 'scripts/restore_uploads.py')
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode='w') as archive:
            entry = tarfile.TarInfo('protected/a.txt'); entry.size = 5
            archive.addfile(entry, io.BytesIO(b'hello'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for _ in range(2):
                restore.prepare(root, io.BytesIO(raw.getvalue()), 'same-archive')
                self.assertEqual((root / 'protected/a.txt').read_bytes(), b'hello')
            with self.assertRaises(ValueError):
                restore.prepare(root, io.BytesIO(raw.getvalue()), 'different-archive')
            (root / 'private.txt').write_text('keep')
            with self.assertRaises(ValueError):
                restore.prepare(root, io.BytesIO(raw.getvalue()), 'same-archive')
            self.assertEqual((root / 'private.txt').read_text(), 'keep')

    def test_watchdog_tolerates_transient_failures_and_exits_on_six_consecutive_failures(self):
        watchdog = load(ROOT / 'docker/app/watchdog.py')
        probe = Mock(side_effect=[False] * 5 + [True] + [False] * 6)
        stop = Mock()
        watchdog.monitor(probe=probe, sleep=Mock(), terminate=stop)
        self.assertEqual(probe.call_count, 12)
        stop.assert_called_once()
