import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.ci.publish_release import verify
from scripts.ci.release_gate import preflight, reusable_run
from scripts.ci.select_suites import SUITES, select


class RoutingTests(unittest.TestCase):
    def test_documentation_and_deleted_paths(self):
        self.assertEqual(select(['README.md', 'docs/old-guide.md']), set())
        self.assertEqual(select(['frontend/src/removed.vue']), {'fast', 'browser'})

    def test_backend_and_migration_changes(self):
        self.assertEqual(select(['backend/apps/business/services/supply.py']), {'fast', 'browser'})
        self.assertEqual(select(['backend/apps/business/migrations/0001_initial.py']), {'fast', 'browser', 'ota'})

    def test_release_and_unknown_changes_are_conservative(self):
        for path in (
            'backend/apps/core/version.py',
            'frontend/package-lock.json',
            '.github/workflows/ci.yml',
            'scripts/ci/release_gate.py',
            'backend/requirements.txt',
            'docker/app/Dockerfile',
            'unknown.file',
        ):
            self.assertEqual(select([path]), set(SUITES), path)

    def test_custom_combination_and_standalone(self):
        self.assertEqual(select([], 'custom', ['browser', 'ota']), {'browser', 'ota'})
        for suite in SUITES:
            self.assertEqual(select([], suite), {suite})
        with self.assertRaises(ValueError):
            select([], 'custom')
        with self.assertRaises(ValueError):
            select([], 'unsafe')


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.run = {
            'id': 42,
            'event': 'pull_request',
            'conclusion': 'success',
            'head_repository': {'full_name': 'owner/erp'},
        }
        self.jobs = lambda run: [{'name': 'Full validation (abc)', 'conclusion': 'success'}]

    def test_reuse_requires_exact_tree_and_complete_suite(self):
        self.assertEqual(reusable_run([self.run], 'owner/erp', 'abc', self.jobs), 42)
        self.assertIsNone(reusable_run([self.run], 'owner/erp', 'different', self.jobs))
        self.assertIsNone(
            reusable_run([self.run], 'owner/erp', 'abc', lambda _: [{'name': 'CI gate', 'conclusion': 'success'}])
        )

    def test_failed_foreign_or_incomplete_evidence_is_rejected(self):
        self.assertIsNone(reusable_run([dict(self.run, conclusion='failure')], 'owner/erp', 'abc', self.jobs))
        self.assertIsNone(reusable_run([self.run], 'other/erp', 'abc', self.jobs))
        self.assertIsNone(
            reusable_run(
                [self.run], 'owner/erp', 'abc', lambda _: [{'name': 'Full validation (abc)', 'conclusion': 'skipped'}]
            )
        )

    def test_six_packages_provenance_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            lines = []
            for platform in ('linux', 'macos', 'windows'):
                for mode in ('docker', 'native'):
                    path = folder / f'atm-erp-v2.0.0-{platform}-{mode}.zip'
                    with zipfile.ZipFile(path, 'w') as archive:
                        archive.writestr(
                            path.stem + '/INSTALL-MANIFEST.json',
                            json.dumps(
                                {
                                    'version': 'v2.0.0',
                                    'source_commit': 'commit',
                                    'installer_commit': 'commit',
                                    'mode': mode,
                                    'docker_image': 'ghcr.io/hongheshan-svg/atm-erp@sha256:' + 'a' * 64,
                                    'docker_archives': {arch: {'sha256': hashlib.sha256(b'image').hexdigest()} for arch in ('amd64', 'arm64')},
                                    'native_prebuilt': True,
                                    'native_architectures': ['x86_64'],
                                }
                            ),
                        )
                        if mode == 'docker':
                            for arch in ('amd64', 'arm64'):
                                archive.writestr(path.stem + '/images/' + arch + '.tar.gz', b'image')
                        else:
                            archive.writestr(path.stem + '/wheelhouse/x86_64/SHA256.json', json.dumps({'requirements.lock': hashlib.sha256(b'lock').hexdigest()}))
                            archive.writestr(path.stem + '/wheelhouse/x86_64/requirements.lock', b'lock')
                    lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
            (folder / 'atm-erp-v2.0.0-SHA256SUMS.txt').write_text('\n'.join(lines) + '\n')
            self.assertEqual(len(verify(folder, 'v2.0.0', 'commit')), 7)
            with self.assertRaises(ValueError):
                verify(folder, 'v2.0.0', 'other-commit')
            path.write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                verify(folder, 'v2.0.0', 'commit')

    def test_preflight_reuses_only_valid_release_evidence(self):
        def git_result(*args):
            if args[0] == 'rev-parse':
                return 'abc' if args[1].endswith('^{tree}') else 'commit'
            if args[1].endswith('version.py'):
                return "VERSION = '2.0.0'"
            if args[1].endswith('.json'):
                return '{"version":"2.0.0"}'
            return '## 📥 Installation\n## 📚 Documentation'

        with (
            patch('scripts.ci.release_gate.git', side_effect=git_result),
            patch('scripts.ci.release_gate.subprocess.run'),
        ):
            with patch(
                'scripts.ci.release_gate.api', side_effect=[[], {'workflow_runs': [self.run]}, {'jobs': self.jobs(42)}]
            ):
                self.assertEqual(preflight('v2.0.0', 'owner/erp')['validate'], 'false')
            with patch('scripts.ci.release_gate.api', return_value=[]):
                self.assertEqual(preflight('v2.0.0', 'owner/erp', force=True)['validate'], 'true')
            with patch('scripts.ci.release_gate.api', return_value=[{'tag_name': 'v2.0.0', 'draft': False}]):
                with self.assertRaises(ValueError):
                    preflight('v2.0.0', 'owner/erp')

    def test_preflight_rejects_unstable_tag_before_git_or_network(self):
        with patch('scripts.ci.release_gate.git') as git, patch('scripts.ci.release_gate.api') as api:
            with self.assertRaises(ValueError):
                preflight('v2.0.0-beta', 'owner/erp')
            git.assert_not_called()
            api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
