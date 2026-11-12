"""Selection reductions and their guards: a suite is skipped only for paths it neither runs nor imports."""

import glob
import re
import subprocess
import unittest
from unittest.mock import patch

from scripts.ci.backend_test_matrix import TARGETS
from scripts.ci.impact import (
    INSTALLER_TESTS,
    MODULE_FILES,
    NOT_INSTALLER_PATHS,
    ROOT,
    RUNNER_PATHS,
    contains,
    plan,
    words,
)
from scripts.ci.release_gate import preflight, release_scope, reusable_run
from scripts.ci.run_selected import backend_commands, command
from scripts.ci.select_suites import default_base, select

WORKFLOWS = ROOT / '.github/workflows'
TRACKED = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
# 引用分析只看运维范围（仓库根、scripts/、docker/、deploy/）；backend/frontend 按业务模块映射另行覆盖。
SCOPE = [path for path in TRACKED if '/' not in path or path.startswith(('scripts/', 'docker/', 'deploy/'))]
FILE = re.compile(r'[\w./-]*[\w-]\.(?:py|sh|ps1)\b|[\w./-]*Dockerfile(?:\.[\w-]+)?')
MODULE = re.compile(
    r'^\s*from\s+scripts(?:\.tests)?\s+import\s+(\w+)'
    r'|^\s*(?:from|import)\s+(?:scripts(?:\.tests)?\.)?(\w+)'
    r'|import_module\(\s*[\'"](\w+)',
    re.M,
)
# 经审阅的纯数据引用：package_release 只在安装说明中写出原生安装入口；升级演练只导入其中的 docker_compose，
# 不执行这些安装脚本。其余引用一律视为执行或导入（只会多算，不会少算）。
DATA_ONLY = {
    ('scripts/package_release.py', 'install-native.sh'),
    ('scripts/package_release.py', 'install-native.ps1'),
}


def references(path):
    text = (ROOT / path).read_text(encoding='utf-8')
    names = set(FILE.findall(text)) | {name + '.py' for groups in MODULE.findall(text) for name in groups if name}
    bases = {name.rsplit('/', 1)[-1] for name in names}
    return {
        other
        for other in SCOPE
        if other.rsplit('/', 1)[-1] in bases and other != path and (path, other) not in DATA_ONLY
    }


def closure(entries):
    seen, todo = set(), list(entries)
    while todo:
        path = todo.pop()
        if path not in seen:
            seen.add(path)
            todo.extend(references(path) - seen)
    return seen


def workflow_entries(name):
    """工作流直接运行的仓库文件，以及只做 bash -n 语法检查（不跟随其引用）的脚本。"""
    text = (WORKFLOWS / name).read_text()
    parse_only = set()
    for line in re.findall(r'for script in ([^;]+); do bash -n', text):
        for pattern in line.split():
            parse_only.update(glob.glob(pattern, root_dir=ROOT))
    text = re.sub(r'for script in [^;]+; do bash -n[^\n]*', '', text)
    executed = {f'scripts/tests/{name}' for name in re.findall(r"-p\s+'?(test_\w+\.py)", text)}
    executed.update(token.removeprefix('./') for token in FILE.findall(text) if (ROOT / token).is_file())
    return executed, parse_only


def unit_spec_matches(module, old):
    names = MODULE_FILES[module]
    specs = (ROOT / 'frontend/src').rglob('*.spec.ts')
    if old:
        return {
            str(p.relative_to(ROOT / 'frontend'))
            for p in specs
            if any(n.casefold() in p.name.casefold() for n in names)
        }
    return {
        str(p.relative_to(ROOT / 'frontend'))
        for p in specs
        if any(contains(words(p.name.removesuffix('.spec.ts')), words(n)) for n in names)
    }


