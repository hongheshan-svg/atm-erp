"""Deterministic impact plan. Unclassified executable changes fail closed, never run full implicitly."""

import hashlib
import json
import re
from pathlib import Path

from scripts.ci.backend_test_matrix import MODULE_TESTS, TARGETS, module_targets

ROOT = Path(__file__).resolve().parents[2]
MODULE_FILES = {
    'sales': ('sales', 'amendments', 'SalesPage', 'business-date', 'progress', 'ProjectProgress'),
    'projects': (
        'projects',
        'execution',
        'milestones',
        'task_milestones',
        'task_supervision',
        'task_notices',
        'ProjectMilestones',
        'ProjectReadiness',
        'ProjectTaskSupervisors',
        'TaskNotices',
        'TaskTimeRecords',
        'budgets',
        'ProjectsPage',
        'ProjectPage',
        'BudgetPanel',
        'production',
        'progress',
        'ProjectProgress',
    ),
    'bom': (
        'bom',
        'bom_export',
        'bom-export',
        'bom_import',
        'bom_material_import',
        'BOMPage',
        'BOMDemand',
        'BOMPurchasePicker',
        'bom-purchase',
    ),
    'purchases': (
        'progress',
        'ProjectProgress',
        'supply',
        'approval',
        'purchases',
        'warehouse-lines',
        'WarehouseLines',
        'purchase_contract',
        'purchase_warranty',
        'purchase_changes',
        'purchase-changes',
        'contract_clauses',
        'payment_terms',
        'payment-terms',
        'PurchasesPage',
        'PurchaseContractPage',
        'business-date',
    ),
    'inventory': ('inventory', 'corrections', 'InventoryPage', 'IssueSlipPage', 'warehouse-lines', 'WarehouseLines'),
    'finance': (
        'progress',
        'ProjectProgress',
        'finance',
        'monthly',
        'banking',
        'bank_identity',
        'bank_import',
        'reconciliation',
        'settlement',
        'FinancePage',
        'FinanceTotals',
        'business-date',
    ),
    'masterdata': ('manual-codes', 'masterdata', 'product-categories', 'MasterdataPage'),
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
    'sales': (
        'document-preview',
        'process-progress',
        'admin-deletion',
        'sales-role',
        'attachments',
        'industry-forms',
        'import-surface-audit',
    ),
    'projects': (
        'project-milestones',
        'document-preview',
        'process-progress',
        'admin-deletion',
        'import-audit-real',
        'production-role',
        'state-actions-audit',
        'attachments',
        'coding-rules',
        'industry-forms',
        'specialist-roles',
        'import-surface-audit',
    ),
    'bom': (
        'bom-export',
        'admin-deletion',
        'bom-selection',
        'bom-purchase-layout',
        'specialist-roles',
        'import-feedback',
    ),
    'purchases': (
        'purchase-changes',
        'purchase-contract',
        'document-preview',
        'process-progress',
        'admin-deletion',
        'payment-terms',
        'review-remediation',
        'warehouse-lines',
        'attachments',
        'hardening-ui',
        'specialist-roles',
        'import-surface-audit',
    ),
    'inventory': ('cancel-actions-audit', 'import-surface-audit', 'warehouse-lines'),
    'finance': (
        'document-preview',
        'process-progress',
        'admin-deletion',
        'reconciliation',
        'bank-review-audit',
        'import-surface-audit',
        'import-audit-real',
        'usability-finance',
    ),
    'masterdata': (
        'manual-codes',
        'admin-deletion',
        'product-coding',
        'account-masterdata-audit',
        'transfers',
        'import-surface-audit',
    ),
    'accounts': (
        'admin-deletion',
        'initial-password',
        'settings',
        'login',
        'setup',
        'account-masterdata-audit',
        'role-page-audit',
        'multi-role',
        'specialist-roles',
        'coding-rules',
        'navigation-dialog',
    ),
    'reports': ('reports', 'hardening-ui', 'transfers'),
    'ota': ('system-upgrade', 'navigation-dialog'),
}
# 完整业务链只在显式 full 时运行，普通发版不包含，不属于任何模块。
FULL_ONLY_BROWSERS = ('full-chain',)
BUSINESS = ('sales', 'projects', 'bom', 'purchases', 'inventory', 'finance', 'masterdata', 'accounts', 'reports')
# 公共界面组件改动时额外运行的页面级用例：导航、页签、分页、各页面概览和各岗位逐页巡检。
SHARED_UI_BROWSERS = (
    'admin-deletion',
    'navigation-dialog',
    'module-tabs',
    'pagination-layout',
    'ui-concepts',
    'role-page-audit',
    'usability-forms',
    'role-pages-usability',
    'remote-select',
)
# 经过审阅的共享路径映射：这些文件被多个模块直接调用，改动时运行所列模块的全部关联用例。
# 按前缀匹配、先匹配先用；只在文件名未命中 MODULE_FILES 时使用。新增的未登记路径仍然失败，不静默漏测。
SHARED_PATHS = (
    # This API only downloads BOM rows; generic request/download paths remain shared below.
    (('frontend/src/api/bom.ts', 'frontend/src/api/bom.spec.ts'), ('bom',)),
    (
        (
            'backend/apps/business/services/deletions.py',
            'backend/apps/business/api/deletions.py',
            'frontend/src/modules/deletions.ts',
            'frontend/src/components/RecordDeletionDialog.vue',
        ),
        BUSINESS,
    ),
    (
        (
            'backend/apps/business/services/documents.py',
            'backend/apps/business/attachments.py',
            'backend/apps/business/document_preview.py',
            'frontend/src/document-preview.ts',
            'frontend/src/components/DocumentPreview.vue',
            'frontend/src/components/PdfPreview.vue',
            'frontend/pdf-assets.ts',
            'frontend/e2e/fixtures/document-preview/',
            'frontend/src/components/AttachmentDialog.vue',
            'frontend/src/components/AttachmentDialog.spec.ts',
            'frontend/src/components/AttachmentRemovalDialog.vue',
            'frontend/src/components/InlineDocumentField.vue',
            'frontend/src/modules/documents.ts',
        ),
        ('sales', 'purchases', 'projects', 'finance'),
    ),
    (
        (
            'backend/apps/business/services/transfers.py',
            'backend/apps/business/services/import_guides.py',
            'backend/apps/business/services/import_feedback.py',
            'backend/apps/business/services/import_dedup.py',
            'backend/apps/business/services/import_locks.py',
            'frontend/src/components/ImportFeedback.vue',
            'frontend/src/components/TransferTools.vue',
        ),
        ('masterdata', 'sales', 'projects', 'purchases', 'inventory', 'finance', 'reports', 'bom'),
    ),
    (
        # 管理员历史数据只读核查：读取收付款、银行、采购质保与交付的在办规则，入口在设置页。
        (
            'backend/apps/business/services/data_checks.py',
            'backend/apps/business/api/data_checks.py',
            'frontend/src/components/DataChecks.vue',
        ),
        ('finance', 'purchases', 'projects', 'accounts'),
    ),
    (('frontend/src/utils/batch-selection.ts', 'frontend/src/utils/batch-selection.spec.ts'), BUSINESS),
    (('frontend/src/batch-mode.ts', 'frontend/src/batch-mode.spec.ts'), BUSINESS),
    (('frontend/src/components/SupplierMonthly.vue',), ('finance',)),
    (('frontend/src/components/ProjectAttention.vue',), ('projects', 'bom', 'purchases')),
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
            'backend/apps/core/error_messages.py',
            'backend/apps/core/models.py',
            'backend/apps/core/periods.py',
            'backend/apps/core/permissions.py',
            'backend/apps/core/request_id.py',
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
            'frontend/e2e/remote-select-helpers.ts',
            'frontend/e2e/settlement-helpers.ts',
            'frontend/src/App.vue',
            'frontend/src/main.ts',
            'frontend/src/style.css',
            'frontend/src/api/',
            'frontend/src/business.ts',
            'frontend/src/catalog.ts',
            'frontend/src/flows.ts',
            'frontend/src/forms.ts',
            'frontend/src/form-experience.ts',
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
            'frontend/src/components/BusinessTable.vue',
            'frontend/src/components/TableScroll.vue',
            'frontend/src/components/ListPagination.vue',
            'frontend/src/components/ModulePage.vue',
            'frontend/src/components/ModuleTabs.vue',
            'frontend/src/components/ProcessSteps.vue',
            'frontend/src/components/RecordContext.vue',
            'frontend/src/components/RemoteSelect.vue',
            'frontend/src/components/QuickReferenceCreate.vue',
            'frontend/src/components/RoleTaskGuide.vue',
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
    # 开发依赖只在运行时依赖之外固定 Ruff 版本；运行时依赖 requirements.txt 仍走共享映射。
    'backend/requirements-dev.txt',
    'backend/apps/business/tests/__init__.py',
    'backend/apps/core/tests/__init__.py',
    'frontend/eslint.config.js',
    'frontend/tsconfig.json',
    'frontend/tsconfig.node.json',
    'frontend/vitest.config.ts',
)
# 本地 Git 钩子与仓库元数据：不进入镜像、安装包或 CI 运行路径，只运行运维脚本测试（含本计划自检）。
# .pre-commit-config.yaml 已删除，保留登记使包含删除的 PR 与发版差异仍可归类。
OPS_ONLY = ('.githooks/', '.pre-commit-config.yaml', '.gitattributes', '.codex')
# 真实升级演练（ci-ota）直接执行或导入这些文件：ota_smoke 运行 install.sh（其中调用 network_check.py），
# 宿主机升级先调用 backup.py 备份，直接 Compose 启动演练读取 .env.example；.dockerignore 决定镜像内容，
# restore_uploads.py 由 Dockerfile 复制进镜像。两个容器演练导入 package_release 生成 Compose；原生升级演练先用
# native_install（及其 native_service）安装，并用 build_native_wheels 准备离线依赖。
# 文件名含 ota、container_runtime、release_install 的脚本及 docker/、Compose 另按名称选择，见 plan()。
OTA_PATHS = (
    'install.sh',
    'scripts/backup.py',
    '.env.example',
    '.dockerignore',
    'scripts/network_check.py',
    'scripts/restore_uploads.py',
    'scripts/package_release.py',
    'scripts/native_install.py',
    'scripts/native_service.py',
    'scripts/ci/build_native_wheels.py',
    'scripts/tests/direct_compose_smoke.py',
)
# 安装器流程（release-installers.yml）在三平台运行的运维单测；其余单测只在 fast/ops 运行。两处名单由测试核对一致。
INSTALLER_TESTS = (
    'scripts/tests/test_native_install.py',
    'scripts/tests/test_native_service.py',
    'scripts/tests/test_direct_compose.py',
    'scripts/tests/test_container_ota.py',
    'scripts/tests/test_ota_service.py',
    'scripts/tests/test_release_install.py',
    'scripts/tests/test_network_check.py',
)
# 不进入安装器流程的运维文件：独立的备份巡检工具，以及只由 ci-ota 运行的升级演练脚本。安装器流程既不执行
# 也不导入它们（由测试按引用关系核对）。scripts/ 下其他文件，包括新增文件，仍默认运行安装器，不静默漏测。
NOT_INSTALLER_PATHS = (
    'scripts/backup_cycle.py',
    'scripts/ops_check.py',
    'scripts/tests/ota_smoke.py',
    'scripts/tests/ota_native_smoke.py',
    'scripts/tests/direct_compose_smoke.py',
)
# CI 运行器：run_selected 生成后端、前端单测与浏览器命令，select_suites 生成计划输出与浏览器分片矩阵。
# 与 ci-fast.yml、ci-browser.yml 同样处理，本次改动就实际执行一遍各类命令，而不是只跑运维单测。
RUNNER_PATHS = ('scripts/ci/run_selected.py', 'scripts/ci/select_suites.py')
# docs 下不可执行的图片和 Office/PDF 文档只作说明，与 Markdown 一样不选择测试；其他类型仍须登记。
DOC_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.pdf', '.docx', '.pptx', '.xlsx')


