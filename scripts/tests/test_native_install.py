import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("native", Path(__file__).parents[1] / "native_install.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


class NativeInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean native ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / "config.json"
        with patch.object(native, "ROOT", self.root):
            native.create_config(self.path)
        self.config = json.loads(self.path.read_text(encoding="utf-8"))
        self.config["DB_PASSWORD"] = "test-password"

    def save(self):
        self.path.write_text(json.dumps(self.config), encoding="utf-8")

    def test_configuration_is_private_and_never_overwritten(self):
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            native.create_config(self.path)
        self.assertEqual(before, self.path.read_bytes())
        if native.os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.config["APP_ENVIRONMENT"], "production")

    def test_rejects_missing_password_development_and_invalid_ports(self):
        for key, value in (("DB_PASSWORD", "CHANGE_ME"), ("APP_ENVIRONMENT", "development"),
                           ("HTTP_PORT", True), ("HTTP_PORT", 70000),
                           ("BIND_ADDRESS", "0.0.0.0; malicious"), ("DATA_DIR", "relative")):
            with self.subTest(key=key, value=value):
                original = self.config[key]
                self.config[key] = value
                self.save()
                with self.assertRaises(ValueError):
                    native.load_config(self.path)
                self.config[key] = original

    def test_environment_forces_release_settings(self):
        with patch.dict(native.os.environ, {"DEBUG": "true", "APP_ENVIRONMENT": "development"}):
            env = native.environment(self.config, self.root)
        self.assertEqual(env["DEBUG"], "false")
        self.assertEqual(env["APP_ENVIRONMENT"], "production")
        self.assertEqual(env["MEDIA_ROOT"], str(self.root / "uploads"))

    def test_nginx_keeps_uploads_private_and_quotes_spaces(self):
        result = native.nginx_config(self.config, self.root)
        self.assertIn('root "', result)
        self.assertIn("location / { return 404; }", result)
        self.assertNotIn("uploads", result)
        self.assertIn("proxy_pass http://127.0.0.1:18001", result)
        with self.assertRaises(ValueError):
            native.quote_path(self.root / '$bad')

    def test_missing_frontend_does_not_modify_database(self):
        with patch.object(native, "ROOT", self.root), patch.object(native, "nginx_path", return_value="nginx"), \
                patch.object(native, "available_ports"), patch.object(native, "run") as run:
            with self.assertRaisesRegex(ValueError, "前端"):
                native.install(self.config, self.root / "data")
            run.assert_not_called()

    def test_dependency_failure_stops_before_migration(self):
        (self.root / "frontend/dist").mkdir(parents=True)
        (self.root / "frontend/dist/index.html").write_text("test")
        with patch.object(native, "ROOT", self.root), patch.object(native, "nginx_path", return_value="nginx"), \
                patch.object(native, "available_ports"), patch.object(native, "run") as run, \
                patch.object(native, "check_services", side_effect=RuntimeError("unavailable")):
            with self.assertRaises(RuntimeError):
                native.install(self.config, self.root / "data")
            self.assertFalse(any("manage.py" in str(call) for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