class OtaSuiteSelectionTests(unittest.TestCase):
    """OPS-8：升级接口模块（单测与页面用例）与真实升级演练（ci-ota）分开选择。"""

    def test_upgrade_page_and_client_run_ota_unit_and_page_checks_without_rehearsal(self):
        for path in ('frontend/src/components/SystemUpgrade.vue', 'frontend/src/api/upgrade.ts'):
            scope = plan([path])
            self.assertEqual(scope['modules'], ['ota'], path)
            self.assertFalse(scope['ota'] or scope['installers'], path)
            self.assertIn('src/components/SystemUpgrade.spec.ts', scope['frontend_tests'], path)
            self.assertIn('e2e/system-upgrade.spec.ts', scope['browser_specs'], path)
            self.assertIn('apps.core.tests.test_ota', scope['backend_targets'], path)
            self.assertEqual(select([path]), {'fast', 'browser'}, path)
        self.assertEqual(select(['backend/apps/core/ota.py']), {'fast', 'browser', 'ota'})

    def test_ops_unit_tests_run_only_where_they_are_executed(self):
        for path in (
            'scripts/tests/test_ota_runner.py',
            'scripts/tests/test_ota_service.py',
            'scripts/tests/test_release_install.py',
            'scripts/tests/test_container_ota.py',
            'scripts/tests/test_backup.py',
            'scripts/tests/test_reliability.py',
            'scripts/tests/test_ops_check.py',
        ):
            scope = plan([path])
            self.assertTrue(scope['ops'], path)
            self.assertFalse(scope['ota'], path)
            self.assertEqual(scope['modules'], [], path)
            self.assertFalse(scope['backend'] or scope['frontend'] or scope['browser_specs'], path)
            # 安装器流程在三平台运行的单测仍启动安装器，其余只在 fast/ops 运行。
            self.assertEqual(scope['installers'], path in INSTALLER_TESTS, path)
            self.assertEqual(select([path]), {'fast', 'installers'} if path in INSTALLER_TESTS else {'fast'}, path)

    def test_runtime_upgrade_changes_still_run_the_rehearsal(self):
        for path in (
            'backend/apps/core/ota.py',
            'backend/apps/core/schema_guard.py',
            'backend/apps/core/management/commands/migrate.py',
            'backend/apps/core/migrations/0004_upgradejob.py',
            'backend/apps/business/migrations/0001_initial.py',
            'backend/requirements.txt',
            '.github/workflows/ci-ota.yml',
            'docker/app/Dockerfile',
            'docker-compose.yml',
            'install.sh',
            'scripts/ota_runner.py',
            'scripts/container_ota.py',
            'scripts/container_runtime.py',
            'scripts/release_install.py',
            'scripts/tests/ota_smoke.py',
            'scripts/tests/container_ota_smoke.py',
            'scripts/tests/native-ota-smoke.sh',
            # 此前漏选：ci-ota 直接运行或导入，现由引用分析核对。
            'scripts/tests/direct_compose_smoke.py',
            'scripts/package_release.py',
            'scripts/native_install.py',
            'scripts/ci/build_native_wheels.py',
        ):
            self.assertTrue(plan([path])['ota'], path)
        # 显式指定 ota 模块仍运行演练。
        self.assertTrue(plan(['frontend/src/components/NewWidget.vue'], modules=('ota',))['ota'])

    def test_unit_specs_match_whole_words_not_substrings(self):
        self.assertEqual(words('FinanceTotals'), ['finance', 'totals'])
        self.assertEqual(words('BOMPurchasePicker'), ['bom', 'purchase', 'picker'])
        self.assertEqual(words('PurchaseContractPage.audit'), ['purchase', 'contract', 'page', 'audit'])
        self.assertTrue(contains(words('SystemUpgrade'), words('upgrade')))
        self.assertTrue(contains(words('bom-purchase-layout'), words('bom-purchase')))
        self.assertFalse(contains(words('FinanceTotals'), words('ota')))
        self.assertFalse(contains(words('anything'), []))
        ota = plan(['backend/apps/core/ota.py'])['frontend_tests']
        self.assertNotIn('src/components/FinanceTotals.spec.ts', ota)
        self.assertIn('src/components/SystemUpgrade.spec.ts', ota)
        self.assertIn(
            'src/components/FinanceTotals.spec.ts',
            plan(['backend/apps/business/services/finance.py'])['frontend_tests'],
        )

    def test_whole_word_matching_drops_only_reviewed_substring_hits(self):
        # 与原子串匹配相比，只允许去掉经审阅、确认与模块无关的命中；新增文件若因此少选，须先审阅再登记。
        # 整词匹配多选（如 bom-purchase 命中 BOMPurchasePicker）只会多跑用例，不受限制。
        reviewed = {('ota', 'src/components/FinanceTotals.spec.ts')}
        for module in MODULE_FILES:
            dropped = unit_spec_matches(module, True) - unit_spec_matches(module, False)
            self.assertEqual({(module, spec) for spec in dropped} - reviewed, set(), module)


