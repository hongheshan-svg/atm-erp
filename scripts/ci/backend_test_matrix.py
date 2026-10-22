"""Single registry of backend test targets, shared by local runs and CI."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    'platform': (
        'apps.core.tests.test_platform',
        'apps.core.tests.test_ota',
        'apps.accounts.tests.test_auth',
        'apps.core.tests.test_setup',
    ),
    'business': (
        'apps.business.tests.test_models',
        'apps.business.tests.test_deletions',
        'apps.business.tests.test_sales',
        'apps.business.tests.test_budgets',
        'apps.business.tests.test_commercial_chain',
        'apps.business.tests.test_inventory',
        'apps.business.tests.test_execution',
        'apps.business.tests.test_import_documents',
        'apps.business.tests.test_import_feedback',
        'apps.business.tests.test_import_dedup',
        'apps.business.tests.test_money_scope',
        'apps.business.tests.test_permission_queries',
        'apps.business.tests.test_workbench',
        'apps.business.tests.test_reports',
        'apps.business.tests.test_transfers',
        'apps.business.tests.test_bom_selection',
        'apps.business.tests.test_product_coding',
        'apps.business.tests.test_review_remediation',
        'apps.business.tests.test_operational_review',
        'apps.business.tests.test_reconciliation',
        'apps.business.tests.test_bank_import',
        'apps.business.tests.test_system_reliability',
        'apps.business.tests.test_payment_terms',
        'apps.business.tests.test_hardening',
        'apps.business.tests.test_production_roles',
        'apps.business.tests.test_audit_fixes',
        'apps.business.tests.test_audit_remediation',
        'apps.business.tests.test_audit_business',
    ),
    'concurrency': (
        'apps.core.tests.test_concurrency',
        'apps.business.tests.test_concurrency',
        'apps.business.tests.test_import_concurrency',
    ),
}

# Module routing references the registry above; it is not a second target inventory.
# 跨模块的回归（权限加固、并发、导入导出、历次评审整改）挂到其实际覆盖的每个模块，
# 改动任一模块都会运行；每个登记目标至少属于一个模块，不再只在全量时才执行。
# concurrency 同时匹配 core 与 business 的并发用例。
MODULE_TESTS = {
    'sales': (
        'deletions',
        'audit_business',
        'import_dedup',
        'sales',
        'commercial_chain',
        'payment_terms',
        'audit_remediation',
        'concurrency',
        'transfers',
        'import_feedback',
        'import_concurrency',
    ),
    'projects': (
        'deletions',
        'audit_business',
        'import_dedup',
        'money_scope',
        'permission_queries',
        'import_concurrency',
        'execution',
        'budgets',
        'production_roles',
        'commercial_chain',
        'audit_remediation',
        'concurrency',
        'hardening',
        'operational_review',
        'system_reliability',
        'audit_fixes',
        'transfers',
        'import_feedback',
    ),
    'bom': (
        'deletions',
        'audit_business',
        'import_dedup',
        'permission_queries',
        'import_concurrency',
        'bom_selection',
        'import_documents',
        'import_feedback',
        'product_coding',
        'audit_remediation',
        'concurrency',
        'hardening',
        'operational_review',
        'audit_fixes',
    ),
    'purchases': (
        'deletions',
        'audit_business',
        'import_dedup',
        'money_scope',
        'permission_queries',
        'import_concurrency',
        'commercial_chain',
        'inventory',
        'budgets',
        'payment_terms',
        'review_remediation',
        'audit_remediation',
        'concurrency',
        'hardening',
        'operational_review',
        'system_reliability',
        'transfers',
        'import_feedback',
    ),
    'inventory': (
        'deletions',
        'audit_business',
        'import_dedup',
        'money_scope',
        'import_concurrency',
        'inventory',
        'review_remediation',
        'audit_remediation',
        'concurrency',
        'audit_fixes',
        'transfers',
        'import_feedback',
    ),
    'finance': (
        'deletions',
        'audit_business',
        'import_dedup',
        'money_scope',
        'import_concurrency',
        'commercial_chain',
        'reconciliation',
        'bank_import',
        'payment_terms',
        'audit_remediation',
        'concurrency',
        'hardening',
        'operational_review',
        'system_reliability',
        'audit_fixes',
        'transfers',
        'import_feedback',
    ),
    'masterdata': (
        'deletions',
        'import_dedup',
        'import_concurrency',
        'product_coding',
        'import_documents',
        'import_feedback',
        'models',
        'audit_remediation',
        'concurrency',
        'hardening',
        'transfers',
        'import_feedback',
    ),
    'accounts': ('deletions', 'auth', 'setup', 'platform', 'audit_remediation', 'concurrency', 'hardening'),
    'reports': (
        'deletions',
        'money_scope',
        'reports',
        'workbench',
        'audit_remediation',
        'hardening',
        'operational_review',
        'system_reliability',
        'transfers',
        'import_feedback',
    ),
    'ota': ('ota',),
}


def module_targets(modules):
    names = {name for module in modules for name in MODULE_TESTS[module]}
    return sorted(target for group in TARGETS.values() for target in group if target.rsplit('.test_', 1)[-1] in names)


def validate_coverage():
    actual = {
        str(path.relative_to(ROOT / 'backend')).replace('/', '.')[:-3]
        for path in (ROOT / 'backend' / 'apps').rglob('test_*.py')
    }
    registered = [target for targets in TARGETS.values() for target in targets]
    duplicates = {target for target in registered if registered.count(target) > 1}
    if set(registered) != actual or duplicates:
        raise SystemExit(
            f'测试登记与实际用例不一致：缺少={actual - set(registered)}，多余={set(registered) - actual}，重复={duplicates}'
        )
    if not all(TARGETS.values()):
        raise SystemExit('每个后端测试阶段都必须显式登记测试目标。')


def build_matrix():
    validate_coverage()
    return {
        'include': [{'name': stage, 'stage': stage, 'targets': ','.join(targets)} for stage, targets in TARGETS.items()]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args()
    matrix = json.dumps(build_matrix(), separators=(',', ':'))
    if args.github_output:
        with args.github_output.open('a') as output:
            output.write(f'matrix={matrix}\n')
    print(matrix)


if __name__ == '__main__':
    main()
