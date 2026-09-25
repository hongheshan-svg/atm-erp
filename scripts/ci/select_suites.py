"""Select affected checks; releases use the release plan; the full business chain requires an explicit request."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from scripts.ci.impact import plan, version_only_paths

SUITES = ('fast', 'browser', 'ota', 'installers')


def select(paths, suite='auto', custom=()):
    if suite == 'full':
        return set(SUITES)
    if suite == 'release':
        return required_suites(plan(paths, release=True))
    if suite == 'custom':
        if not set(custom) or set(custom) - set(SUITES):
            raise ValueError('请至少选择一个已知的测试套件')
        return set(custom)
    if suite in SUITES:
        return {suite}
    if suite != 'auto':
        raise ValueError('未知的测试套件')
    return required_suites(plan(paths))


def required_suites(scope):
    selected = {'fast'} if scope['backend'] or scope['frontend'] or scope['ops'] else set()
    selected.update(name for name in ('ota', 'installers') if scope[name])
    if scope['browser_specs']:
        selected.add('browser')
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', default='auto')
    parser.add_argument('--base')
    parser.add_argument('--head', default='HEAD')
    parser.add_argument('--projects', choices=('both', 'desktop', 'mobile'), default='both')
    parser.add_argument('--modules', default='')
    args = parser.parse_args()
    if not args.base:
        args.base = subprocess.check_output(
            ['git', 'describe', '--tags', '--abbrev=0', '--match', 'v[0-9]*', args.head + '^'],
            text=True,
        ).strip()
    paths = (
        subprocess.check_output(
            ['git', 'diff', '--name-only', '-z', args.base, args.head],
            text=True,
        ).split('\0')
        if args.base
        else []
    )
    custom = [name for name in SUITES if os.environ.get('CUSTOM_' + name.upper()) == 'true']
    scope = plan(
        [path for path in paths if path],
        modules=tuple(filter(None, args.modules.split(','))),
        full=args.suite == 'full',
        release=args.suite == 'release',
        version_only=version_only_paths(
            args.base,
            args.head,
            paths,
            lambda ref, path: subprocess.check_output(['git', 'show', f'{ref}:{path}'], text=True),
        ),
    )
    if args.suite in ('auto', 'release'):
        selected = required_suites(scope)
    else:
        selected = select([], args.suite, custom)
    if 'browser' in selected and not scope['browser_specs']:
        raise ValueError('浏览器任务需指定受影响 modules 或显式 full，禁止空目标回退全量')
    if 'fast' in selected and not (scope['backend'] or scope['frontend'] or scope['ops']):
        raise ValueError('没有受影响的快速检查目标；请使用 auto 跳过或指定 modules')
    values = {name: str(name in selected).lower() for name in SUITES}
    values['full'] = str(args.suite == 'full' and args.projects == 'both').lower()
    values['release'] = str(args.suite == 'release' and args.projects == 'both').lower()
    required = required_suites(scope)
    values['scoped'] = str(required <= selected and args.projects == 'both').lower()
    values['fingerprint'] = scope['fingerprint']
    values.update(
        {
            key: json.dumps(scope[key], separators=(',', ':'))
            for key in (
                'backend_targets',
                'frontend_tests',
                'browser_specs',
                'backend',
                'frontend',
                'ops',
                'modules',
                'reasons',
            )
        }
    )
    values['tree'] = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip()
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream:
            stream.writelines(f'{key}={value}\n' for key, value in values.items())
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as stream:
            stream.write('## Validation selection\n\n' + '\n'.join(f'- {k}: {v}' for k, v in values.items()) + '\n')
    print(json.dumps(values))


if __name__ == '__main__':
    main()
