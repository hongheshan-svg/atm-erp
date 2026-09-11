import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('release_install', Path(__file__).parents[1] / 'release_install.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'images').mkdir()
        self.image = self.root / 'images/amd64.tar.gz'
        self.image.write_bytes(b'verified image archive')
        self.image_id = 'sha256:' + 'b' * 64
        self.data = {'mode': 'docker', 'docker_image': release.REPOSITORY + '@sha256:' + 'a' * 64,
                     'docker_archives': {'amd64': {'image_id': self.image_id, 'sha256': hashlib.sha256(self.image.read_bytes()).hexdigest()}}}
        self.save()

    def save(self):
        (self.root / 'INSTALL-MANIFEST.json').write_text(json.dumps(self.data))

    def test_archive_install_does_not_pull_or_build(self):
        with patch.object(release.subprocess, 'check_output', side_effect=['x86_64', self.image_id]), \
                patch.object(release.subprocess, 'run') as run:
            self.assertEqual(release.prepare_docker(self.root), self.image_id)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][:2], ['docker', 'load'])

    def test_tampered_archive_fails_before_import(self):
        self.image.write_bytes(b'tampered')
        with patch.object(release.subprocess, 'check_output', return_value='amd64'), patch.object(release.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, '校验失败'):
                release.prepare_docker(self.root)
        run.assert_not_called()

    def test_no_archive_pulls_only_digest(self):
        self.image.unlink()
        with patch.object(release.subprocess, 'check_output', return_value='amd64'), patch.object(release.subprocess, 'run') as run:
            self.assertEqual(release.prepare_docker(self.root), self.data['docker_image'])
        self.assertEqual(run.call_args.args[0], ['docker', 'pull', self.data['docker_image']])

    def test_mutable_or_foreign_image_is_rejected(self):
        for image in ('ghcr.io/hongheshan-svg/atm-erp:latest', 'ghcr.io/other/erp@sha256:' + 'a' * 64):
            self.data['docker_image'] = image
            self.save()
            with self.assertRaises(ValueError):
                release.docker_image(self.root)

    def test_missing_prebuilt_artifact_never_falls_back_to_compile(self):
        self.data = {'mode': 'docker'}
        self.save()
        with self.assertRaises(ValueError):
            release.prepare_docker(self.root)
        with self.assertRaises(ValueError):
            release.native_dependencies(self.root)

    def test_image_update_keeps_secrets_and_deployment(self):
        config = self.root / '.env'
        config.write_text('LEAN_PROJECT_NAME=keep\nLEAN_DB_PASSWORD=keep-secret\nLEAN_IMAGE=old\n')
        release.set_image(config, self.image_id)
        text = config.read_text()
        self.assertIn('LEAN_DB_PASSWORD=keep-secret', text)
        self.assertIn('LEAN_PROJECT_NAME=keep', text)
        self.assertEqual(text.count('LEAN_IMAGE='), 1)


if __name__ == '__main__':
    unittest.main()
