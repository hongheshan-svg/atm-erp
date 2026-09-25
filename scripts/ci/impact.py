"""Deterministic impact plan. Unclassified executable changes fail closed, never run full implicitly."""

import hashlib
import json
from pathlib import Path

from scripts.ci.backend_test_matrix import MODULE_TESTS, TARGETS, module_targets

ROOT = Path(__file__).resolve().parents[2]
MODULE_FILES = {
    'sales': ('sales', 'amendments', 'SalesPage'),
    'projects': ('projects', 'execution', 'budgets', 'ProjectsPage', 'ProjectPage', 'BudgetPanel', 'production'),
    'bom': ('bom', 'bom_import', 'bom_material_import', 'BOMPage', 'BOMDemand', 'BOMPurchasePicker', 'bom-purchase'),
    'purchases': (
        'supply',
        'approval',
        'purchases',
        'purchase_contract',
        'purchase_warranty',
        'contract_clauses',
        'payment_terms',
        'payment-terms',
        'PurchasesPage',
        'PurchaseContractPage',
    ),
    'inventory': ('inventory', 'corrections', 'InventoryPage'),
    'finance': (
        'finance',
        'monthly',
        'banking',
        'bank_import',
        'reconciliation',
        'settlement',
        'FinancePage',
        'FinanceTotals',
    ),
    'masterdata': ('masterdata', 'product-categories', 'MasterdataPage'),
    'accounts': (
        'settings',
        'SettingsPage',
        'LoginPage',
        'SetupPage',
        'InitialPasswordInput',
        'session',
        'CodingRules',
    ),
    'reports': ('reports', 'workbench', 'attention', 'ReportsPage', 'WorkbenchPage', 'ReportAttention', 'CostSources'),
    'ota': ('ota', 'upgrade', 'SystemUpgrade'),
}
BROWSERS = {
    'sales': ('sales-role', 'attachments', 'industry-forms', 'import-surface-audit'),
    'projects': (
        'production-role',
        'state-actions-audit',
        'attachments',
        'coding-rules',
        'industry-forms',
        'specialist-roles',
        'import-surface-audit',
    ),
    'bom': ('bom-selection', 'bom-purchase-layout', 'specialist-roles'),
    'purchases': (
        'payment-terms',
        'review-remediation',
        'attachments',
        'hardening-ui',
        'specialist-roles',
        'import-surface-audit',
    ),
    'inventory': ('cancel-actions-audit', 'import-surface-audit'),
    'finance': ('reconciliation', 'bank-review-audit', 'import-surface-audit'),
    'masterdata': ('product-coding', 'account-masterdata-audit', 'transfers', 'import-surface-audit'),
    'accounts': (
        'initial-password',
        'settings',
        'login',
        'setup',
        'account-masterdata-audit',
        'eight-role-audit',
        'multi-role',
        'specialist-roles',
        'coding-rules',
        'navigation-dialog',
    ),
    'reports': ('reports', 'hardening-ui', 'transfers'),
    'ota': ('system-upgrade', 'navigation-dialog'),
}
# 完整业务链只在显式 full（含发版本）时运行，不属于任何模块。
FULL_ONLY_BROWSERS = ('full-chain',)
BUSINESS = ('sales', 'projects', 'bom', 'purchases', 'inventory', 'finance', 'masterdata', 'accounts', 'reports')
# 公共界面组件改动时额外运行的页面级用例：导航、页签、分页、各页面概览和各岗位逐页巡检。
SHARED_UI_BROWSERS = ('navigation-dialog', 'module-tabs', 'pagination-layout', 'ui-concepts', 'eight-role-audit')
# 经过审阅的共享路径映射：这些文件被多个模块直接调用，改动时运行所列模块的全部关联用例。
# 按前缀匹配、先匹配先用；只在文件名未命中 MODULE_FILES 时使用。新增的未登记路径仍然失败，不静默漏测。
SHARED_PATHS = (
    (
        (
            'backend/apps/business/services/documents.py',
            'backend/apps/business/attachments.py',
            'frontend/src/components/AttachmentDialog.vue',
            'frontend/src/modules/documents.ts',
        ),
        ('sales', 'purchases', 'projects', 'finance'),
    ),
    (
        ('backend/apps/business/services/transfers.py', 'frontend/src/components/TransferTools.vue'),
        ('masterdata', 'sales', 'projects', 'purchases', 'inventory', 'finance', 'reports'),
    ),
    (('frontend/src/components/SupplierMonthly.vue',), ('finance',)),
    (('frontend/src/industry-forms.ts',), ('sales', 'projects')),
    (
        ('frontend/src/utils/password.ts', 'backend/apps/core/views.py', 'backend/apps/core/setup.py'),
        ('accounts',),
    ),
    (('backend/apps/core/codes.py',), ('accounts', 'masterdata', 'sales', 'projects', 'purchases')),
    (('backend/apps/core/schema_guard.py', 'backend/apps/core/management/'), ('accounts', 'ota')),
    (
        (
            'backend/apps/__init__.py',
            'backend/apps/business/__init__.py',
            'backend/apps/business/api/__init__.py',
            'backend/apps/business/services/__init__.py',
            'backend/apps/core/__init__.py',
            'backend/apps/business/migrations/',
            'backend/apps/core/migrations/',
            'backend/apps/business/models.py',
            'backend/apps/business/serializers.py',
            'backend/apps/business/urls.py',
            'backend/apps/business/api/common.py',
            'backend/apps/business/services/common.py',
            'backend/apps/business/services/tabular.py',
            'backend/apps/core/actions.py',
            'backend/apps/core/api.py',
            'backend/apps/core/models.py',
            'backend/apps/core/periods.py',
            'backend/apps/core/permissions.py',
            'backend/config/',
            'backend/manage.py',
            'backend/requirements',
        ),
        BUSINESS,
    ),
    (
        (
            'frontend/index.html',
            'frontend/package.json',
            'frontend/package-lock.json',
            'frontend/vite.config.ts',
            'frontend/playwright.config.ts',
            'frontend/e2e/fixtures.ts',
            'frontend/e2e/role-helpers.ts',
            'frontend/e2e/settlement-helpers.ts',
            'frontend/src/App.vue',
            'frontend/src/main.ts',
            'frontend/src/style.css',
            'frontend/src/api/',
            'frontend/src/business.ts',
            'frontend/src/catalog.ts',
            'frontend/src/flows.ts',
            'frontend/src/forms.ts',
            'frontend/src/navigation.ts',
            'frontend/src/pagination.ts',
            'frontend/src/resource-ui.ts',
            'frontend/src/router.ts',
            'frontend/src/row-actions.ts',
            'frontend/src/types.ts',
            'frontend/src/plugins/',
            'frontend/src/utils/',
            'frontend/src/modules/shared.ts',
            'frontend/src/components/ActionDialog.vue',
            'frontend/src/components/FormFields.vue',
            'frontend/src/components/ListPagination.vue',
            'frontend/src/components/ModulePage.vue',
            'frontend/src/components/ModuleTabs.vue',
            'frontend/src/components/ProcessSteps.vue',
            'frontend/src/components/RecordContext.vue',
            'frontend/src/components/RemoteSelect.vue',
            'frontend/src/components/ResourcePanel.vue',
            'frontend/src/components/StatusBadge.vue',
            'frontend/src/components/TabContent.vue',
        ),
        BUSINESS,
    ),
)
# 只影响静态检查或测试运行器的配置：执行对应一侧的 lint/typecheck/build 与单测，不选业务模块。
CHECK_ONLY = (
    'backend/pyproject.toml',
    'backend/apps/business/tests/__init__.py',
    'backend/apps/core/tests/__init__.py',
    'frontend/eslint.config.js',
    'frontend/tsconfig.json',
    'frontend/tsconfig.node.json',
    'frontend/vitest.config.ts',
)


