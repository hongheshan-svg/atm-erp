import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('network_check', Path(__file__).parents[1] / 'network_check.py')
network = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(network)


class NetworkCheckTests(unittest.TestCase):
    def config(self, **values):
        temp = tempfile.NamedTemporaryFile('w', suffix='.env', delete=False, encoding='utf-8')
        self.addCleanup(lambda: Path(temp.name).unlink(missing_ok=True))
        temp.write('LEAN_PROJECT_NAME=atm-erp-lean\n')
        for name, value in values.items():
            temp.write(f'{name}={value}\n')
        temp.close()
        return temp.name

    def test_published_port_without_matching_host_is_reported(self):
        found = network.warnings('0.0.0.0', 'localhost,127.0.0.1')
        self.assertEqual(len(found), 1)
        self.assertIn('HTTP 400', found[0])
        self.assertIn('LEAN_ALLOWED_HOSTS', found[0])

    def test_allowed_host_without_published_port_is_reported(self):
        found = network.warnings('127.0.0.1', 'localhost,127.0.0.1,192.168.3.105')
        self.assertEqual(len(found), 1)
        self.assertIn('192.168.3.105', found[0])
        self.assertIn('LEAN_BIND_ADDRESS', found[0])

    def test_consistent_configurations_stay_silent(self):
        self.assertEqual(network.warnings('127.0.0.1', 'localhost,127.0.0.1'), [])
        self.assertEqual(network.warnings('0.0.0.0', 'localhost,127.0.0.1,erp.example.com'), [])
        self.assertEqual(network.warnings('192.168.3.105', '192.168.3.105'), [])
        # A wildcard already accepts every host, so the published port is not a mismatch.
        self.assertEqual(network.warnings('0.0.0.0', '*'), [])

    def test_loopback_spellings_all_count_as_local(self):
        for address in ('127.0.0.1', '127.0.1.1', 'localhost', '::1', '[::1]'):
            self.assertTrue(network.local_only(address), address)
        for address in ('0.0.0.0', '192.168.3.105', '10.0.0.7', 'erp.example.com', '*'):
            self.assertFalse(network.local_only(address), address)

    def test_defaults_apply_when_the_env_file_omits_the_keys(self):
        self.assertEqual(network.inspect(self.config()), [])
        self.assertEqual(len(network.inspect(self.config(LEAN_BIND_ADDRESS='0.0.0.0'))), 1)

    def test_last_assignment_wins_like_compose(self):
        path = self.config(LEAN_BIND_ADDRESS='127.0.0.1', LEAN_ALLOWED_HOSTS='localhost,127.0.0.1')
        Path(path).write_text(Path(path).read_text() + 'LEAN_BIND_ADDRESS=0.0.0.0\n', encoding='utf-8')
        self.assertEqual(len(network.inspect(path)), 1)

    def test_missing_config_never_fails_the_install(self):
        with patch.object(sys, 'argv', ['network_check.py', '--config', '/nonexistent/.env.lean']):
            self.assertEqual(network.main(), 0)

    def test_warning_goes_to_stderr_and_still_exits_zero(self):
        path = self.config(LEAN_BIND_ADDRESS='0.0.0.0')
        stderr = io.StringIO()
        with patch.object(sys, 'argv', ['network_check.py', '--config', path]), redirect_stderr(stderr):
            self.assertEqual(network.main(), 0)
        self.assertIn('注意：', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
