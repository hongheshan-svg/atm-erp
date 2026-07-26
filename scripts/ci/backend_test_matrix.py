"""Generate the GitHub Actions backend test matrix and guard app coverage."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django = importlib.import_module('django')
apps = importlib.import_module('django.apps').apps


GROUPS = (
    {
        'name': 'platform, permissions and accounts',
        'modules': ('apps.core', 'apps.core.workflow', 'apps.accounts', 'apps.ai'),
        'targets': ('apps.core.tests', 'apps.core.workflow', 'apps.accounts.tests', 'apps.ai.tests'),
    },
    {
        'name': 'projects, master data and sales',
        'modules': ('apps.masterdata', 'apps.projects', 'apps.sales'),
        'targets': ('apps.masterdata.tests', 'apps.projects.tests', 'apps.sales.tests'),
    },
    {
        'name': 'supply chain, inventory and production',
        'modules': ('apps.purchase', 'apps.inventory', 'apps.production'),
        'targets': ('apps.purchase.tests', 'apps.inventory.tests', 'apps.production.tests'),
    },
    {
        'name': 'finance, reporting and office',
        'modules': ('apps.finance', 'apps.reports', 'apps.analytics', 'apps.oa'),
        'targets': ('apps.finance.tests', 'apps.reports.tests', 'apps.analytics.tests', 'apps.oa'),
    },
)


def validate_coverage() -> None:
    django.setup()
    installed = {config.name for config in apps.get_app_configs() if config.name.startswith('apps.')}
    covered = [module for group in GROUPS for module in group['modules']]
    duplicates = sorted({module for module in covered if covered.count(module) > 1})
    missing = sorted(installed - set(covered))
    unexpected = sorted(set(covered) - installed)

    if duplicates or missing or unexpected:
        details = []
        if duplicates:
            details.append(f'duplicate modules: {", ".join(duplicates)}')
        if missing:
            details.append(f'uncovered installed modules: {", ".join(missing)}')
        if unexpected:
            details.append(f'unknown modules: {", ".join(unexpected)}')
        raise SystemExit('Backend test matrix coverage is invalid: ' + '; '.join(details))


def build_matrix() -> dict[str, list[dict[str, str]]]:
    return {
        'include': [
            {
                'name': group['name'],
                'targets': ','.join(group['targets']),
            }
            for group in GROUPS
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args()

    validate_coverage()
    matrix = build_matrix()
    encoded = json.dumps(matrix, separators=(',', ':'))

    for group in GROUPS:
        print(f'{group["name"]}: {", ".join(group["modules"])}')

    if args.github_output:
        with args.github_output.open('a', encoding='utf-8') as output:
            output.write(f'matrix={encoded}\n')
    else:
        print(encoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
