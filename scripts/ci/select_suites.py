"""PRs use fast checks; full validation is explicitly requested for releases."""

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
    for path in paths:
        if path.startswith('docs/') or path.endswith('.md') or path in ('.gitignore', 'LICENSE', '.editorconfig'):
            continue
        return {'fast'}
    return set()


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