class InstallerSelectionTests(unittest.TestCase):
    """OPS-9：安装器只因其执行或导入的文件启动；scripts/ 下其他文件（含新增）默认仍启动。"""

    def test_standalone_ops_tools_and_rehearsal_scripts_skip_installers(self):
        for path in ('scripts/backup_cycle.py', 'scripts/ops_check.py'):
            scope = plan([path])
            self.assertTrue(scope['ops'], path)
            self.assertFalse(scope['installers'] or scope['ota'], path)
            self.assertEqual(scope['modules'], [], path)
            self.assertEqual(select([path]), {'fast'}, path)
        for path in (
            'scripts/tests/ota_smoke.py',
            'scripts/tests/ota_native_smoke.py',
            'scripts/tests/direct_compose_smoke.py',
        ):
            scope = plan([path])
            self.assertTrue(scope['ota'], path)
            self.assertFalse(scope['installers'], path)

    def test_installer_inputs_and_unknown_scripts_still_run_installers(self):
        for path in (
            'install.sh',
            'install.ps1',
            'install-native.sh',
            'install-native.ps1',
            'deploy/native-config.example.json',
            'docker/app/Dockerfile',
            'docker-compose.yml',
            '.env.example',
            '.dockerignore',
            'backend/requirements.txt',
            'scripts/native_install.py',
            'scripts/native_service.py',
            'scripts/ota_service.py',
            'scripts/ota_runner.py',
            'scripts/release_install.py',
            'scripts/network_check.py',
            'scripts/package_release.py',
            'scripts/backup.py',
            'scripts/restore_uploads.py',
            'scripts/container_runtime.py',
            'scripts/container_ota.py',
            # 安装器任务对 scripts/*.sh、scripts/tests/*.sh 做 bash -n 语法检查。
            'scripts/precheck-tests.sh',
            'scripts/setup-hooks.sh',
            'scripts/tests/native-ota-smoke.sh',
            'scripts/tests/install.ps1',
            'scripts/tests/native_smoke.py',
            'scripts/tests/container_ota_smoke.py',
            'scripts/ci/build_native_wheels.py',
            'scripts/ci/verify_native_wheels.py',
            '.github/workflows/release-installers.yml',
            # 未登记的新脚本默认启动安装器，不因清单遗漏而少测。
            'scripts/brand_new_tool.py',
            'scripts/tests/brand_new_smoke.py',
            *INSTALLER_TESTS,
        ):
            self.assertTrue(plan([path])['installers'], path)

    def test_installer_test_list_matches_the_workflow(self):
        workflow = (WORKFLOWS / 'release-installers.yml').read_text()
        listed = {f'scripts/tests/{name}' for name in re.findall(r'-p (test_\w+\.py)', workflow)}
        self.assertEqual(listed, set(INSTALLER_TESTS))
        self.assertTrue(set(NOT_INSTALLER_PATHS) <= set(TRACKED))


