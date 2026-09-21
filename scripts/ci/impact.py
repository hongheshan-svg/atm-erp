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
    'sales': ('sales-role',),
    'projects': ('production-role', 'state-actions-audit'),
    'bom': ('bom-selection', 'bom-purchase-layout'),
    'purchases': ('payment-terms', 'review-remediation'),
    'inventory': ('cancel-actions-audit',),
    'finance': ('reconciliation', 'bank-review-audit'),
    'masterdata': ('product-coding',),
    'accounts': ('initial-password', 'settings', 'login'),
    'reports': ('reports',),
    'ota': ('system-upgrade',),
}


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


def plan(paths, modules=(), full=False, version_only=()):
    selected = set(modules)
    if selected - MODULE_TESTS.keys():
        raise ValueError('未知模块：' + ','.join(sorted(selected - MODULE_TESTS.keys())))
    backend, frontend, browser = set(), set(), set()
    unknown = []
    ops = installers = checks_backend = checks_frontend = False
    reasons = []
    for path in sorted(set(paths)):
        if path.endswith('.md') or path in ('.gitignore', '.editorconfig', 'LICENSE'):
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
        matched = {module for module, names in MODULE_FILES.items() if stem in names}
        if matched:
            selected.update(matched)
        else:
            unknown.append(path)
    if unknown and not modules and not full:
        raise ValueError('以下共享/未知变更需显式指定 modules，不能静默漏测或启动全量：' + ', '.join(unknown))
    if unknown:
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
        'modules': sorted(selected),
        'reasons': reasons,
    }
    for path in [*frontend, *browser]:
        if not (ROOT / 'frontend' / path).is_file():
            raise ValueError('验证用例缺失：' + path)
    result['fingerprint'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:20]
    return result
