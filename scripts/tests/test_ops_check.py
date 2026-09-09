import hashlib
import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location('ops_check', Path(__file__).resolve().parents[1] / 'ops_check.py')
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


class OpsCheckTests(unittest.TestCase):
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
