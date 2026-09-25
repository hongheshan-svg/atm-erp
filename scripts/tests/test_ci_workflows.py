import hashlib
import json
import re
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.ci.impact import BROWSERS, BUSINESS, FULL_ONLY_BROWSERS, ROOT, SHARED_UI_BROWSERS, plan, version_only_paths
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
        # 迁移属于经过审阅的共享路径，自动覆盖全部业务模块，不再要求手动补跑。
        scope = plan(['backend/apps/business/migrations/0001_initial.py'])
        # 升级流程先备份再迁移，迁移变化同时选择 OTA 升级演练。
        self.assertEqual(scope['modules'], sorted((*BUSINESS, 'ota')))
        self.assertTrue(scope['ota'])
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])

    def test_pr_changes_do_not_implicitly_run_full_validation(self):
        for path in (
            'backend/apps/core/version.py',
            '.github/workflows/ci.yml',
            'scripts/ci/release_gate.py',
        ):
            self.assertEqual(select([path]), {'fast'}, path)
        for path in ('frontend/package-lock.json', 'backend/requirements.txt'):
            scope = plan([path])
            self.assertEqual(scope['modules'], sorted(BUSINESS + (('ota',) if 'requirements' in path else ())), path)
            self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])
        for path in ('unknown.file', 'backend/apps/business/new_module.py', 'frontend/src/components/NewWidget.vue'):
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
        self.assertEqual(scope['browser_specs'], ['e2e/navigation-dialog.spec.ts', 'e2e/system-upgrade.spec.ts'])

    def test_shared_scope_explicit_and_fingerprint_changes_with_coverage(self):
        # 尚未登记映射的新文件仍需显式 modules，覆盖范围不同则计划指纹不同。
        unmapped = ['frontend/src/components/NewWidget.vue']
        first = plan(unmapped, modules=('finance',))
        second = plan(unmapped, modules=('finance', 'purchases'))
        self.assertNotEqual(first['fingerprint'], second['fingerprint'])
        self.assertEqual(first, plan(unmapped, modules=('finance',)))
        self.assertIn('src/utils/money.spec.ts', plan(['frontend/src/utils/money.ts'])['frontend_tests'])
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

    def test_every_registered_test_is_reachable_from_a_module(self):
        from scripts.ci.backend_test_matrix import MODULE_TESTS, TARGETS, module_targets

        registered = {target for group in TARGETS.values() for target in group}
        self.assertEqual(registered - set(module_targets(MODULE_TESTS)), set())
        specs = {path.name.removesuffix('.spec.ts') for path in (ROOT / 'frontend/e2e').glob('*.spec.ts')}
        routed = {name for names in BROWSERS.values() for name in names} | set(SHARED_UI_BROWSERS)
        self.assertEqual(specs - routed, set(FULL_ONLY_BROWSERS))

    def test_every_tracked_source_file_is_classified(self):
        paths = subprocess.check_output(['git', 'ls-files', 'backend', 'frontend'], cwd=ROOT, text=True).split()
        unclassified = []
        for path in paths:
            if path == 'frontend/e2e/full-chain.spec.ts':
                continue  # 完整业务链改动按设计只能通过显式 full 验证
            try:
                plan([path])
            except ValueError:
                unclassified.append(path)
        self.assertEqual(unclassified, [])

    def test_shared_core_change_runs_every_business_module_but_not_full(self):
        scope = plan(['backend/apps/business/services/common.py'])
        self.assertEqual(scope['modules'], sorted(BUSINESS))
        for target in ('apps.business.tests.test_hardening', 'apps.business.tests.test_concurrency'):
            self.assertIn(target, scope['backend_targets'])
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])
        self.assertFalse(scope['ota'] or scope['installers'])

    def test_shared_ui_change_adds_page_level_specs(self):
        scope = plan(['frontend/src/components/ResourcePanel.vue'])
        self.assertEqual(scope['modules'], sorted(BUSINESS))
        for name in SHARED_UI_BROWSERS:
            self.assertIn(f'e2e/{name}.spec.ts', scope['browser_specs'])
        narrow = plan(['frontend/src/components/SupplierMonthly.vue'])
        self.assertEqual(narrow['modules'], ['finance'])
        self.assertNotIn('e2e/ui-concepts.spec.ts', narrow['browser_specs'])

    def test_module_change_runs_its_cross_module_regressions(self):
        scope = plan(['backend/apps/business/services/supply.py'])
        for target in ('hardening', 'concurrency', 'transfers', 'operational_review'):
            self.assertIn(f'apps.business.tests.test_{target}', scope['backend_targets'])
        self.assertIn('e2e/specialist-roles.spec.ts', scope['browser_specs'])

    def test_check_only_configuration_runs_static_checks_without_modules(self):
        scope = plan(['frontend/eslint.config.js', 'backend/pyproject.toml'])
        self.assertEqual(scope['modules'], [])
        self.assertTrue(scope['backend'] and scope['frontend'])
        self.assertEqual(scope['browser_specs'], [])

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

    def test_scoped_evidence_is_never_release_evidence(self):
        def jobs(_):
            return [
                {'name': 'Scoped validation (abc coverage1)', 'conclusion': 'success'},
                {'name': 'CI gate', 'conclusion': 'success'},
            ]

        # 按影响范围通过的记录不含全部后端、单测、安装器与 OTA，即使计划指纹相同也不能作为发版凭据。
        self.assertIsNone(reusable_run([self.run], 'owner/erp', 'abc', jobs, 'coverage1'))

    def test_release_evidence_requires_identical_release_plan(self):
        def jobs(_):
            return [{'name': 'Release validation (abc coverage1)', 'conclusion': 'success'}]

        self.assertEqual(reusable_run([self.run], 'owner/erp', 'abc', jobs, 'coverage1'), 42)
        self.assertIsNone(reusable_run([self.run], 'owner/erp', 'abc', jobs, 'coverage2'))
        self.assertIsNone(reusable_run([self.run], 'owner/erp', 'different', jobs, 'coverage1'))
        # 显式全量覆盖面更大，同 tree 时同样可作为发版凭据。
        self.assertEqual(reusable_run([self.run], 'owner/erp', 'abc', self.jobs, 'coverage1'), 42)

    def test_release_workflow_uses_release_suite(self):
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        validate = workflow.split('\n  validate:', 1)[1].split('\n  images:', 1)[0]
        self.assertIn('suite: release', validate)
        self.assertIn('base: ${{ needs.preflight.outputs.base }}', validate)
        self.assertIn('browser_projects: both', validate)
        self.assertNotIn('validation_modules', workflow)
        for other in ('suite: full', 'suite: auto'):
            self.assertNotIn(other, validate)

    def test_validation_markers_follow_gate_even_when_suites_are_skipped(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        for job, output in (('full-validation', 'full'), ('release-validation', 'release'), ('scoped-validation', 'scoped')):
            block = re.split(r'\n  (?! )', workflow.split(f'\n  {job}:\n', 1)[1], maxsplit=1)[0]
            condition = next(line for line in block.splitlines() if line.strip().startswith('if:'))
            # 未选中的套件会被跳过；默认 success() 会把标记连带跳过，必须显式依据 gate 结论。
            self.assertIn('!cancelled()', condition, job)
            self.assertIn("needs.gate.result == 'success'", condition, job)
            self.assertIn(f"needs.plan.outputs.{output} == 'true'", condition, job)
        self.assertIn('name: Full validation (${{ needs.plan.outputs.tree }})', workflow)

    def release_plan(self, *changed):
        def fake_git(*args):
            if args[0] == 'tag':
                return 'v1.8.8'
            return '\0'.join(changed) + '\0'

        with patch('scripts.ci.release_gate.git', side_effect=fake_git):
            return release_scope('commit', 'v1.8.9')[1]

    def test_release_runs_all_backend_and_unit_tests_but_only_affected_pages_ota_and_installers(self):
        from scripts.ci.backend_test_matrix import TARGETS

        scope = self.release_plan('backend/apps/business/services/supply.py')
        self.assertEqual(scope['mode'], 'release')
        self.assertEqual(set(scope['backend_targets']), {t for group in TARGETS.values() for t in group})
        units = {str(p.relative_to(ROOT / 'frontend')) for p in (ROOT / 'frontend/src').rglob('*.spec.ts')}
        self.assertEqual(set(scope['frontend_tests']), units)
        self.assertTrue(scope['ops'])
        self.assertFalse(scope['ota'] or scope['installers'])
        self.assertIn('e2e/payment-terms.spec.ts', scope['browser_specs'])
        self.assertNotIn('e2e/sales-role.spec.ts', scope['browser_specs'])
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])

    def test_release_never_runs_full_chain_and_covers_unregistered_paths(self):
        scope = self.release_plan('frontend/e2e/full-chain.spec.ts', 'brand-new.file')
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])
        self.assertEqual(scope['modules'], sorted(BUSINESS))
        self.assertTrue(any('未登记路径' in reason for reason in scope['reasons']))
        # 文档类发布只跑后端、前端单测与运维脚本测试，不启动浏览器、OTA 与安装器。
        self.assertEqual(select(['README.md'], 'release'), {'fast'})
        self.assertEqual(select(['backend/apps/business/services/supply.py'], 'release'), {'fast', 'browser'})

    def test_release_runs_ota_and_installers_only_for_related_changes(self):
        cases = {
            'backend/apps/business/migrations/0001_initial.py': (True, False),
            'backend/requirements.txt': (True, True),
            'install.sh': (False, True),
            'docker/app/Dockerfile': (True, True),
            'backend/apps/core/ota.py': (True, False),
            'backend/apps/business/services/reports.py': (False, False),
        }
        for path, (ota, installers) in cases.items():
            scope = self.release_plan(path)
            self.assertEqual((scope['ota'], scope['installers']), (ota, installers), path)

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
            patch(
                'scripts.ci.release_gate.release_scope',
                return_value=('v1.9.9', {'modules': ['purchases'], 'fingerprint': 'coverage1'}),
            ),
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