class ReferenceClosureTests(unittest.TestCase):
    """跳过某套件的前提：该套件运行的文件及其（递归）导入、执行的文件都会选中它。"""

    def test_every_file_the_installer_workflow_runs_or_imports_selects_installers(self):
        executed, parse_only = workflow_entries('release-installers.yml')
        self.assertIn('scripts/tests/native_smoke.py', executed)
        self.assertIn('scripts/precheck-tests.sh', parse_only)
        missing = sorted(path for path in closure(executed) | parse_only if not plan([path])['installers'])
        self.assertEqual(missing, [])
        self.assertFalse(closure(executed) & set(NOT_INSTALLER_PATHS))

    def test_every_file_the_ota_workflow_runs_or_imports_selects_ota(self):
        executed, parse_only = workflow_entries('ci-ota.yml')
        self.assertEqual(parse_only, set())
        # ci-ota 不运行单测：单测由 fast/ops 与安装器运行，改单测不需要升级演练。
        self.assertNotIn('unittest', (WORKFLOWS / 'ci-ota.yml').read_text())
        self.assertIn('scripts/tests/ota_smoke.py', executed)
        # 两个任务都构建 docker/app/Dockerfile，复制进镜像的脚本同样是演练输入。
        reached = closure(executed | {'docker/app/Dockerfile'})
        self.assertIn('scripts/restore_uploads.py', reached)
        missing = sorted(path for path in reached if not plan([path])['ota'])
        self.assertEqual(missing, [])
        self.assertFalse(any(path.startswith('scripts/tests/test_') for path in reached))


class ParallelBackendTests(unittest.TestCase):
    """OPS-27：后端用例多进程执行，并发阶段保持串行；只改执行方式，不增减用例。"""

    def test_backend_runs_split_concurrency_serially_and_the_rest_in_parallel(self):
        targets = sorted(target for group in TARGETS.values() for target in group)
        runs = backend_commands(targets, parallel=True)
        self.assertEqual(len(runs), 2)
        (_, rest), (_, serial) = runs
        self.assertIn('--parallel=auto', rest)
        self.assertNotIn('--parallel=auto', serial)
        ran = [arg for argv in (rest, serial) for arg in argv if arg.startswith('apps.')]
        self.assertEqual(sorted(ran), targets)
        self.assertEqual({arg for arg in serial if arg.startswith('apps.')}, set(TARGETS['concurrency']))
        for argv in (rest, serial):
            self.assertIn('--settings=config.test_settings', argv)

    def test_backend_split_handles_partial_selections_and_falls_back_to_serial(self):
        self.assertEqual(backend_commands([], parallel=True), [])
        only = backend_commands(['apps.core.tests.test_concurrency'], parallel=True)
        self.assertEqual(len(only), 1)
        self.assertNotIn('--parallel=auto', only[0][1])
        rest = backend_commands(['apps.core.tests.test_ota'], parallel=True)
        self.assertEqual(len(rest), 1)
        self.assertIn('--parallel=auto', rest[0][1])
        # 没有 tblib（多进程回溯传递）时退回与原来相同的串行命令。
        self.assertEqual(
            backend_commands(['apps.core.tests.test_ota'], parallel=False)[0],
            command('backend', ['apps.core.tests.test_ota']),
        )
        with self.assertRaises(ValueError):
            command('backend', ['apps.core.tests.test_ota', 'apps.unknown'])

    def test_parallel_clone_databases_pass_the_test_database_guards(self):
        # Django 多进程把测试库克隆为 <name>_1、<name>_2…；迁移与清库保护按前缀放行，克隆库仍满足。
        settings = (ROOT / 'backend/config/test_settings.py').read_text()
        self.assertIn("'TEST': {'NAME': 'test_atm_erp_lean'}", settings)
        for command_name in ('migrate', 'flush'):
            guard = (ROOT / f'backend/apps/core/management/commands/{command_name}.py').read_text()
            self.assertIn(".startswith('test_atm_erp_lean')", guard, command_name)
        workflow = (WORKFLOWS / 'ci-fast.yml').read_text()
        backend = workflow.split('\n  backend:\n', 1)[1].split('\n  ops:\n', 1)[0]
        self.assertIn('pip install -r backend/requirements-dev.txt', backend)
        # tblib 随开发依赖固定版本安装，CI 后端任务才会走多进程。
        self.assertRegex((ROOT / 'backend/requirements-dev.txt').read_text(), r'(?m)^tblib==\d+\.\d+\.\d+$')
        self.assertIn('python -m scripts.ci.run_selected backend', backend)


