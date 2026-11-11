import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location('backup', Path(__file__).parents[1] / 'backup.py')
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


def uploads_tar():
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w') as archive:
        entry = tarfile.TarInfo('./evidence.txt')
        entry.size = 5
        archive.addfile(entry, io.BytesIO(b'hello'))
    return raw.getvalue()


class FakeDocker:
    """只应答 backup.py 实际发出的 docker/compose 调用，并按顺序记录。"""

    def __init__(self, version):
        self.version = version  # 容器实际运行的程序版本；None 表示无法确认
        self.calls = []

    def compose_args(self, command):
        return command[command.index('-f') + 2 :] if '-f' in command else []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        args = self.compose_args(command)
        stdout = ''
        if args[:1] == ['config']:
            stdout = json.dumps({'services': {'app': {'image': 'atm-erp-lean:test'}}})
        elif 'psql' in args:
            stdout = backup.GENERATION if 'lean_schema' in args[-1] else '0'
        elif args[:1] == ['run'] and '-c' in args:
            if self.version is None:
                raise subprocess.CalledProcessError(1, command)
            stdout = self.version + '\n'
        elif 'pg_dump' in args:
            kwargs['stdout'].write(b'database')
        elif args[:1] == ['run'] and 'tar' in args:
            kwargs['stdout'].write(uploads_tar())
        return subprocess.CompletedProcess(command, 0, stdout=stdout)

    def index(self, predicate):
        return next(i for i, call in enumerate(self.calls) if predicate(self.compose_args(call)))

    def ran(self, word):
        return any(word in call for call in self.calls)


class BackupVersionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = self.root / '.env'
        self.env.write_text('LEAN_PROJECT_NAME=test\n')
        # main() 收紧进程 umask，测试结束后恢复。
        previous = os.umask(0o022)
        os.umask(previous)
        self.addCleanup(os.umask, previous)

    def main(self, docker, *args):
        argv = ['backup.py', *args, '--env-file', str(self.env)]
        stderr = io.StringIO()
        with patch.object(backup.subprocess, 'run', side_effect=docker), patch.object(sys, 'argv', argv):
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                try:
                    backup.main()
                except SystemExit as exc:
                    return exc.code, stderr.getvalue()
        return 0, stderr.getvalue()

    def make_archive(self, manifest_extra):
        files = {'database.dump': b'database', 'uploads.tar': uploads_tar()}
        manifest = {
            'schema': backup.GENERATION,
            'sha256': {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
            **manifest_extra,
        }
        archive = self.root / 'restore.zip'
        with ZipFile(archive, 'w') as bundle:
            bundle.writestr('manifest.json', json.dumps(manifest))
            for name, content in files.items():
                bundle.writestr(name, content)
        return archive

    def restore(self, docker, manifest_extra):
        return self.main(docker, 'restore', '--archive', str(self.make_archive(manifest_extra)))

    def test_backup_records_program_version_before_stopping_app(self):
        docker = FakeDocker('1.8.31')
        archive = self.root / 'backup.zip'
        code, _ = self.main(docker, 'backup', '--archive', str(archive))
        self.assertEqual(code, 0)
        with ZipFile(archive) as bundle:
            manifest = json.loads(bundle.read('manifest.json'))
        self.assertEqual(manifest['version'], '1.8.31')
        self.assertEqual(manifest['schema'], backup.GENERATION)
        probe = docker.index(lambda args: args[:1] == ['run'] and '-c' in args)
        self.assertEqual(docker.calls[probe][-1], backup.VERSION_PROBE)
        self.assertLess(probe, docker.index(lambda args: args == ['stop', 'app']))

    def test_backup_still_completes_without_version_and_warns(self):
        archive = self.root / 'backup.zip'
        code, stderr = self.main(FakeDocker(None), 'backup', '--archive', str(archive))
        self.assertEqual(code, 0)
        with ZipFile(archive) as bundle:
            self.assertNotIn('version', json.loads(bundle.read('manifest.json')))
        self.assertIn('无法确认部署实际运行的程序版本', stderr)

    def test_restore_refuses_older_target_before_touching_database(self):
        docker = FakeDocker('1.8.20')
        code, stderr = self.restore(docker, {'version': '1.8.31'})
        self.assertEqual(code, 2)
        self.assertIn('1.8.31', stderr)
        self.assertIn('1.8.20', stderr)
        for word in ('up', 'pg_restore', '/restore_uploads.py'):
            self.assertFalse(docker.ran(word), word)

    def test_restore_compares_versions_numerically(self):
        docker = FakeDocker('1.10.0')
        code, _ = self.restore(docker, {'version': '1.9.5'})
        self.assertEqual(code, 0)
        self.assertTrue(docker.ran('pg_restore'))

    def test_restore_of_legacy_manifest_skips_version_probe(self):
        docker = FakeDocker('1.0.0')
        code, stderr = self.restore(docker, {})
        self.assertEqual(code, 0)
        self.assertTrue(docker.ran('pg_restore'))
        self.assertFalse(any('-c' in docker.compose_args(call) for call in docker.calls))
        self.assertIn('未记录程序版本', stderr)

    def test_restore_warns_and_continues_when_target_version_unknown(self):
        docker = FakeDocker(None)
        code, stderr = self.restore(docker, {'version': '1.8.31'})
        self.assertEqual(code, 0)
        self.assertIn('无法确认目标部署的程序版本', stderr)
        self.assertTrue(docker.ran('pg_restore'))

    def test_restore_rejects_malformed_manifest_version(self):
        docker = FakeDocker('1.8.31')
        code, stderr = self.restore(docker, {'version': 'latest'})
        self.assertEqual(code, 2)
        self.assertIn('程序版本无效', stderr)
        self.assertFalse(docker.ran('pg_restore'))


if __name__ == '__main__':
    unittest.main()
