import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('native_service', Path(__file__).parents[1] / 'native_service.py')
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)


class NativeServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name).resolve()

    def test_units_boot_and_forward_signals_to_launcher(self):
        system = service.unit(self.data, '/python with space', True)
        self.assertIn('WantedBy=multi-user.target', system)
        self.assertIn('Restart=on-failure', system)
        self.assertIn('"/python with space"', system)
        self.assertIn('WantedBy=default.target', service.unit(self.data, '/python', False))

    def test_forward_install_updates_stable_service_launcher(self):
        with patch.object(service.os, 'getuid', return_value=501, create=True):
            service.update(self.data / 'old', self.data / 'config.json', self.data)
            service.update(self.data / 'new', self.data / 'config.json', self.data)
        with patch.object(service.os, 'execv') as execute:
            service.launch(self.data)
        args = execute.call_args.args[1]
        self.assertIn(str(self.data / 'new/scripts/native_install.py'), args)
        self.assertIn('--foreground', args)

    def test_control_uses_original_account_and_does_not_spawn_foreground_copy(self):
        with patch.object(service.os, 'getuid', return_value=501, create=True):
            service.update(self.data, self.data / 'config.json', self.data)
            with patch.object(service.sys, 'platform', 'linux'), patch.object(service.subprocess, 'run') as run:
                service.control(self.data, 'stop')
                self.assertEqual(run.call_args.args[0], ['systemctl', '--user', 'stop', service.name(self.data)])
        with patch.object(service.sys, 'platform', 'linux'), patch.object(service.os, 'getuid', return_value=0, create=True):
            with self.assertRaisesRegex(ValueError, '原安装账户'):
                service.control(self.data, 'start')

    def test_user_service_registration_and_running_guard(self):
        (self.data / 'nginx.conf').touch()
        with patch.object(service.sys, 'platform', 'linux'), patch.object(service.os, 'getuid', return_value=501, create=True), \
                patch.object(service.Path, 'home', return_value=self.data), patch.object(service.subprocess, 'run') as run:
            service.register(self.data, self.data / 'config.json', self.data)
            self.assertTrue(service.managed(self.data))
            self.assertTrue((self.data / 'native_service.py').exists())
            self.assertIn('enable', run.call_args.args[0])
            (self.data / 'native-runtime.json').write_text(json.dumps({'seen': 1}))
            with self.assertRaisesRegex(ValueError, '先停止'):
                service.register(self.data, self.data / 'config.json', self.data)
