import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
runtime = importlib.import_module('container_runtime')
ota = importlib.import_module('container_ota')


class ContainerTests(unittest.TestCase):
    def test_fixture_wheels_owned_by_host_packager(self):
        from scripts.tests import container_ota_smoke as smoke
        with patch.object(smoke.os, 'getuid', return_value=1001), \
                patch.object(smoke.os, 'getgid', return_value=1002), \
                patch.object(smoke.subprocess, 'run') as run:
            smoke.export_fixture_wheels('isolated-test-image', Path('/isolated/wheels'))
        argv = run.call_args.args[0]
        self.assertEqual(argv[argv.index('--user') + 1], '1001:1002')
        self.assertEqual(argv[argv.index('--network') + 1], 'none')
        self.assertTrue(run.call_args.kwargs['check'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name).resolve()
        self.base = self.data / 'base'
        (self.base / 'apps/core').mkdir(parents=True)
        (self.base / 'apps/core/version.py').write_text("VERSION = '1.8.8'\n")
        self.target = self.data / 'job-1/release/atm-erp-v9.0.0-linux-native'
        (self.target / 'backend/apps/core').mkdir(parents=True)
        (self.target / 'backend/apps/core/version.py').write_text("VERSION = '9.0.0'\n")
        for name, value in [('DATA', self.data), ('BASE', self.base)]:
            patcher = patch.object(runtime, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def activate(self):
        ota.atomic_json(self.data / 'active.json', {'release': str(self.target.relative_to(self.data))})

    def runner(self):
        runner = object.__new__(ota.ContainerRunner)
        runner.directory = self.data
        runner.path = self.data / 'state.json'
        runner.state = {'pending': []}
        runner.url = 'http://127.0.0.1:8080'
        runner.report = Mock()
        runner.running_version = Mock(return_value=(1, 8, 8))
        runner.prepare = Mock()
        runner.control = Mock()
        runner.backup = Mock()
        runner.command = Mock()
        runner.reserve_space = Mock()
        runner.check_backup_space = Mock()
        return runner

    def execute(self, runner, job_id=2, restart=True):
        target = self.data / f'job-{job_id}/release/atm-erp-v9.0.0-linux-native'
        def unpack(*_):
            shutil.copytree(self.target, target)
            self.target = target
            (target / '.venv/bin').mkdir(parents=True)
            (target / '.venv/bin/python').touch()
            return target
        with patch.object(ota, 'trusted_asset', return_value={'sha256': 'verified', 'size': 10}), patch.object(ota, 'download'), \
                patch.object(ota, 'unpack', side_effect=unpack), patch.object(runtime, 'frontend'), \
                patch.object(ota, 'file_hash', return_value='verified'), \
                patch.object(ota.urllib.request, 'urlopen') as health:
            health.return_value.__enter__.return_value.read.return_value = b'{"version":"9.0.0"}'
            job = {'id': job_id, 'target': 'v9.0.0', 'claim': 'test', 'status': 'downloading'}
            runner.execute(job)
            if restart and runner.is_prepared(job):
                runner.dispatch({**job, 'status': 'restarting', 'recovered': True})

    def test_prepared_update_survives_worker_restart_without_stopping_app(self):
        runner = self.runner()
        self.execute(runner, restart=False)
        runner.control.assert_not_called()
        runner.backup.assert_not_called()
        runner.command.assert_not_called()
        self.assertFalse((self.data / 'active.json').exists())
        job = {'id': 2, 'target': 'v9.0.0', 'claim': 'test', 'status': 'ready', 'recovered': True}
        runner.state = json.loads(runner.path.read_text())
        runner.state['inflight'] = job
        runner.recover()
        runner.report.reset_mock()
        runner.dispatch(job)
        runner.report.assert_not_called()
        runner.control.assert_not_called()
        self.assertTrue(runner.is_prepared(job))

    def test_restart_without_prepared_files_is_not_executed(self):
        runner = self.runner()
        runner.dispatch({'id': 2, 'target': 'v9.0.0', 'claim': 'test', 'status': 'restarting', 'recovered': True})
        runner.control.assert_not_called()
        self.assertEqual(runner.report.call_args.args[1], 'failed')

    def test_source_version_changed_cancels_prepared_update_without_stopping(self):
        runner = self.runner()
        self.execute(runner, restart=False)
        runner.running_version.return_value = (2, 0, 0)
        runner.dispatch({'id': 2, 'target': 'v9.0.0', 'claim': 'test', 'status': 'ready', 'recovered': True})
        runner.control.assert_not_called()
        runner.command.assert_not_called()
        self.assertNotIn('prepared', runner.state)
        self.assertEqual(runner.report.call_args.args[1], 'failed')

    def test_prepared_archive_corruption_cannot_stop_or_migrate(self):
        runner = self.runner()
        self.execute(runner, restart=False)
        with patch.object(ota, 'trusted_asset', return_value={'sha256': 'original'}), \
                patch.object(ota, 'file_hash', return_value='corrupt'):
            runner.dispatch({'id': 2, 'target': 'v9.0.0', 'claim': 'test', 'status': 'restarting', 'recovered': True})
        runner.control.assert_not_called()
        runner.command.assert_not_called()
        self.assertEqual(runner.report.call_args.args[1], 'failed')

    def test_recreation_uses_persistent_release_and_never_older_base(self):
        self.activate()
        self.assertEqual(runtime.selected()[0], self.target / 'backend')
        (self.base / 'apps/core/version.py').write_text("VERSION = '10.0.0'\n")
        self.assertEqual(runtime.selected()[0], self.base)

    def test_worker_killed_during_backup_restarts_app_before_reporting(self):
        runner = self.runner()
        job = {'id': 2, 'target': 'v9.0.0', 'claim': 'test'}
        runner.state['inflight'] = job
        runner.phase('backup', job)
        events = []
        runner.control.side_effect = lambda action, _: events.append(action)
        runner.report.side_effect = lambda *_: events.append('report')
        runner.recover()
        self.assertEqual(events, ['start', 'report'])
        self.assertFalse(runtime.journal())
        self.assertNotIn('inflight', runner.state)

    def test_failed_restart_retains_recovery_journal(self):
        runner = self.runner()
        runner.state['inflight'] = {'id': 2, 'target': 'v9.0.0'}
        runner.phase('backup', runner.state['inflight'])
        runner.control.side_effect = ota.subprocess.CalledProcessError(1, 'start')
        with self.assertRaises(ota.subprocess.CalledProcessError):
            runner.recover()
        self.assertEqual(runtime.journal()['phase'], 'backup')
        self.assertIn('inflight', runner.state)
        runner.report.assert_not_called()

    def test_worker_killed_after_migration_cannot_restart_old_code(self):
        runner = self.runner()
        runner.state['inflight'] = {'id': 2, 'target': 'v9.0.0'}
        runner.phase('migrating', runner.state['inflight'])
        runner.recover()
        self.assertEqual(runner.control.call_args.args[0], 'stop')
        self.assertEqual(runtime.journal()['phase'], 'blocked')
        self.assertEqual(runner.report.call_args.args[1], 'failed')

    def test_switched_version_is_verified_and_reconciled_after_interruption(self):
        runner = self.runner()
        self.activate()
        job = {'id': 1, 'target': 'v9.0.0'}
        runner.state['inflight'] = job
        runner.phase('verifying', job)
        runner.verify = Mock()
        runner.recover()
        runner.verify.assert_called_once_with(job)
        self.assertEqual([call.args[1] for call in runner.report.call_args_list], ['verifying', 'succeeded'])
        self.assertEqual(runner.report.call_args.args[1], 'succeeded')
        self.assertFalse(runtime.journal())
        self.assertNotIn('inflight', runner.state)

    def test_container_boot_keeps_verification_journal_for_worker(self):
        ota.atomic_json(self.data / 'maintenance.json', {'phase': 'verifying', 'job': 1})
        with patch.dict(os.environ, OTA_MODE='host'), patch.object(runtime.subprocess, 'run'), \
                patch.object(runtime, 'frontend'):
            runtime.initialize()
        self.assertEqual(runtime.journal()['phase'], 'verifying')

    def test_success_acknowledged_before_crash_never_reports_older_stage(self):
        runner = self.runner()
        self.activate()
        job = {'id': 1, 'target': 'v9.0.0'}
        runner.state.update(inflight=job, terminal=1)
        runner.phase('verifying', job)
        runner.verify = Mock()
        runner.recover()
        self.assertEqual([call.args[1] for call in runner.report.call_args_list], ['succeeded'])
        self.assertFalse(runtime.journal())

    def test_unhealthy_switched_version_is_blocked(self):
        runner = self.runner()
        self.activate()
        job = {'id': 1, 'target': 'v9.0.0'}
        runner.state['inflight'] = job
        runner.phase('verifying', job)
        runner.verify = Mock(side_effect=RuntimeError('unhealthy'))
        runner.recover()
        self.assertEqual(runner.control.call_args.args[0], 'stop')
        self.assertEqual(runtime.journal()['phase'], 'blocked')

    def test_low_disk_is_rejected_before_stop(self):
        runner = self.runner()
        runner.check_backup_space.side_effect = RuntimeError('disk full')
        self.execute(runner)
        runner.control.assert_not_called()
        runner.command.assert_not_called()
        with patch.object(ota.shutil, 'disk_usage', return_value=Mock(free=100)):
            with self.assertRaisesRegex(RuntimeError, '空间不足'):
                ota.ContainerRunner.reserve_space(runner, 200)

    def test_rejects_pointer_traversal_and_symlink_escape(self):
        ota.atomic_json(self.data / 'active.json', {'release': '../elsewhere'})
        with self.assertRaises(ValueError):
            runtime.selected()
        self.activate()
        with patch.object(Path, 'resolve', side_effect=[Path('/outside'), self.data]):
            with self.assertRaises(ValueError):
                runtime.selected()

    def test_interrupted_migration_blocks_restart(self):
        for phase in ('migrating', 'blocked'):
            ota.atomic_json(self.data / 'maintenance.json', {'phase': phase})
            with self.assertRaises(RuntimeError):
                runtime.assert_bootable()
        ota.atomic_json(self.data / 'maintenance.json', {'phase': 'backup'})
        runtime.assert_bootable()

    def test_management_command_uses_active_virtualenv_and_backend(self):
        self.activate()
        with patch.object(sys, 'argv', ['runtime', 'manage', 'check']), \
                patch.object(runtime.os, 'chdir') as chdir, \
                patch.object(runtime.os, 'execv', side_effect=SystemExit) as execute:
            with self.assertRaises(SystemExit):
                runtime.main()
        chdir.assert_called_once_with(self.target / 'backend')
        execute.assert_called_once_with(str(self.target / '.venv/bin/python'),
                                        [str(self.target / '.venv/bin/python'), 'manage.py', 'check'])

    def test_bad_checksum_cannot_stop_or_migrate(self):
        runner = self.runner()
        with patch.object(ota, 'trusted_asset', side_effect=ValueError('SHA256 mismatch')):
            runner.execute({'id': 2, 'target': 'v9.0.0', 'claim': 'test'})
        runner.control.assert_not_called()
        runner.command.assert_not_called()
        self.assertEqual(runner.report.call_args.args[1], 'failed')

    def test_preparation_failure_does_not_stop_app(self):
        runner = self.runner()
        runner.prepare.side_effect = ValueError('incompatible runtime')
        self.execute(runner)
        runner.control.assert_not_called()
        self.assertFalse((self.data / 'active.json').exists())

    def test_runtime_protocol_mismatch_rejected_before_dependency_commands(self):
        runner = self.runner()
        (self.target / 'INSTALL-MANIFEST.json').write_text('{"container_runtime": 2}')
        with self.assertRaises(ValueError):
            ota.ContainerRunner.prepare(runner, self.target, Mock(), {'id': 1})
        runner.command.assert_not_called()

    def test_backup_failure_restarts_unchanged_app_without_migration(self):
        runner = self.runner()
        runner.backup.side_effect = OSError('disk full')
        self.execute(runner)
        self.assertEqual([call.args[0] for call in runner.control.call_args_list], ['stop', 'start'])
        runner.command.assert_not_called()
        self.assertFalse((self.data / 'active.json').exists())
        self.assertFalse((self.data / 'maintenance.json').exists())
        self.assertEqual(runner.report.call_args.args[3], '')

    def test_migration_failure_is_durable_and_never_restarts_old_code(self):
        runner = self.runner()
        runner.command.side_effect = RuntimeError('migration failed')
        self.execute(runner)
        self.assertEqual([call.args[0] for call in runner.control.call_args_list], ['stop', 'stop'])
        self.assertEqual(runtime.journal()['phase'], 'blocked')
        self.assertFalse((self.data / 'active.json').exists())
        self.assertIn('/backup', runner.report.call_args.args[3])

    def test_success_switches_only_after_backup_and_migration(self):
        runner = self.runner()
        events = []
        runner.backup.side_effect = lambda *_: events.append('backup')
        runner.command.side_effect = lambda argv, *_, **__: events.append(argv[2])
        self.execute(runner)
        self.assertEqual(events, ['backup', 'migrate', 'init_system'])
        self.assertEqual(runtime.selected()[0], self.target / 'backend')
        self.assertEqual(runner.report.call_args.args[1], 'succeeded')
        self.assertFalse((self.data / 'maintenance.json').exists())
        self.assertNotIn('inflight', json.loads(runner.path.read_text()))

    def test_backup_configuration_is_private_and_token_not_in_cli(self):
        runner = self.runner()
        runner.config = self.data / 'config.json'
        runner.config.write_text('{"SECRET_KEY":"private"}')
        uploads = self.data / 'uploads'
        uploads.mkdir()
        (uploads / 'attachment.txt').write_text('preserve')
        output = self.data / 'backup'
        output.mkdir()
        runner.command.side_effect = lambda argv, *_args, **_kw: Path(argv[-1]).write_bytes(b'database')
        # Exercise the real backup method, not the execute-test mock.
        with patch.dict(os.environ, DB_HOST='postgres', DB_NAME='test', DB_USER='test',
                        DB_PASSWORD='private-db', MEDIA_ROOT=str(uploads)):
            ota.ContainerRunner.backup(runner, output, Mock())
        self.assertNotIn('private-db', str(runner.command.call_args.args))
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertEqual(set(manifest['sha256']), {'database.dump', 'uploads.tar', 'config.json'})


if __name__ == '__main__':
    unittest.main()
