import importlib.util
import io
import json
import plistlib
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('ota_service', SCRIPTS / 'ota_service.py')
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='erp ota service ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / '.env.lean'
        self.config.write_text('LEAN_OTA_AGENT_TOKEN=' + 'a' * 64 + '\nLEAN_HTTP_PORT=18360\n')
        self.state = self.root / 'service'

    def test_install_waits_for_real_heartbeat_and_preserves_secrets(self):
        def register(directory):
            service.private_json(directory / 'heartbeat.json', {'seen': time.time()})
        with patch.object(service, 'register', side_effect=register) as call:
            service.install('docker', self.root, self.config, directory=self.state)
            service.install('docker', self.root, self.config, directory=self.state)
        self.assertEqual(call.call_count, 1)
        saved = (self.state / 'service.json').read_text()
        self.assertNotIn('a' * 64, saved)
        self.assertEqual(json.loads(saved)['url'], 'http://127.0.0.1:18360')

    def test_old_or_future_heartbeat_does_not_claim_connection(self):
        self.state.mkdir()
        for stamp in (time.time() - 60, time.time() + 60):
            service.private_json(self.state / 'heartbeat.json', {'seen': stamp})
            self.assertFalse(service.fresh(self.state))

    def test_install_chinese_output_on_windows_redirected_console(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding='cp1252')
        self.addCleanup(stream.close)
        def register(directory):
            service.private_json(directory / 'heartbeat.json', {'seen': time.time()})
        with patch.object(service, 'register', side_effect=register), patch.object(service.sys, 'stdout', stream):
            service.install('docker', self.root, self.config, directory=self.state)
        self.assertIn('执行器已自动启动并连接', buffer.getvalue().decode('utf-8'))

    def test_missing_token_does_not_register_service(self):
        self.config.write_text('LEAN_HTTP_PORT=18360\n')
        with patch.object(service, 'register') as register:
            with self.assertRaisesRegex(ValueError, '密钥'):
                service.install('docker', self.root, self.config, directory=self.state)
        register.assert_not_called()

    def test_registration_without_connection_fails_install(self):
        with patch.object(service, 'register'), patch.object(service.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, '未连接'):
                service.install('docker', self.root, self.config, directory=self.state)

    def test_unfinished_upgrade_is_not_interrupted(self):
        self.state.mkdir()
        service.private_json(self.state / 'state.json', {'inflight': {'id': 1}})
        with patch.object(service, 'register') as register:
            with self.assertRaisesRegex(ValueError, '未完成升级'):
                service.install('docker', self.root, self.config, directory=self.state)
        register.assert_not_called()

    def test_state_directories_are_deployment_specific(self):
        self.assertNotEqual(service.location('docker', self.config), service.location('native', self.config))
        self.assertNotEqual(service.location('docker', self.config), service.location('docker', self.root / 'other.env'))
        self.assertEqual(service.location('docker', self.config, 'same-project'),
                         service.location('docker', self.root / 'upgrade.env', 'same-project'))

    def test_systemd_arguments_escape_spaces_quotes_and_specifiers(self):
        unit = service.unit(['/path with spaces/python', '/path/100%/a"b.py'], self.state)
        self.assertIn('"/path with spaces/python"', unit)
        self.assertIn('100%%/a\\"b.py', unit)
        self.assertIn('Restart=always', unit)

    def test_supervisor_uses_updated_release_and_configuration(self):
        self.state.mkdir()
        service.private_json(self.state / 'service.json', {
            'mode': 'docker', 'root': '/old', 'config': '/old.env', 'url': 'http://127.0.0.1:18360', 'path': '/bin'})
        service.private_json(self.state / 'state.json', {'root': '/new', 'config': '/new.env'})
        with patch.object(service.subprocess, 'run') as run, patch.object(service.time, 'sleep', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                service.supervise(self.state)
        args = run.call_args.args[0]
        self.assertIn(str(Path('/new/scripts/ota_runner.py')), args)
        self.assertIn('/new.env', args)
        self.assertEqual(run.call_args.kwargs['env']['ATM_ERP_OTA_MANAGED'], '1')

    def test_macos_registers_real_keepalive_with_separate_arguments(self):
        with patch.object(service.sys, 'platform', 'darwin'), patch.object(service.os, 'getuid', return_value=501, create=True), \
                patch.object(service.Path, 'home', return_value=self.root), patch.object(service.subprocess, 'run') as run:
            service.register(self.state)
        plist = next((self.root / 'Library/LaunchAgents').glob('*.plist'))
        value = plistlib.loads(plist.read_bytes())
        self.assertTrue(value['RunAtLoad'])
        self.assertTrue(value['KeepAlive'])
        self.assertIn(str(self.state), value['ProgramArguments'])
        self.assertEqual(run.call_args.args[0][1], 'kickstart')

    def test_windows_task_recovers_without_password_or_time_limit(self):
        self.state.mkdir()
        with patch.object(service.sys, 'platform', 'win32'), patch.object(service.subprocess, 'check_output', return_value='ERP\\user'), \
                patch.object(service.subprocess, 'run') as run:
            service.register(self.state)
        import xml.etree.ElementTree as ET
        tree = ET.parse(self.state / 'service.xml')
        def value(tag):
            return tree.find('.//{*}' + tag).text
        self.assertEqual(value('Interval'), 'PT1M')
        self.assertEqual(value('MultipleInstancesPolicy'), 'IgnoreNew')
        self.assertEqual(value('ExecutionTimeLimit'), 'PT0S')
        self.assertEqual(value('LogonType'), 'InteractiveToken')
        self.assertEqual(run.call_args.args[0][1], '/Run')

    def test_linux_user_service_is_enabled_and_survives_logout(self):
        with patch.object(service.sys, 'platform', 'linux'), patch.object(service.os, 'getuid', return_value=501, create=True), \
                patch.object(service.Path, 'home', return_value=self.root), patch.object(service.subprocess, 'run') as run:
            service.register(self.state)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertTrue(any('enable' in args and '--now' in args and '--user' in args for args in commands))
        self.assertEqual(commands[-1], ['loginctl', 'enable-linger', '501'])


if __name__ == '__main__':
    unittest.main()
