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
from scripts.ci.publish_release import is_highest_stable, verify
from scripts.ci.publish_release import main as publish_main
from scripts.ci.release_gate import preflight, release_scope, reusable_run
from scripts.ci.run_selected import command
from scripts.ci.select_suites import BROWSER_MAX_SHARDS, BROWSER_SECONDS, SUITES, browser_matrix, browser_shards, select


class RoutingTests(unittest.TestCase):
    def test_project_milestones_select_project_browser_and_backend_regressions(self):
        paths = [
            'backend/apps/business/services/milestones.py',
            'backend/apps/business/task_milestones.py',
            'frontend/src/components/ProjectMilestones.vue',
            'frontend/src/components/TaskTimeRecords.vue',
            'frontend/src/components/ProjectTaskSupervisors.vue',
            'frontend/src/components/TaskNotices.vue',
            'backend/apps/business/services/task_supervision.py',
            'backend/apps/business/api/task_notices.py',
            'frontend/src/modules/milestones.ts',
        ]
        for path in paths:
            with self.subTest(path=path):
                scope = plan([path])
                self.assertIn('projects', scope['modules'])
                self.assertIn('e2e/project-milestones.spec.ts', scope['browser_specs'])
                self.assertIn('apps.business.tests.test_milestones', scope['backend_targets'])
                self.assertIn('apps.business.tests.test_task_supervision', scope['backend_targets'])
        self.assertEqual(
            plan(['frontend/e2e/project-milestones.spec.ts'])['browser_specs'], ['e2e/project-milestones.spec.ts']
        )

    def test_bom_export_paths_select_scoped_export_and_selection_checks(self):
        for path in (
            'backend/apps/business/services/bom_export.py',
            'frontend/src/api/bom.ts',
        ):
            scope = plan([path])
            self.assertEqual(scope['modules'], ['bom'])
            self.assertIn('apps.business.tests.test_bom_export', scope['backend_targets'])
            self.assertIn('e2e/bom-export.spec.ts', scope['browser_specs'])
            self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])
        self.assertEqual(plan(['frontend/e2e/bom-export.spec.ts'])['browser_specs'], ['e2e/bom-export.spec.ts'])

    def test_attachment_preview_covers_all_document_consumers(self):
        for path in (
            'backend/apps/business/document_preview.py',
            'frontend/src/document-preview.ts',
            'frontend/src/components/DocumentPreview.vue',
            'frontend/src/components/PdfPreview.vue',
            'frontend/pdf-assets.ts',
            'frontend/e2e/fixtures/document-preview/comparison.xlsx',
        ):
            scope = plan([path])
            self.assertEqual(set(scope['modules']), {'sales', 'projects', 'purchases', 'finance'}, path)
            self.assertIn('apps.business.tests.test_document_preview', scope['backend_targets'], path)
            self.assertIn('e2e/document-preview.spec.ts', scope['browser_specs'], path)
            self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'], path)

    def test_warehouse_detail_components_cover_receipt_and_issue_pages(self):
        scope = plan(['frontend/src/components/WarehouseLines.vue', 'frontend/src/modules/warehouse-lines.ts'])
        self.assertEqual(set(scope['modules']), {'purchases', 'inventory'})
        self.assertIn('e2e/warehouse-lines.spec.ts', scope['browser_specs'])
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])

    def test_process_progress_covers_its_read_projections(self):
        scope = plan(['backend/apps/business/services/progress.py', 'frontend/src/components/ProjectProgress.vue'])
        self.assertEqual(set(scope['modules']), {'sales', 'projects', 'purchases', 'finance'})
        self.assertIn('apps.business.tests.test_progress', scope['backend_targets'])
        self.assertIn('e2e/process-progress.spec.ts', scope['browser_specs'])
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])

    def test_data_checks_cover_the_modules_whose_rules_they_read(self):
        scope = plan(['backend/apps/business/services/data_checks.py', 'backend/apps/business/api/data_checks.py'])
        self.assertEqual(set(scope['modules']), {'finance', 'purchases', 'projects', 'accounts'})
        for target in ('reconciliation', 'deletions', 'bank_import', 'transfers'):
            self.assertIn(f'apps.business.tests.test_{target}', scope['backend_targets'])
        page = plan(['frontend/src/components/DataChecks.vue'])
        self.assertEqual(page['modules'], scope['modules'])
        self.assertIn('src/components/DataChecks.spec.ts', page['frontend_tests'])
        self.assertIn('e2e/settings.spec.ts', page['browser_specs'])
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])

    def test_purchase_change_requests_select_purchase_regressions(self):
        scope = plan(['backend/apps/business/services/purchase_changes.py'])
        self.assertEqual(scope['modules'], ['purchases'])
        self.assertIn('apps.business.tests.test_purchase_changes', scope['backend_targets'])
        self.assertIn('e2e/purchase-changes.spec.ts', scope['browser_specs'])
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])

    def test_purchase_contract_template_selects_complete_preview_and_archive_checks(self):
        scope = plan(
            ['backend/apps/business/services/contract_clauses.py', 'frontend/src/views/PurchaseContractPage.vue']
        )
        self.assertEqual(scope['modules'], ['purchases'])
        self.assertIn('apps.business.tests.test_purchase_contract', scope['backend_targets'])
        self.assertIn('e2e/purchase-contract.spec.ts', scope['browser_specs'])
        self.assertIn('src/views/PurchaseContractPage.audit.spec.ts', scope['frontend_tests'])

    def test_import_helpers_include_scope_and_concurrency_regressions(self):
        for helper in ('import_dedup', 'import_locks'):
            scope = plan([f'backend/apps/business/services/{helper}.py'])
            self.assertIn('apps.business.tests.test_import_concurrency', scope['backend_targets'])
            self.assertIn('finance', scope['modules'])
            self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])

    def test_documentation_and_deleted_paths(self):
        self.assertEqual(select(['README.md', 'docs/old-guide.md']), set())
        with self.assertRaises(ValueError):
            select(['frontend/src/removed.vue'])

    def test_release_screenshots_are_documentation_but_unknown_sources_are_not(self):
        screenshots = [f'docs/releases/assets/v1.8.11/desktop.{ext}' for ext in ('png', 'jpg', 'jpeg', 'webp')]
        documents = ['docs/screenshots/login.png', 'docs/output/手册.docx', 'docs/output/分析.pptx']
        self.assertEqual(select([*screenshots, *documents]), set())
        self.assertEqual(
            plan(['backend/apps/business/services/supply.py', *screenshots]),
            plan(['backend/apps/business/services/supply.py']),
        )
        for path in ('docs/releases/assets/helper.py', 'docs/releases/assets/page.html', 'docs/tool.sh', 'unknown.png'):
            with self.assertRaises(ValueError):
                select([path])

    def test_root_tooling_files_are_classified(self):
        # 镜像内容由 .dockerignore 决定，与 docker/ 一样运行安装器与升级演练。
        scope = plan(['.dockerignore'])
        self.assertTrue(scope['ota'] and scope['installers'] and scope['ops'])
        # 升级演练实际执行 install.sh、backup.py，并以 .env.example 直接 Compose 启动。
        for path in ('install.sh', 'scripts/backup.py', '.env.example'):
            self.assertTrue(plan([path])['ota'], path)
        self.assertFalse(plan(['install-native.sh'])['ota'])
        # ci-fast 的后端任务通过 run_all_tests.py 执行静态检查。
        self.assertEqual(plan(['run_all_tests.py']), plan(['.github/workflows/ci-fast.yml']))
        # 本地钩子与仓库元数据只运行运维脚本测试，不选业务模块。
        for path in ('.githooks/pre-push', '.pre-commit-config.yaml', '.gitattributes', '.codex'):
            scope = plan([path])
            self.assertEqual(select([path]), {'fast'}, path)
            self.assertTrue(scope['ops'], path)
            self.assertFalse(scope['backend'] or scope['frontend'] or scope['ota'] or scope['installers'], path)
            self.assertEqual(scope['modules'], [], path)

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
        for path in ('frontend/package-lock.json', 'backend/requirements.txt', 'backend/constraints.txt'):
            scope = plan([path])
            self.assertEqual(scope['modules'], sorted(BUSINESS + (('ota',) if path.startswith('backend/') else ())), path)
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
        scoped = plan(['frontend/e2e/full-chain.spec.ts'])
        self.assertNotIn('e2e/full-chain.spec.ts', scoped['browser_specs'])
        self.assertTrue(any('仅在显式 suite=full' in reason for reason in scoped['reasons']))
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
        # 覆盖整个仓库，不只 backend/frontend；-z 保留含空格或中文的路径原样（与 select_suites 读取差异一致）。
        paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT, text=True).split('\0')
        unclassified = []
        for path in filter(None, paths):
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

    def test_shared_business_tables_cover_all_modules_without_full_chain(self):
        for name in ('BusinessTable', 'TableScroll'):
            scope = plan([f'frontend/src/components/{name}.vue'])
            self.assertEqual(scope['modules'], sorted(BUSINESS))
            self.assertIn('e2e/pagination-layout.spec.ts', scope['browser_specs'])
            self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])
            self.assertFalse(scope['ota'] or scope['installers'])

    def test_config_settings_uses_shared_mapping_not_accounts_stem(self):
        scope = plan(['backend/config/settings.py'])
        self.assertEqual(scope['modules'], sorted(BUSINESS))
        self.assertNotIn('e2e/full-chain.spec.ts', scope['browser_specs'])
        for path in ('frontend/src/modules/settings.ts', 'frontend/src/views/SettingsPage.vue'):
            self.assertTrue((ROOT / path).is_file(), path)
            self.assertIn('accounts', plan([path])['modules'], path)

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
        for path in (
            'frontend/src/forms.ts',
            'frontend/src/modules/sales.ts',
            'frontend/src/modules/purchases.ts',
            'frontend/src/modules/finance.ts',
        ):
            self.assertIn('src/modules/business-date.spec.ts', plan([path])['frontend_tests'])

    def test_check_only_configuration_runs_static_checks_without_modules(self):
        scope = plan(['frontend/eslint.config.js', 'backend/pyproject.toml'])
        self.assertEqual(scope['modules'], [])
        self.assertTrue(scope['backend'] and scope['frontend'])
        self.assertEqual(scope['browser_specs'], [])
        # requirements-dev.txt 只固定 Ruff：只跑后端静态检查，不像运行时依赖那样覆盖全部业务模块。
        dev = plan(['backend/requirements-dev.txt'])
        self.assertEqual(dev['modules'], [])
        self.assertTrue(dev['backend'])
        self.assertEqual(dev['browser_specs'], [])
        self.assertFalse(dev['ota'] or dev['installers'])

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

    def test_browser_shards_cover_every_selected_spec_exactly_once(self):
        business = plan([], modules=BUSINESS)['browser_specs']
        full = plan([], full=True)['browser_specs']
        narrow = plan(['backend/apps/core/ota.py'])['browser_specs']
        for specs in (business, full, narrow, business[:1]):
            shards = browser_shards(specs)
            self.assertEqual(sorted(spec for group in shards for spec in group), sorted(specs))
            self.assertTrue(all(shards))
            self.assertLessEqual(len(shards), BROWSER_MAX_SHARDS)
            self.assertEqual(shards, browser_shards(reversed(specs)))
        # 小范围不拆分，避免为几条用例多起几套安装；大范围拆开且不把最慢的文件叠在同一片。
        self.assertEqual(len(browser_shards(narrow)), 1)
        self.assertGreater(len(browser_shards(business)), 1)
        slowest = [f'e2e/{name}.spec.ts' for name in sorted(BROWSER_SECONDS, key=BROWSER_SECONDS.get)[-2:]]
        self.assertEqual(len([group for group in browser_shards(full) if set(group) & set(slowest)]), 2)
        self.assertEqual(browser_shards([]), [])
        for name in BROWSER_SECONDS:
            self.assertTrue((ROOT / f'frontend/e2e/{name}.spec.ts').is_file(), name)

    def test_browser_matrix_runs_each_shard_in_the_requested_viewports(self):
        specs = plan([], modules=BUSINESS)['browser_specs']
        both = browser_matrix(specs, 'both')
        count = len(browser_shards(specs))
        self.assertEqual(len(both), 2 * count)
        for project in ('desktop', 'mobile'):
            rows = [row for row in both if row['project'] == project]
            self.assertEqual([row['shard'] for row in rows], list(range(1, count + 1)))
            self.assertEqual(sorted(spec for row in rows for spec in json.loads(row['specs'])), specs)
            self.assertEqual({row['shards'] for row in rows}, {count})
            # 每片的目标仍须通过运行器的路径校验，不能借分片绕开。
            for row in rows:
                self.assertEqual(command('browser', json.loads(row['specs']), project)[1][-1], '--project=' + project)
        self.assertEqual({row['project'] for row in browser_matrix(specs, 'mobile')}, {'mobile'})
        self.assertEqual(browser_matrix([], 'both'), [])

    def test_browser_workflow_runs_planned_shards_and_only_reads_the_image_cache(self):
        ci = (ROOT / '.github/workflows/ci.yml').read_text()
        browser = (ROOT / '.github/workflows/ci-browser.yml').read_text()
        self.assertIn('browser_matrix: ${{ steps.select.outputs.browser_matrix }}', ci)
        self.assertIn('matrix: ${{ needs.plan.outputs.browser_matrix }}', ci)
        self.assertIn('include: ${{ fromJSON(inputs.matrix) }}', browser)
        self.assertIn('TEST_TARGETS: ${{ matrix.specs }}', browser)
        self.assertIn('fail-fast: false', browser)
        # 各片的失败截图分开保存，重跑也不覆盖。
        self.assertIn('browser-${{ matrix.project }}-${{ matrix.shard }}-${{ github.run_attempt }}', browser)
        # 验证任务只读镜像缓存；唯一写入方是 main 上不产生验证凭据的预热流程。
        writers = [
            path.name
            for path in (ROOT / '.github/workflows').glob('*.yml')
            if 'scope=app-image,mode=max' in path.read_text()
        ]
        self.assertEqual(writers, ['ci-cache.yml'])
        for name in ('ci-browser.yml', 'ci-ota.yml'):
            text = (ROOT / '.github/workflows' / name).read_text()
            self.assertIn('cache-from: type=gha,scope=app-image', text)
            self.assertNotIn('cache-to:', text)
        warm = (ROOT / '.github/workflows/ci-cache.yml').read_text()
        self.assertIn('branches: [main]', warm)
        self.assertNotIn('pull_request', warm)

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
        for job, output in (
            ('full-validation', 'full'),
            ('release-validation', 'release'),
            ('scoped-validation', 'scoped'),
        ):
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
            'backend/constraints.txt': (True, True),
            'install.sh': (True, True),
            'install-native.sh': (False, True),
            'scripts/backup.py': (True, True),
            '.env.example': (True, True),
            '.dockerignore': (True, True),
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

    def test_packages_built_from_a_tag_pass_publish_verification(self):
        # OPS-30：打包只用 tag 自身的源码（无安装器覆盖），产物须原样通过发布校验；此前只有打 tag 后才会执行。
        from scripts import package_release

        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            repo, artifacts, output = temporary / 'repo', temporary / 'artifacts', temporary / 'dist'
            for relative in ('docker-compose.yml', 'docker/app/runtime-protocol.json'):
                (repo / relative).parent.mkdir(parents=True, exist_ok=True)
                (repo / relative).write_bytes((ROOT / relative).read_bytes())
            (repo / 'frontend').mkdir()
            (repo / 'frontend/package.json').write_text('{}')
            identity = ['-c', 'user.name=ci', '-c', 'user.email=ci@example.invalid', '-c', 'commit.gpgsign=false']
            for args in (['init', '-q'], ['add', '.'], [*identity, 'commit', '-qm', 'release'], ['tag', 'v2.0.0']):
                subprocess.run(['git', *args], cwd=repo, check=True)
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
            records = {}
            (artifacts / 'images').mkdir(parents=True)
            for arch in ('amd64', 'arm64'):
                (artifacts / 'images' / f'{arch}.tar.gz').write_bytes(arch.encode())
                records[arch] = {'sha256': hashlib.sha256(arch.encode()).hexdigest()}
            (artifacts / 'images/manifest.json').write_text(
                json.dumps(
                    {'docker_image': 'ghcr.io/hongheshan-svg/atm-erp@sha256:' + 'a' * 64, 'docker_archives': records}
                )
            )
            for platform, arch in (('linux', 'x86_64'), ('macos', 'arm64'), ('windows', 'amd64')):
                wheels = artifacts / 'wheels' / platform / arch
                wheels.mkdir(parents=True)
                (wheels / 'requirements.lock').write_text('django==5.2\n')
                digest = hashlib.sha256((wheels / 'requirements.lock').read_bytes()).hexdigest()
                (wheels / 'SHA256.json').write_text(json.dumps({'requirements.lock': digest}))
            real_run = subprocess.run

            def run(command, **kwargs):
                if command[0] != 'npm':
                    return real_run(command, **kwargs)
                (Path(kwargs['cwd']) / 'node_modules').mkdir(exist_ok=True)
                return subprocess.CompletedProcess(command, 0)

            with (
                patch.object(package_release, 'ROOT', repo),
                patch.object(package_release.shutil, 'which', return_value='npm'),
                patch.object(package_release.subprocess, 'run', side_effect=run),
            ):
                package_release.build('v2.0.0', output, artifacts)
            self.assertEqual(len(verify(output, 'v2.0.0', commit)), 7)
            with zipfile.ZipFile(output / 'atm-erp-v2.0.0-linux-docker.zip') as archive:
                manifest = json.loads(archive.read('atm-erp-v2.0.0-linux-docker/INSTALL-MANIFEST.json'))
                compose = archive.read('atm-erp-v2.0.0-linux-docker/docker-compose.yml').decode()
            self.assertEqual(manifest['source_commit'], commit)
            self.assertNotIn('installer_commit', manifest)
            self.assertNotIn('build:', compose)
            with self.assertRaises(ValueError):
                verify(output, 'v2.0.0', 'other-commit')

    def test_publish_marks_latest_only_for_the_highest_stable_tag(self):
        # 按数值比较版本；预发布与其他 tag 不参与。
        self.assertTrue(is_highest_stable('v1.10.0', ['v1.9.9', 'v1.10.0', 'v1.11.0-rc1', 'nightly']))
        self.assertFalse(is_highest_stable('v1.9.9', ['v1.9.9', 'v1.10.0']))

        def publish(tag, tags):
            def fake_git(*args):
                return '\n'.join(tags) if args[0] == 'tag' else 'commit'

            digest = 'f' * 64
            draft = {
                'tag_name': tag,
                'draft': True,
                'assets': [{'name': 'a.zip', 'state': 'uploaded', 'digest': 'sha256:' + digest}],
            }
            with (
                patch('sys.argv', ['publish_release', '--tag', tag, '--folder', 'dist', '--upload', '--publish']),
                patch.dict('os.environ', {'GITHUB_REPOSITORY': 'owner/erp'}),
                patch('scripts.ci.publish_release.git', side_effect=fake_git),
                patch('scripts.ci.publish_release.verify', return_value={'a.zip': digest}),
                patch('scripts.ci.publish_release.api', return_value=[draft]),
                patch('scripts.ci.publish_release.subprocess.run') as run,
                patch('builtins.print'),
            ):
                publish_main()
            return run.call_args_list[-1].args[0]

        # 旧 tag 的发布（或草稿重试）晚于新版本完成时，不能把 Latest 挤回旧版本，否则 OTA 不再提示新版本。
        self.assertEqual(
            publish('v1.8.28', ['v1.8.27', 'v1.8.28', 'v1.8.29']),
            ['gh', 'release', 'edit', 'v1.8.28', '--draft=false', '--latest=false'],
        )
        self.assertEqual(
            publish('v1.8.29', ['v1.8.27', 'v1.8.28', 'v1.8.29', 'v1.9.0-rc1']),
            ['gh', 'release', 'edit', 'v1.8.29', '--draft=false', '--latest'],
        )

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
