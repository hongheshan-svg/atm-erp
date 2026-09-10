"""Conservative change routing; unknown executable changes select the full suite."""

import argparse
import json
import os
import subprocess
from pathlib import Path

SUITES = ('fast', 'browser', 'ota', 'installers')


def select(paths, suite='auto', custom=()):
    if suite == 'full':
        return set(SUITES)
    if suite == 'custom':
        if not set(custom) or set(custom) - set(SUITES):
            raise ValueError('Select at least one known suite')
        return set(custom)
    if suite in SUITES:
        return {suite}
    if suite != 'auto':
        raise ValueError('Unknown suite')
    selected = set()
    for path in paths:
        if path.startswith(('.github/workflows/', 'scripts/ci/')) or path in (
            'backend/apps/core/version.py',
            'frontend/package.json',
            'frontend/package-lock.json',
            'run_all_tests.py',
        ):
            selected.update(SUITES)
        elif path.startswith('backend/'):
            selected.update(('fast', 'browser'))
            if '/migrations/' in path or path.startswith(('backend/config/', 'backend/apps/core/')):
                selected.add('ota')
            if path.startswith('backend/requirements'):
                selected.update(SUITES)
        elif path.startswith('frontend/'):
            selected.update(('fast', 'browser'))
        elif (
            path.startswith(
                ('docker/', 'install', 'scripts/native', 'scripts/package', 'scripts/ota', 'scripts/backup')
            )
            or path == 'docker-compose.yml'
        ):
            selected.update(SUITES)
        elif path.startswith('scripts/tests/'):
            selected.add('fast')
            if 'ota' in path:
                selected.add('ota')
            if 'native' in path or 'install' in path:
                selected.add('installers')
        elif path.startswith('scripts/'):
            selected.update(SUITES)
        elif path.startswith('docs/') or path.endswith('.md') or path in ('.gitignore', 'LICENSE', '.editorconfig'):
            continue
        else:
            selected.update(SUITES)
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', default='auto')
    parser.add_argument('--base')
    parser.add_argument('--head', default='HEAD')
    parser.add_argument('--projects', choices=('both', 'desktop', 'mobile'), default='both')
    args = parser.parse_args()
    if args.suite == 'auto' and not args.base:
        raise ValueError('Automatic selection requires the PR base commit')
    paths = (
        subprocess.check_output(
            ['git', 'diff', '--name-only', '-z', args.base, args.head],
            text=True,
        ).split('\0')
        if args.base
        else []
    )
    custom = [name for name in SUITES if os.environ.get('CUSTOM_' + name.upper()) == 'true']
    selected = select([path for path in paths if path], args.suite, custom)
    values = {name: str(name in selected).lower() for name in SUITES}
    values['full'] = str(selected == set(SUITES) and args.projects == 'both').lower()
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
