"""Execute structured selections without shell interpolation or empty-list full-suite fallback."""

import argparse
import importlib.util
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


def backend_commands(targets, parallel):
    """后端分两次执行：并发阶段（多线程抢锁、带超时的事务用例）按原样串行；其余用例在 parallel 为真时
    使用 Django 多进程（每个进程一套由测试库克隆出的独立数据库）。只拆分执行方式，不增减任何用例。"""
    serial = [target for target in targets if target in TARGETS['concurrency']]
    rest = [target for target in targets if target not in TARGETS['concurrency']]
    result = []
    if rest:
        cwd, argv = command('backend', rest)
        result.append((cwd, [*argv, '--parallel=auto'] if parallel else argv))
    if serial:
        result.append(command('backend', serial))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=('backend', 'frontend', 'browser'))
    parser.add_argument('--project', choices=('desktop', 'mobile'), default='desktop')
    args = parser.parse_args()
    targets = json.loads(os.environ.get('TEST_TARGETS', '[]'))
    if args.kind == 'backend':
        # 多进程下失败用例的回溯须经 tblib 才能传回主进程；没有它时第一个失败就会中断整轮、不报其余结果，
        # 因此缺少 tblib 的环境（如本地）退回串行。
        command('backend', targets)
        runs = backend_commands(targets, importlib.util.find_spec('tblib') is not None)
    else:
        result = command(args.kind, targets, args.project)
        runs = [result] if result else []
    if not runs:
        print('本次范围未选择该类用例；不回退到全量。')
    for cwd, argv in runs:
        print(' '.join(argv[1:]), flush=True)
        subprocess.run(argv, cwd=cwd, check=True)


if __name__ == '__main__':
    main()