class WorkflowCostTests(unittest.TestCase):
    """OPS-21/OPS-22：去掉重复安装与无效缓存导出，保留实际验证。"""

    def test_installers_verify_offline_wheels_without_a_second_pypi_install(self):
        workflow = (WORKFLOWS / 'release-installers.yml').read_text()
        self.assertNotIn('pip install -r backend/requirements.txt', workflow)
        self.assertIn('python scripts/ci/verify_native_wheels.py --wheels "wheels/$PLATFORM"', workflow)
        verify = (ROOT / 'scripts/ci/verify_native_wheels.py').read_text()
        for check in ("'check'", 'import django, daphne, psycopg2, redis'):
            self.assertIn(check, verify)

    def test_every_native_wheel_architecture_is_installed_on_its_own_runner(self):
        # OPS-4：verify_native_wheels 只检查运行器自身架构；每个打包的 wheelhouse 都要有对应架构的运行器。
        from scripts.ci.build_native_wheels import TARGETS as WHEELS

        workflow = (WORKFLOWS / 'release-installers.yml').read_text()
        self.assertIn('os: [ubuntu-latest, macos-latest, windows-latest]', workflow)
        covered = {('linux', 'x86_64'), ('macos', 'arm64'), ('windows', 'amd64')}
        covered |= set(re.findall(r'\{platform: (\w+), arch: (\w+), runner: [\w.-]+\}', workflow))
        self.assertEqual(covered, {(name, arch) for name, arches in WHEELS.items() for arch in arches})

    def test_release_images_read_the_warm_main_cache_and_do_not_export(self):
        release = (WORKFLOWS / 'release.yml').read_text()
        images = release.split('\n  images:\n', 1)[1].split('\n  native-wheels:\n', 1)[0]
        self.assertIn('cache-from: type=gha,scope=app-image', images)
        self.assertNotIn('cache-to:', images)
        warm = (WORKFLOWS / 'ci-cache.yml').read_text()
        paths = warm.split('paths:', 1)[1].split('schedule:', 1)[0]
        # 镜像依赖层的输入：Dockerfile、运行时依赖、npm ci 层复制的两个前端清单。
        for path in (
            'docker/app/Dockerfile',
            'backend/requirements.txt',
            'frontend/package.json',
            'frontend/package-lock.json',
        ):
            self.assertIn(f'- {path}\n', paths, path)
        dockerfile = (ROOT / 'docker/app/Dockerfile').read_text()
        self.assertIn('COPY frontend/package*.json ./', dockerfile)


