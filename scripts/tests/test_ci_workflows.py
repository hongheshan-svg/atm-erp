import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.ci.impact import plan, version_only_paths
from scripts.ci.publish_release import verify
from scripts.ci.release_gate import preflight, release_scope, reusable_run
from scripts.ci.run_selected import command
from scripts.ci.select_suites import SUITES, select


class RoutingTests(unittest.TestCase):
    def test_documentation_and_deleted_paths(self):
        self.assertEqual(select(['README.md', 'docs/old-guide.md']), set())
        with self.assertRaises(ValueError):
            select(['frontend/src/removed.vue'])

    def test_backend_and_migration_changes(self):
        self.assertEqual(select(['backend/apps/business/services/supply.py']), {'fast', 'browser'})
        with self.assertRaises(ValueError):
            select(['backend/apps/business/migrations/0001_initial.py'])

    def test_pr_changes_do_not_implicitly_run_full_validation(self):
        for path in (
            'backend/apps/core/version.py',
            '.github/workflows/ci.yml',
            'scripts/ci/release_gate.py',
        ):
            self.assertEqual(select([path]), {'fast'}, path)
        for path in ('frontend/package-lock.json', 'backend/requirements.txt', 'unknown.file'):
            with self.assertRaises(ValueError):
                select([path])

    def test_module_scope_has_direct_consumers_but_not_full_chain(self):
        scope = plan(['backend/apps/business/services/supply.py'])
        self.assertIn('apps.business.tests.test_inventory', scope['backend_targets'])
        self.assertIn('apps.business.tests.test_budgets', scope['backend_targets'])
        self.assertNotIn('apps.business.tests.test_bank_import', scope['backend_targets'])
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])
        self.assertFalse(scope['ota'])
        self.assertFalse(scope['installers'])

    def test_ota_requires_real_upgrade_checks_without_sales_chain(self):
        scope = plan(['scripts/container_ota.py'])
        self.assertTrue(scope['ota'])
        self.assertTrue(scope['installers'])
        self.assertEqual(scope['backend_targets'], ['apps.core.tests.test_ota'])
        self.assertEqual(scope['browser_specs'], ['e2e/system-upgrade.spec.ts'])

    def test_shared_scope_explicit_and_fingerprint_changes_with_coverage(self):
        first = plan(['frontend/src/utils/money.ts'], modules=('finance',))
        second = plan(['frontend/src/utils/money.ts'], modules=('finance', 'purchases'))
        self.assertIn('src/utils/money.spec.ts', first['frontend_tests'])
        self.assertNotEqual(first['fingerprint'], second['fingerprint'])
        self.assertEqual(first, plan(['frontend/src/utils/money.ts'], modules=('finance',)))
        with self.assertRaises(ValueError):
            plan([], modules=('typo',))

    def test_empty_or_malicious_selection_cannot_run_all_or_shell(self):
        for kind in ('backend', 'frontend', 'browser'):
            self.assertIsNone(command(kind, []))
            with self.assertRaises(ValueError):
                command(kind, ['--help; echo unsafe'])
        self.assertEqual(command('backend', ['apps.core.tests.test_ota'])[1][2], 'test')

    def test_full_chain_requires_explicit_full_even_if_changed(self):
        with self.assertRaises(ValueError):
            plan(['frontend/e2e/full-chain.spec.ts'])
        self.assertIn('e2e/full-chain.spec.ts', plan([], full=True)['browser_specs'])

    def test_version_only_change_is_not_confused_with_dependency_update(self):
        def blobs(ref, _):
            return json.dumps({'version': '1.0.0' if ref == 'old' else '1.0.1', 'dependencies': {'vue': '3'}})

        paths = ['frontend/package.json']
        only = version_only_paths('old', 'new', paths, blobs)
        self.assertEqual(only, set(paths))
        scope = plan(paths, version_only=only)
        self.assertTrue(scope['frontend'])
        self.assertEqual(scope['browser_specs'], [])
        changed = version_only_paths('old', 'new', paths, lambda ref, _: json.dumps({'dependencies': {'vue': ref}}))
        self.assertFalse(changed)

    def test_changed_workflow_and_wheel_delivery_are_exercised(self):
        self.assertTrue(plan(['.github/workflows/ci-ota.yml'])['ota'])
        self.assertTrue(plan(['.github/workflows/ci-browser.yml'])['browser_specs'])
        self.assertTrue(plan(['scripts/ci/build_native_wheels.py'])['installers'])
        scope = plan(['.github/workflows/ci-fast.yml'])
        self.assertTrue(scope['backend'])
        self.assertTrue(scope['frontend'])

    def test_module_map_references_real_registered_tests(self):
        from scripts.ci.backend_test_matrix import MODULE_TESTS, TARGETS, module_targets, validate_coverage

        validate_coverage()
        names = {target.rsplit('.test_', 1)[-1] for group in TARGETS.values() for target in group}
        for module, cases in MODULE_TESTS.items():
            self.assertTrue(set(cases) <= names, module)
            self.assertTrue(module_targets([module]), module)

    def test_explicit_full_validation_keeps_every_release_suite(self):
        self.assertEqual(select([], 'full'), set(SUITES))
        self.assertEqual(select(['README.md'], 'full'), set(SUITES))

    def test_custom_combination_and_standalone(self):
        self.assertEqual(select([], 'custom', ['browser', 'ota']), {'browser', 'ota'})
        for suite in SUITES:
            self.assertEqual(select([], suite), {suite})
        with self.assertRaises(ValueError):
            select([], 'custom')
        with self.assertRaises(ValueError):
            select([], 'unsafe')


class ReleaseEvidenceTests(unittest.TestCase):
    def test_release_baseline_is_previous_stable_and_uses_whole_release_diff(self):
        def fake_git(*args):
            if args[0] == 'tag':
                return 'v3.0.0\nv2.0.0\nv1.9.0-rc1\nv1.8.8\nv1.8.7'
            self.assertEqual(args, ('diff', '--name-only', '-z', 'v1.8.8', 'commit'))
            return 'backend/apps/business/services/supply.py\0'

        with patch('scripts.ci.release_gate.git', side_effect=fake_git):
            base, scope = release_scope('commit', 'v2.0.0')
        self.assertEqual(base, 'v1.8.8')
        self.assertEqual(scope['modules'], ['purchases'])

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

    def test_scoped_evidence_requires_identical_plan(self):
        def jobs(_):
            return [{'name': 'Scoped validation (abc coverage1)', 'conclusion': 'success'}]

        self.assertEqual(reusable_run([self.run], 'owner/erp', 'abc', jobs, 'coverage1'), 42)
        self.assertIsNone(reusable_run([self.run], 'owner/erp', 'abc', jobs, 'coverage2'))
        self.assertIsNone(reusable_run([self.run], 'owner/erp', 'different', jobs, 'coverage1'))

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
                                    'docker_archives': {
                                        arch: {'sha256': hashlib.sha256(b'image').hexdigest()}
                                        for arch in ('amd64', 'arm64')
                                    },
                                    'native_prebuilt': True,
                                    'native_architectures': ['x86_64'],
                                }
                            ),
                        )
                        if mode == 'docker':
                            for arch in ('amd64', 'arm64'):
                                archive.writestr(path.stem + '/images/' + arch + '.tar.gz', b'image')
                        else:
                            archive.writestr(
                                path.stem + '/wheelhouse/x86_64/SHA256.json',
                                json.dumps({'requirements.lock': hashlib.sha256(b'lock').hexdigest()}),
                            )
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
            patch('scripts.ci.release_gate.release_scope', return_value=('v1.9.9', {'fingerprint': 'coverage1'})),
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
