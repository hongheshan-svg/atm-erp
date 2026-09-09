import importlib.util
import argparse
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location('ota_runner', Path(__file__).parents[1] / 'ota_runner.py')
ota = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ota)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_extract_rejects_traversal_and_symlinks(self):
        for name in ('../outside', '/absolute', 'root/../../outside', 'root/C:stream'):
            archive = self.folder / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr(name, 'bad')
            with self.assertRaises(ValueError):
                ota.unpack(archive, self.folder / 'out', 'v2.0.0', 'docker', 'linux')
        with zipfile.ZipFile(archive, 'w') as bundle:
            entry = zipfile.ZipInfo('root/link')
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            bundle.writestr(entry, '/etc/passwd')
        with self.assertRaises(ValueError):
            ota.unpack(archive, self.folder / 'out', 'v2.0.0', 'docker', 'linux')

    def test_download_rejects_hash_mismatch(self):
        with patch.object(ota.urllib.request, 'urlopen', return_value=io.BytesIO(b'bad')):
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                ota.download({'url': 'https://github.com/test', 'sha256': 'a' * 64, 'size': 3}, self.folder / 'package.zip')

    def test_host_verifies_published_asset_digest_again(self):
        name = 'atm-erp-v2.0.0-linux-docker.zip'
        release = {'tag_name': 'v2.0.0', 'assets': [{'name': name, 'digest': 'sha256:' + 'a' * 64,
                    'size': 1, 'browser_download_url': f'https://github.com/{ota.REPO}/releases/download/v2.0.0/{name}'}]}
        job = {'target': 'v2.0.0', 'asset': {'sha256': 'b' * 64}}
        with patch.object(ota.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(release).encode())):
            with self.assertRaises(ValueError):
                ota.trusted_asset(job, 'docker', 'linux')

    def test_reports_survive_application_downtime(self):
        runner = object.__new__(ota.Runner)
        runner.state = {'pending': []}
        runner.path = self.folder / 'state.json'
        job = {'id': 1, 'claim': 'secret'}
        with patch.object(runner, 'api', side_effect=OSError('offline')):
            runner.report(job, 'installing', '备份完成', '/backup')
        self.assertEqual(json.loads(runner.path.read_text())['pending'][0]['status'], 'installing')
        with patch.object(runner, 'api', return_value={}):
            runner.flush()
        self.assertEqual(json.loads(runner.path.read_text())['pending'], [])

    def test_terminal_status_is_recorded_before_network_confirmation(self):
        runner = object.__new__(ota.Runner)
        runner.state = {'pending': [], 'inflight': {'id': 7, 'claim': 'secret'}}
        runner.path = self.folder / 'state.json'
        with patch.object(runner, 'api', side_effect=OSError('offline')):
            runner.report(runner.state['inflight'], 'succeeded', '完成')
        saved = json.loads(runner.path.read_text())
        self.assertEqual(saved['terminal'], 7)
        self.assertEqual(saved['pending'][0]['status'], 'succeeded')

    def test_commands_ignore_ambient_compose_project_overrides(self):
        runner = object.__new__(ota.Runner)
        with patch.dict(ota.os.environ, {'LEAN_PROJECT_NAME': 'other-project', 'COMPOSE_PROJECT_NAME': 'other-project'}), \
                patch.object(ota.subprocess, 'run') as run:
            runner.command(['docker', 'compose', 'version'], io.StringIO())
        self.assertNotIn('LEAN_PROJECT_NAME', run.call_args.kwargs['env'])
        self.assertNotIn('COMPOSE_PROJECT_NAME', run.call_args.kwargs['env'])

    def test_second_runner_cannot_overwrite_live_state(self):
        path = self.folder / 'state.json'
        path.write_text('{"inflight": {"id": 1}}')
        args = argparse.Namespace(mode='docker', root=self.folder, config=self.folder / 'config',
                                  state_dir=self.folder, url='http://127.0.0.1:8080')
        with ota.exclusive(self.folder / 'runner.lock'):
            with self.assertRaises(OSError):
                ota.Runner(args)
        self.assertEqual(json.loads(path.read_text()), {'inflight': {'id': 1}})