class NestedReleaseEvidenceTests(unittest.TestCase):
    """OPS-10：重新派发 Release 时复用此前 Release 内已通过的同 tree 同计划发版验证。"""

    def setUp(self):
        self.run = {
            'id': 7,
            'event': 'push',
            'status': 'completed',
            'conclusion': 'failure',
            'head_repository': {'full_name': 'owner/erp'},
        }
        self.marker = 'validate / Release validation (abc coverage1)'

    def find(self, runs, jobs, tree='abc', fingerprint='coverage1', repository='owner/erp'):
        return reusable_run(runs, repository, tree, lambda _: jobs, fingerprint, nested=True)

    def test_successful_nested_validation_is_reused_even_if_packaging_failed(self):
        jobs = [
            {'name': self.marker, 'conclusion': 'success'},
            {'name': 'images (amd64, ubuntu-latest)', 'conclusion': 'failure'},
        ]
        self.assertEqual(self.find([self.run], jobs), 7)
        self.assertEqual(self.find([dict(self.run, conclusion='cancelled')], jobs), 7)
        self.assertEqual(self.find([dict(self.run, event='workflow_dispatch', conclusion='success')], jobs), 7)

    def test_nested_evidence_requires_success_tree_plan_repository_and_finished_run(self):
        ok = [{'name': self.marker, 'conclusion': 'success'}]
        for jobs in (
            [{'name': self.marker, 'conclusion': 'failure'}],
            [{'name': self.marker, 'conclusion': 'skipped'}],
            [{'name': self.marker, 'conclusion': 'cancelled'}],
            # 未经 Release 调用的同名任务、按影响范围的凭据与 gate 都不算。
            [{'name': 'Release validation (abc coverage1)', 'conclusion': 'success'}],
            [{'name': 'validate / Scoped validation (abc coverage1)', 'conclusion': 'success'}],
            [{'name': 'validate / CI gate', 'conclusion': 'success'}],
        ):
            self.assertIsNone(self.find([self.run], jobs), jobs)
        self.assertIsNone(self.find([self.run], ok, tree='different'))
        self.assertIsNone(self.find([self.run], ok, fingerprint='coverage2'))
        self.assertIsNone(self.find([self.run], ok, repository='other/erp'))
        self.assertIsNone(self.find([dict(self.run, status='in_progress', conclusion=None)], ok))
        self.assertIsNone(self.find([dict(self.run, event='pull_request_target')], ok))

    def test_ci_runs_still_require_a_successful_run(self):
        jobs = [{'name': 'Release validation (abc coverage1)', 'conclusion': 'success'}]
        failed = dict(self.run, conclusion='failure')
        self.assertIsNone(reusable_run([failed], 'owner/erp', 'abc', lambda _: jobs, 'coverage1'))
        self.assertEqual(
            reusable_run([dict(failed, conclusion='success')], 'owner/erp', 'abc', lambda _: jobs, 'coverage1'), 7
        )

    def preflight_with(self, ci_runs, release_runs, jobs, force=False):
        def git_result(*args):
            if args[0] == 'rev-parse':
                return 'abc' if args[1].endswith('^{tree}') else 'commit'
            if args[1].endswith('version.py'):
                return "VERSION = '2.0.0'"
            if args[1].endswith('.json'):
                return '{"version":"2.0.0"}'
            return '## 📥 Installation\n## 📚 Documentation'

        calls = []

        def api(path):
            calls.append(path)
            if path.endswith('/releases?per_page=100'):
                return []
            if '/workflows/ci.yml/runs' in path:
                return {'workflow_runs': ci_runs}
            if '/workflows/release.yml/runs' in path:
                self.assertIn('status=completed', path)
                return {'workflow_runs': release_runs}
            return {'jobs': jobs}

        with (
            patch('scripts.ci.release_gate.git', side_effect=git_result),
            patch('scripts.ci.release_gate.subprocess.run'),
            patch(
                'scripts.ci.release_gate.release_scope',
                return_value=('v1.9.9', {'modules': ['purchases'], 'fingerprint': 'coverage1'}),
            ),
            patch('scripts.ci.release_gate.api', side_effect=api),
        ):
            return preflight('v2.0.0', 'owner/erp', force=force), calls

    def test_preflight_falls_back_to_earlier_release_runs(self):
        jobs = [{'name': self.marker, 'conclusion': 'success'}]
        result, calls = self.preflight_with([], [self.run], jobs)
        self.assertEqual((result['validate'], result['reused_run']), ('false', '7'))
        self.assertTrue(any('/workflows/release.yml/runs' in call for call in calls))
        result, _ = self.preflight_with([], [self.run], [{'name': self.marker, 'conclusion': 'failure'}])
        self.assertEqual((result['validate'], result['reused_run']), ('true', ''))
        # 强制重跑不查任何凭据。
        result, calls = self.preflight_with([], [self.run], jobs, force=True)
        self.assertEqual(result['validate'], 'true')
        self.assertFalse(any('/runs' in call for call in calls))


