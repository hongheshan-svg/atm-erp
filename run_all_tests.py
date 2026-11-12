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
        # 测试登记一致性由 main() 在执行任何阶段前调用 validate_coverage() 校验。
        # Lint 覆盖全部 scripts（含 OTA、安装器与运维单测）；格式检查仍只针对已统一格式的文件。
        return [
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
                    'scripts',
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
                    'scripts/ci',
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
    parser = argparse.ArgumentParser(description='按阶段运行测试；不会迁移、初始化或重置生产数据库')
    parser.add_argument(
        '--stage', choices=['checks', *TARGETS, 'backend', 'frontend', 'browser', 'all'], default='checks'
    )
    parser.add_argument('--plan-only', action='store_true')
    args = parser.parse_args()
    validate_coverage()
    stages = ['checks', *TARGETS] if args.stage == 'backend' else [args.stage]
    if args.stage == 'all':
        stages = ['checks', *TARGETS, 'frontend', 'browser']
    if not args.plan_only and any(stage in TARGETS for stage in stages):
        if not all(os.environ.get(key) for key in ('PG_TEST_HOST', 'PG_TEST_USER', 'PG_TEST_PASSWORD')):
            parser.error('后端测试必须显式提供 PG_TEST_HOST、PG_TEST_USER 和 PG_TEST_PASSWORD。')
    for stage in stages:
        for cwd, command in commands(stage):
            print(f'{stage}: {" ".join(command)}', flush=True)
            if not args.plan_only:
                subprocess.run(command, cwd=cwd, check=True)


if __name__ == '__main__':
    main()
