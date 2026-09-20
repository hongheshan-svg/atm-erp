"""Execute structured selections without shell interpolation or empty-list full-suite fallback."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.ci.backend_test_matrix import ROOT, TARGETS


def command(kind, targets, project='desktop'):
    if not isinstance(targets, list) or any(not isinstance(item, str) for item in targets):
        raise ValueError('测试目标必须是 JSON 字符串数组')
    if not targets:
        return None
    if kind == 'backend':
        allowed = {target for group in TARGETS.values() for target in group}
        if set(targets) - allowed:
            raise ValueError('后端用例不在测试矩阵中')
        return ROOT / 'backend', [
            sys.executable,
            'manage.py',
            'test',
            *targets,
            '--noinput',
            '--settings=config.test_settings',
        ]
    prefix = 'src/' if kind == 'frontend' else 'e2e/'
    for value in targets:
        path = Path(value)
        if (
            not value.startswith(prefix)
            or '..' in path.parts
            or not value.endswith('.spec.ts')
            or not (ROOT / 'frontend' / path).is_file()
        ):
            raise ValueError('无效前端测试目标：' + value)
    if kind == 'frontend':
        return ROOT / 'frontend', ['npm', 'run', 'test', '--', *targets]
    return ROOT / 'frontend', ['npm', 'run', 'test:e2e', '--', *targets, '--project=' + project]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=('backend', 'frontend', 'browser'))
    parser.add_argument('--project', choices=('desktop', 'mobile'), default='desktop')
    args = parser.parse_args()
    result = command(args.kind, json.loads(os.environ.get('TEST_TARGETS', '[]')), args.project)
    if result:
        subprocess.run(result[1], cwd=result[0], check=True)
    else:
        print('本次范围未选择该类用例；不回退到全量。')


if __name__ == '__main__':
    main()