class RunnerLintAndBaselineTests(unittest.TestCase):
    """OPS-18/OPS-28/OPS-31：运行器改动实际执行各类命令；Lint 覆盖全部 scripts；手动发版验证与 Release 同一基线。"""

    def test_runner_changes_exercise_backend_frontend_and_browser_commands(self):
        for path in RUNNER_PATHS:
            scope = plan([path])
            self.assertTrue(scope['backend'] and scope['frontend'] and scope['ops'], path)
            self.assertIn('apps.core.tests.test_platform', scope['backend_targets'], path)
            self.assertTrue(scope['frontend_tests'] and scope['browser_specs'], path)
            self.assertFalse(scope['ota'] or scope['installers'], path)
            self.assertEqual(select([path]), {'fast', 'browser'}, path)
        # 发布预检与证据核对不生成测试命令，仍只跑运维单测。
        self.assertEqual(select(['scripts/ci/release_gate.py']), {'fast'})

    def test_deleted_spec_files_are_recorded_but_not_run(self):
        # 改名或删除的用例文件不能再运行；替代用例按自身路径选择，删除的被测源码仍须显式指定 modules。
        scope = plan(['frontend/e2e/removed-audit.spec.ts', 'frontend/e2e/login.spec.ts'])
        self.assertEqual(scope['browser_specs'], ['e2e/login.spec.ts'])
        self.assertTrue(any('removed-audit.spec.ts' in reason for reason in scope['reasons']))
        # 删除的单测文件不再运行，前端检查照常执行。
        self.assertTrue(plan(['frontend/src/components/Removed.spec.ts'])['frontend'])
        with self.assertRaises(ValueError):
            plan(['frontend/src/components/Removed.vue'])

    def test_checks_stage_and_ops_job_lint_every_script(self):
        from run_all_tests import commands

        lint = next(argv for _, argv in commands('checks') if 'ruff' in argv and 'check' in argv)
        self.assertIn('scripts', lint)
        # 只改 scripts/ 时不启动 backend 任务，ops 任务同样执行 Ruff。
        workflow = (WORKFLOWS / 'ci-fast.yml').read_text()
        ops = workflow.split('\n  ops:\n', 1)[1].split('\n  frontend:\n', 1)[0]
        self.assertIn('ruff check --config backend/pyproject.toml scripts run_all_tests.py', ops)
        self.assertIn("grep -E '^ruff==' backend/requirements-dev.txt", ops)

    def test_manual_release_validation_uses_the_release_baseline(self):
        # 预发布 tag 离 HEAD 更近；git describe 会选中它，Release 则选低于目标版本的最高正式 tag。
        tags = 'v1.9.0-rc1\nv1.8.36-rc2\nv1.8.35\nv1.8.34'

        def fake_git(*args):
            if args[0] == 'show':
                self.assertEqual(args[1], 'HEAD:backend/apps/core/version.py')
                return "VERSION = '1.8.36'"
            if args[0] == 'diff':
                return ''
            self.assertEqual(args[:2], ('tag', '--merged'))
            return tags

        with (
            patch('scripts.ci.release_gate.git', side_effect=fake_git),
            patch('scripts.ci.select_suites.subprocess.check_output') as describe,
        ):
            manual = default_base('release', 'HEAD')
            describe.assert_not_called()
            released, _ = release_scope('HEAD', 'v1.8.36')
        self.assertEqual((manual, released), ('v1.8.35', 'v1.8.35'))
        with patch('scripts.ci.release_gate.git', return_value="VERSION = '1.8.36-dev'"):
            with self.assertRaises(ValueError):
                default_base('release', 'HEAD')
        with patch('scripts.ci.select_suites.subprocess.check_output', return_value='v1.8.36-rc2\n') as describe:
            self.assertEqual(default_base('auto', 'HEAD'), 'v1.8.36-rc2')
        self.assertIn('HEAD^', describe.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