def words(name):
    """把文件名拆成小写单词：按非字母数字字符和驼峰边界切分，如 FinanceTotals.audit → finance/totals/audit。"""
    return [
        word.lower()
        for part in re.split(r'[^A-Za-z0-9]+', name)
        for word in re.findall(r'[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+', part)
    ]


def contains(haystack, needle):
    """按整词连续匹配：模块名 ota 不再因子串命中 FinanceTotals，upgrade 仍命中 SystemUpgrade。"""
    return bool(needle) and any(
        haystack[index : index + len(needle)] == needle for index in range(len(haystack) - len(needle) + 1)
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
    ops = installers = checks_backend = checks_frontend = ota_suite = False
    reasons = []
    for path in sorted(set(paths)):
        if path.endswith('.md') or Path(path).name in ('.gitignore', '.editorconfig', 'LICENSE'):
            continue
        if path.startswith('docs/') and Path(path).suffix.lower() in DOC_SUFFIXES:
            # 文档截图与附件仅作说明；可执行文件仍须经过影响范围判定。
            continue
        if path.startswith(OPS_ONLY):
            ops = True
            continue
        stem = Path(path).stem.removesuffix('.spec')
        if path.startswith(('docker/', 'deploy/', 'install', 'scripts/')) or path in (
            'docker-compose.yml',
            '.env.example',
            '.dockerignore',
        ):
            ops = True
            if path.startswith('scripts/tests/test_') and path.endswith('.py'):
                # 运维单测本身只在 fast/ops 运行（安装器另跑登记的几项）；升级演练不运行单测，改单测不启动它。
                installers = installers or path in INSTALLER_TESTS
                continue
            if not path.startswith('scripts/ci/') and path not in NOT_INSTALLER_PATHS:
                installers = True
            if stem in ('build_native_wheels', 'verify_native_wheels', 'assemble_images', 'publish_release'):
                installers = True
            if path in RUNNER_PATHS:
                selected.add('accounts')
                checks_backend = checks_frontend = True
                backend.add('apps.core.tests.test_platform')
            if path in OTA_PATHS or any(
                word in path for word in ('ota', 'container_runtime', 'docker/', 'docker-compose', 'release_install')
            ):
                selected.add('ota')
                ota_suite = True
            continue
        if path.startswith('.github/') or path == 'run_all_tests.py':
            ops = True
            if path.endswith('ci-ota.yml'):
                selected.add('ota')
                ota_suite = True
            if path.endswith(('release.yml', 'release-installers.yml')):
                installers = True
            if path.endswith('ci-browser.yml'):
                selected.add('accounts')
            # ci-fast 的后端任务通过 run_all_tests.py 执行静态检查，与 ci-fast.yml 同样处理。
            if path.endswith(('ci.yml', 'ci-fast.yml')) or path == 'run_all_tests.py':
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
            if path.endswith('.spec.ts') and not (ROOT / path).exists():
                # 已删除（或改名前）的用例文件无法再运行；替代用例与被测代码按各自路径照常选择。
                reasons.append('已删除用例，不再运行：' + path)
                continue
            if path.endswith('.spec.ts') and (ROOT / path).is_file():
                if not full and path in {f'frontend/e2e/{name}.spec.ts' for name in FULL_ONLY_BROWSERS}:
                    reasons.append('完整业务链用例已适配，但仅在显式 suite=full 时执行：' + path)
                    continue
                (browser if '/e2e/' in path else frontend).add(path.removeprefix('frontend/'))
                continue
            if path.startswith('frontend/src/assets/'):
                continue
        if path in CHECK_ONLY:
            continue
        matched = {module for module, names in MODULE_FILES.items() if stem in names}
        shared = next((modules for prefixes, modules in SHARED_PATHS if path.startswith(prefixes)), None)
        # 文件名词干可能与模块同名（如 config/settings.py 命中 accounts），若共享组已覆盖该模块，则以共享组为准，避免被截走。
        if shared is not None and (not matched or set(matched) <= set(shared)):
            selected.update(shared)
            # 升级接口模块（ota）与真实升级演练（OTA 套件）分开：后端的升级代码、迁移命令与架构保护会在演练中
            # 执行，同时启动演练；升级页面和前端接口文件只跑升级相关的单测与页面用例，演练不经过界面。
            if 'ota' in shared and not path.startswith('frontend/'):
                ota_suite = True
            if '/migrations/' in path:
                # 升级流程先备份再执行前向迁移；迁移变化须经 OTA 升级演练验证。
                selected.add('ota')
                ota_suite = True
            if path.startswith('frontend/') and set(shared) == set(BUSINESS):
                browser.update(f'e2e/{name}.spec.ts' for name in SHARED_UI_BROWSERS)
            if path == 'backend/requirements.txt':
                # 运行时依赖随离线 wheelhouse 和镜像交付，安装器与升级链路同样受影响。
                installers = True
                selected.add('ota')
                ota_suite = True
        elif matched:
            selected.update(matched)
            if 'ota' in matched and not path.startswith('frontend/'):
                ota_suite = True
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
        names = [words(name) for name in MODULE_FILES[module]]
        frontend.update(
            str(p.relative_to(ROOT / 'frontend'))
            for p in (ROOT / 'frontend/src').rglob('*.spec.ts')
            if any(contains(words(p.name.removesuffix('.spec.ts')), name) for name in names)
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
        'ota': ota_suite or 'ota' in modules or full,
        'mode': 'full' if full else 'release' if release else 'impact',
        'modules': sorted(selected),
        'reasons': reasons,
    }
    for path in [*frontend, *browser]:
        if not (ROOT / 'frontend' / path).is_file():
            raise ValueError('验证用例缺失：' + path)
    result['fingerprint'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:20]
    return result
