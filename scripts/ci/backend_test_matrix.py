"""Single registry of backend test targets, shared by local runs and CI."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    'platform': ('apps.core.tests.test_platform', 'apps.accounts.tests.test_auth'),
    'business': (
        'apps.business.tests.test_models',
        'apps.business.tests.test_sales',
        'apps.business.tests.test_commercial_chain',
        'apps.business.tests.test_inventory',
        'apps.business.tests.test_execution',
        'apps.business.tests.test_import_documents',
        'apps.business.tests.test_workbench',
    ),
    'concurrency': ('apps.core.tests.test_concurrency', 'apps.business.tests.test_concurrency'),
}


def validate_coverage():
    actual = {
        str(path.relative_to(ROOT / 'backend')).replace('/', '.')[:-3]
        for path in (ROOT / 'backend' / 'apps').rglob('test_*.py')
    }
    registered = [target for targets in TARGETS.values() for target in targets]
    duplicates = {target for target in registered if registered.count(target) > 1}
    if set(registered) != actual or duplicates:
        raise SystemExit(
            f'Test registry mismatch: missing={actual - set(registered)}, stale={set(registered) - actual}, duplicate={duplicates}'
        )
    if not all(TARGETS.values()):
        raise SystemExit('Each backend stage must contain explicit test targets.')


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