def version_only_paths(base, head, paths, read_blob):
    result = set()
    for path in paths:
        if path not in ('frontend/package.json', 'frontend/package-lock.json'):
            continue
        try:
            values = [json.loads(read_blob(ref, path)) for ref in (base, head)]
            for value in values:
                value.pop('version', None)
                if path.endswith('package-lock.json'):
                    value.get('packages', {}).get('', {}).pop('version', None)
            if values[0] == values[1]:
                result.add(path)
        except (ValueError, KeyError, TypeError):
            pass
    return result


def plan(paths, modules=(), full=False, version_only=(), release=False):
    """release=True 为发版验证：后端全部阶段、前端全部单测与运维脚本测试全部运行；
    浏览器、OTA 与安装器按发布差异选择（浏览器永不含完整业务链）。"""
    selected = set(modules)
    if selected - MODULE_TESTS.keys():
        raise ValueError('未知模块：' + ','.join(sorted(selected - MODULE_TESTS.keys())))
    backend, frontend, browser = set(), set(), set()
    unknown = []
    ops = installers = checks_backend = checks_frontend = False
    reasons = []
    for path in sorted(set(paths)):
        if path.endswith('.md') or Path(path).name in ('.gitignore', '.editorconfig', 'LICENSE'):
            continue
        stem = Path(path).stem.removesuffix('.spec')
        if path.startswith(('docker/', 'deploy/', 'install', 'scripts/')) or path in (
            'docker-compose.yml',
            '.env.example',
        ):
            ops = True
            if not path.startswith(('scripts/ci/', 'scripts/tests/test_ci_')):
                installers = True
            if stem in ('build_native_wheels', 'verify_native_wheels', 'assemble_images', 'publish_release'):
                installers = True
            if any(
                word in path for word in ('ota', 'container_runtime', 'docker/', 'docker-compose', 'release_install')
            ):
                selected.add('ota')
            continue
        if path.startswith('.github/'):
            ops = True
            if path.endswith('ci-ota.yml'):
                selected.add('ota')
            if path.endswith(('release.yml', 'release-installers.yml')):
                installers = True
            if path.endswith('ci-browser.yml'):
                selected.add('accounts')
            if path.endswith(('ci.yml', 'ci-fast.yml')):
                checks_backend = checks_frontend = True
                backend.add('apps.core.tests.test_platform')
            continue
        if path == 'backend/apps/core/version.py':
            checks_backend = True
            continue
        if path in version_only:
            checks_frontend = True
            continue
        if path.startswith('backend/'):
            checks_backend = True
            target = path[:-3].replace('/', '.').removeprefix('backend.')
            if any(target in group for group in TARGETS.values()):
                backend.add(target)
                continue
            if path.startswith('backend/apps/accounts/'):
                selected.add('accounts')
                continue
        if path.startswith('frontend/'):
            checks_frontend = True
            companion = Path(path).with_suffix('.spec.ts')
            if path.endswith(('.ts', '.vue')) and (ROOT / companion).is_file():
                frontend.add(str(companion).removeprefix('frontend/'))
            if path.endswith('.spec.ts') and (ROOT / path).is_file():
                (browser if '/e2e/' in path else frontend).add(path.removeprefix('frontend/'))
                continue
            if path.startswith('frontend/src/assets/'):
                continue
        if path in CHECK_ONLY:
            continue
        matched = {module for module, names in MODULE_FILES.items() if stem in names}
        shared = next((modules for prefixes, modules in SHARED_PATHS if path.startswith(prefixes)), None)
        if matched:
            selected.update(matched)
        elif shared is not None:
            selected.update(shared)
            if '/migrations/' in path:
                # 升级流程先备份再执行前向迁移；迁移变化须经 OTA 升级演练验证。
                selected.add('ota')
            if path.startswith('frontend/') and set(shared) == set(BUSINESS):
                browser.update(f'e2e/{name}.spec.ts' for name in SHARED_UI_BROWSERS)
            if path == 'backend/requirements.txt':
                # 运行时依赖随离线 wheelhouse 和镜像交付，安装器与升级链路同样受影响。
                installers = True
                selected.add('ota')
        else:
            unknown.append(path)
    if unknown and not modules and not full and not release:
        raise ValueError('以下共享/未知变更需显式指定 modules，不能静默漏测或启动全量：' + ', '.join(unknown))
    if unknown and release and not modules:
        # 发版不能因未登记映射的新文件中断，也不能漏测：页面用例按全部业务模块选择。
        selected.update(BUSINESS)
        reasons.append('发布差异含未登记路径，页面用例覆盖全部业务模块：' + ', '.join(unknown))
    elif unknown:
        reasons.append('显式模块范围覆盖共享/未知变更：' + ', '.join(unknown))
    backend.update(module_targets(selected))
    for module in selected:
        browser.update(f'e2e/{name}.spec.ts' for name in BROWSERS[module])
        names = MODULE_FILES[module]
        frontend.update(
            str(p.relative_to(ROOT / 'frontend'))
            for p in (ROOT / 'frontend/src').rglob('*.spec.ts')
            if any(name.casefold() in p.name.casefold() for name in names)
        )
        if module not in ('ota', 'accounts', 'reports'):
            frontend.update(('src/modules/modules.spec.ts', 'src/flows.spec.ts'))
    if selected:
        checks_backend = checks_frontend = True
    if checks_frontend and not frontend:
        # Shared frontend behavior has broad unit-level consumers, not an implicit E2E full chain.
        frontend.update(str(p.relative_to(ROOT / 'frontend')) for p in (ROOT / 'frontend/src').rglob('*.spec.ts'))
    if full:
        backend = {target for group in TARGETS.values() for target in group}
        frontend = {str(p.relative_to(ROOT / 'frontend')) for p in (ROOT / 'frontend/src').rglob('*.spec.ts')}
        browser = {str(p.relative_to(ROOT / 'frontend')) for p in (ROOT / 'frontend/e2e').glob('*.spec.ts')}
        checks_backend = checks_frontend = ops = installers = True
    if release and not full:
        backend = {target for group in TARGETS.values() for target in group}
        frontend = {str(p.relative_to(ROOT / 'frontend')) for p in (ROOT / 'frontend/src').rglob('*.spec.ts')}
        browser -= {f'e2e/{name}.spec.ts' for name in FULL_ONLY_BROWSERS}
        # OTA 与安装器只在相关改动时运行（升级代码、迁移、Docker/部署、安装与打包脚本、运行时依赖）。
        checks_backend = checks_frontend = ops = True
    if not full and 'e2e/full-chain.spec.ts' in browser:
        raise ValueError('完整业务链仅可通过显式 suite=full 运行')
    result = {
        'backend_targets': sorted(backend),
        'frontend_tests': sorted(frontend),
        'browser_specs': sorted(browser),
        'backend': checks_backend,
        'frontend': checks_frontend,
        'ops': ops,
        'installers': installers,
        'ota': 'ota' in selected or full,
        'mode': 'full' if full else 'release' if release else 'impact',
        'modules': sorted(selected),
        'reasons': reasons,
    }
    for path in [*frontend, *browser]:
        if not (ROOT / 'frontend' / path).is_file():
            raise ValueError('验证用例缺失：' + path)
    result['fingerprint'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:20]
    return result
