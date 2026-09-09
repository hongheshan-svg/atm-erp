"""Explicit stages; never migrate, seed or reset a production database."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.ci.backend_test_matrix import TARGETS, validate_coverage

ROOT = Path(__file__).resolve().parent


def commands(stage):
    if stage == 'checks':
        return [
            (ROOT, [sys.executable, 'scripts/ci/backend_test_matrix.py']),
            (
                ROOT,
                [
                    sys.executable,
                    '-m',
                    'ruff',
                    'check',
                    '--config',
                    'backend/pyproject.toml',
                    'backend',
                    'scripts/ci/backend_test_matrix.py',
                    'scripts/backup.py',
                    'run_all_tests.py',
                ],
            ),
            (
                ROOT,
                [
                    sys.executable,
                    '-m',
                    'ruff',
                    'format',
                    '--check',
                    '--config',
                    'backend/pyproject.toml',
                    'backend',
                    'scripts/ci/backend_test_matrix.py',
                    'scripts/backup.py',
                    'run_all_tests.py',
                ],
            ),
            (ROOT / 'backend', [sys.executable, 'manage.py', 'check']),
            (ROOT / 'backend', [sys.executable, 'manage.py', 'makemigrations', '--check', '--dry-run']),
        ]
    if stage in TARGETS:
        return [
            (
                ROOT / 'backend',
                [sys.executable, 'manage.py', 'test', *TARGETS[stage], '--noinput', '--settings=config.test_settings'],
            )
        ]
    if stage == 'frontend':
        return [(ROOT / 'frontend', ['npm', 'run', task]) for task in ('lint', 'typecheck', 'test', 'build')]
    return [(ROOT / 'frontend', ['npm', 'run', 'test:e2e'])]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['checks', *TARGETS, 'frontend', 'browser', 'all'], default='checks')
    parser.add_argument('--plan-only', action='store_true')
    args = parser.parse_args()
    validate_coverage()
    stages = ['checks', *TARGETS, 'frontend', 'browser'] if args.stage == 'all' else [args.stage]
    if not args.plan_only and any(stage in TARGETS for stage in stages):
        if not all(os.environ.get(key) for key in ('PG_TEST_HOST', 'PG_TEST_USER', 'PG_TEST_PASSWORD')):
            parser.error('Backend tests require explicit PG_TEST_HOST, PG_TEST_USER and PG_TEST_PASSWORD.')
    for stage in stages:
        for cwd, command in commands(stage):
            print(f'{stage}: {" ".join(command)}', flush=True)
            if not args.plan_only:
                subprocess.run(command, cwd=cwd, check=True)


if __name__ == '__main__':
    main()
