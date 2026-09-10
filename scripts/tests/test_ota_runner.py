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

    def test_running_container_version_wins_over_newer_checkout(self):
        runner = object.__new__(ota.Runner)
        runner.mode, runner.url, runner.root, runner.config = 'docker', 'http://localhost', self.folder, self.folder / '.env'
        version_file = self.folder / 'backend/apps/core/version.py'
        version_file.parent.mkdir(parents=True)
        version_file.write_text("VERSION = '1.7.1'")
        with patch.object(ota.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"version":"1.7.0"}')), \
                patch.object(ota.subprocess, 'check_output', return_value='1.7.0\n'):
            self.assertEqual(runner.running_version(), (1, 7, 0))

    def test_mismatched_docker_and_web_target_fails_closed(self):
        runner = object.__new__(ota.Runner)
        runner.mode, runner.url, runner.root, runner.config = 'docker', 'http://localhost', self.folder, self.folder / '.env'
        with patch.object(ota.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"version":"1.7.0"}')), \
                patch.object(ota.subprocess, 'check_output', return_value='1.7.2\n'):
            with self.assertRaisesRegex(ValueError, '不一致'):
                runner.running_version()

    def test_preflight_failure_does_not_claim_a_backup_exists(self):
        runner = object.__new__(ota.Runner)
        runner.directory, runner.path, runner.state = self.folder, self.folder / 'state.json', {'pending': []}
        reports = []
        with patch.object(runner, 'running_version', return_value=(1, 7, 1)), \
                patch.object(runner, 'report', side_effect=lambda *args: reports.append(args)):
            runner.execute({'id': 9, 'target': 'v1.7.1'})
        self.assertEqual(reports[-1][1], 'failed')
        self.assertIn('尚未生成完整备份', reports[-1][2])
        self.assertEqual(reports[-1][3], '')

    def test_download_reports_actual_bytes(self):
        import hashlib
        content = b'hello'
        progress = []
        with patch.object(ota.urllib.request, 'urlopen', return_value=io.BytesIO(content)):
            ota.download({'url': 'https://github.com/test', 'sha256': hashlib.sha256(content).hexdigest(), 'size': 5},
                         self.folder / 'package.zip', lambda *args: progress.append(args))
        self.assertEqual(progress[-1], (5, 5))

    def test_long_build_emits_progress_while_process_is_running(self):
        runner = object.__new__(ota.Runner)
        progress = []
        with patch.object(ota.subprocess, 'Popen') as popen:
            process = popen.return_value.__enter__.return_value
            process.wait.side_effect = [ota.subprocess.TimeoutExpired('build', 5), 0]
            runner.command(['docker', 'build'], io.StringIO(), progress=progress.append)
        self.assertEqual(len(progress), 1)

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
        self.assertEqual(json.loads(runner.path.read_text(encoding='utf-8'))['pending'][0]['status'], 'installing')
        with patch.object(runner, 'api', return_value={}):
            runner.flush()
        self.assertEqual(json.loads(runner.path.read_text(encoding='utf-8'))['pending'], [])

    def test_terminal_status_is_recorded_before_network_confirmation(self):
        runner = object.__new__(ota.Runner)
        runner.state = {'pending': [], 'inflight': {'id': 7, 'claim': 'secret'}}
        runner.path = self.folder / 'state.json'
        with patch.object(runner, 'api', side_effect=OSError('offline')):
            runner.report(runner.state['inflight'], 'succeeded', '完成')
        saved = json.loads(runner.path.read_text(encoding='utf-8'))
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
