import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
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
        self.config = {'architecture': 'amd64', 'os': 'linux', 'rootfs': {'type': 'layers', 'diff_ids': []}}
        self.files = {}
        self.image_id = self.blob(self.config)
        self.manifest_id = self.blob({'schemaVersion': 2, 'config': {'digest': self.image_id}, 'layers': []})
        self.index = {'schemaVersion': 2, 'manifests': [{'digest': self.manifest_id}]}
        self.index_id = self.blob(self.index)
        self.files['index.json'] = json.dumps({'schemaVersion': 2, 'manifests': [{'digest': self.index_id}]}).encode()
        self.files['manifest.json'] = json.dumps([{'Config': self.blob_path(self.image_id),
                                                 'RepoTags': [release.REPOSITORY + ':v2.0.0-amd64'], 'Layers': []}]).encode()
        self.data = {'mode': 'docker', 'docker_image': release.REPOSITORY + '@sha256:' + 'a' * 64,
                     'docker_archives': {'amd64': {'image_id': self.image_id}}}
        self.write_archive()

    @staticmethod
    def blob_path(digest):
        return 'blobs/sha256/' + digest.removeprefix('sha256:')

    def blob(self, value):
        content = json.dumps(value).encode()
        digest = 'sha256:' + hashlib.sha256(content).hexdigest()
        self.files[self.blob_path(digest)] = content
        return digest

    def write_archive(self):
        with tarfile.open(self.image, 'w:gz') as archive:
            for name, content in self.files.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
        self.data['docker_archives']['amd64']['sha256'] = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.save()

    def save(self):
        (self.root / 'INSTALL-MANIFEST.json').write_text(json.dumps(self.data))

    def test_archive_install_does_not_pull_or_build(self):
        with patch.object(release.subprocess, 'check_output', side_effect=['x86_64', self.image_id + ' linux amd64']), \
                patch.object(release.subprocess, 'run') as run:
            self.assertEqual(release.prepare_docker(self.root), self.image_id)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][:2], ['docker', 'load'])

    def prepare_with_store(self, available, arch='amd64'):
        def inspect(command, **kwargs):
            if command[:2] == ['docker', 'info']:
                return arch
            self.assertEqual(command[:3], ['docker', 'image', 'inspect'])
            if command[3] not in available:
                raise subprocess.CalledProcessError(1, command, stderr='No such image')
            return available[command[3]]
        with patch.object(release.subprocess, 'check_output', side_effect=inspect) as check, \
                patch.object(release.subprocess, 'run') as run:
            try:
                return release.prepare_docker(self.root)
            finally:
                run.assert_called_once_with(['docker', 'load', '-i', str(self.image)], check=True)
                for call in check.call_args_list[1:]:
                    self.assertRegex(call.args[0][3], r'^sha256:[a-f0-9]{64}$')

    def test_classic_export_loads_into_containerd_by_manifest_or_index(self):
        for identity in (self.manifest_id, self.index_id):
            with self.subTest(identity=identity):
                self.assertEqual(self.prepare_with_store({identity: identity + ' linux amd64'}), identity)

    def test_containerd_export_loads_into_classic_by_config(self):
        for identity in (self.manifest_id, self.index_id):
            with self.subTest(identity=identity):
                self.data['docker_archives']['amd64']['image_id'] = identity
                self.save()
                self.assertEqual(self.prepare_with_store({self.image_id: self.image_id + ' linux amd64'}), self.image_id)

    def test_legacy_docker_archive_still_loads_into_classic_store(self):
        self.files.pop('index.json')
        legacy_name = self.image_id.removeprefix('sha256:') + '.json'
        self.files[legacy_name] = self.files.pop(self.blob_path(self.image_id))
        self.files['manifest.json'] = json.dumps([{'Config': legacy_name, 'RepoTags': [], 'Layers': []}]).encode()
        self.write_archive()
        self.assertEqual(self.prepare_with_store({self.image_id: self.image_id + ' linux amd64'}), self.image_id)

    def test_arm64_docker_architecture_alias(self):
        arm_config = {**self.config, 'architecture': 'arm64'}
        arm_id = self.blob(arm_config)
        self.files['manifest.json'] = json.dumps([{'Config': self.blob_path(arm_id)}]).encode()
        self.files.pop('index.json')
        self.data['docker_archives']['amd64']['image_id'] = arm_id
        self.write_archive()
        self.image = self.image.rename(self.image.with_name('arm64.tar.gz'))
        self.data['docker_archives']['arm64'] = self.data['docker_archives'].pop('amd64')
        self.save()
        self.assertEqual(self.prepare_with_store({arm_id: arm_id + ' linux arm64'}, arch='aarch64'), arm_id)

    def test_missing_other_platforms_and_attestations_are_not_candidates(self):
        self.index['manifests'].extend([
            {'digest': 'sha256:' + 'c' * 64, 'platform': {'os': 'linux', 'architecture': 'arm64'}},
            {'digest': 'sha256:' + 'd' * 64, 'platform': {'os': 'unknown', 'architecture': 'unknown'}},
        ])
        index_id = self.blob(self.index)
        self.files['index.json'] = json.dumps({'manifests': [{'digest': index_id}]}).encode()
        self.write_archive()
        self.assertEqual(set(release.archive_image_ids(self.image, self.image_id, 'amd64')),
                         {self.image_id, self.manifest_id, index_id})

    def test_unrelated_expected_image_is_rejected_before_load(self):
        self.data['docker_archives']['amd64']['image_id'] = 'sha256:' + 'f' * 64
        self.save()
        with patch.object(release.subprocess, 'check_output', return_value='amd64'), \
                patch.object(release.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, '身份或架构不符'):
                release.prepare_docker(self.root)
        run.assert_not_called()

    def test_wrong_archive_architecture_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '身份或架构不符'):
            release.archive_image_ids(self.image, self.image_id, 'arm64')

    def test_wrong_loaded_identity_or_architecture_is_rejected(self):
        for result in ('sha256:' + 'f' * 64 + ' linux amd64', self.image_id + ' linux arm64', 'invalid'):
            with self.subTest(result=result), self.assertRaisesRegex(ValueError, '身份或架构不符'):
                self.prepare_with_store({self.image_id: result})

    def test_no_resolvable_identity_never_falls_back_to_tag_pull_or_build(self):
        with self.assertRaisesRegex(ValueError, '未找到经校验的镜像'):
            self.prepare_with_store({})

    def test_corrupted_descriptor_is_rejected_before_load(self):
        self.files[self.blob_path(self.manifest_id)] = b'{}'
        self.write_archive()
        with patch.object(release.subprocess, 'check_output', return_value='amd64'), \
                patch.object(release.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, '描述符校验失败'):
                release.prepare_docker(self.root)
        run.assert_not_called()

    def test_corrupted_config_is_rejected(self):
        self.files[self.blob_path(self.image_id)] = json.dumps({**self.config, 'config': {'Cmd': ['wrong']}}).encode()
        self.write_archive()
        with self.assertRaisesRegex(ValueError, '配置校验失败'):
            release.archive_image_ids(self.image, self.image_id, 'amd64')

    def test_oci_layout_must_actually_reference_the_expected_config(self):
        unrelated = self.blob({'schemaVersion': 2, 'config': {'digest': 'sha256:' + 'f' * 64}})
        self.files['index.json'] = json.dumps({'manifests': [{'digest': unrelated}]}).encode()
        self.write_archive()
        with self.assertRaisesRegex(ValueError, '身份或架构不符'):
            release.archive_image_ids(self.image, self.image_id, 'amd64')

    def test_ambiguous_same_platform_index_cannot_select_another_image(self):
        other_config = self.blob({**self.config, 'config': {'Cmd': ['other']}})
        other_manifest = self.blob({'schemaVersion': 2, 'config': {'digest': other_config}})
        entries = json.loads(self.files['manifest.json'])
        entries.append({'Config': self.blob_path(other_config)})
        self.files['manifest.json'] = json.dumps(entries).encode()
        self.index['manifests'].append({'digest': other_manifest})
        ambiguous_index = self.blob(self.index)
        self.files['index.json'] = json.dumps({'manifests': [{'digest': ambiguous_index}]}).encode()
        self.write_archive()
        self.assertEqual(set(release.archive_image_ids(self.image, self.image_id, 'amd64')),
                         {self.image_id, self.manifest_id})
        with self.assertRaisesRegex(ValueError, '身份或架构不符'):
            release.archive_image_ids(self.image, ambiguous_index, 'amd64')

    def test_duplicate_metadata_and_symlinks_are_rejected(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                with tarfile.open(self.image, 'w:gz') as archive:
                    entry = tarfile.TarInfo('manifest.json')
                    entry.type = tarfile.SYMTYPE
                    entry.linkname = '/outside.json'
                    archive.addfile(entry)
                    if duplicate:
                        archive.addfile(entry)
                with self.assertRaises(ValueError):
                    release.archive_image_ids(self.image, self.image_id, 'amd64')

    def test_metadata_is_never_extracted_and_unsafe_config_paths_are_rejected(self):
        self.files['manifest.json'] = b'[{"Config":"../outside.json"}]'
        self.write_archive()
        with self.assertRaisesRegex(ValueError, '配置路径非法'):
            release.archive_image_ids(self.image, self.image_id, 'amd64')
        self.assertFalse((self.root / 'blobs').exists())

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
