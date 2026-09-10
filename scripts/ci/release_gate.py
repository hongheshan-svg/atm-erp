"""Release preflight and exact-tree validation reuse, with no credentials in output."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def reusable_run(runs, repository, tree, jobs_for):
    expected = f'Full validation ({tree})'
    for run in runs:
        if run.get('conclusion') != 'success' or run.get('event') not in ('pull_request', 'workflow_dispatch', 'push'):
            continue
        if (run.get('head_repository') or {}).get('full_name') != repository:
            continue
        if any(job.get('name') == expected and job.get('conclusion') == 'success' for job in jobs_for(run['id'])):
            return run['id']
    return None


def preflight(tag, repository, force=False):
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise ValueError('A stable vMAJOR.MINOR.PATCH tag is required')
    commit = git('rev-parse', f'refs/tags/{tag}^{{commit}}')
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'origin/main'], check=True)
    version_file = git('show', f'{commit}:backend/apps/core/version.py')
    if version_file.strip() != f"VERSION = '{tag[1:]}'":
        raise ValueError('Tag and backend version differ')
    for name in ('frontend/package.json', 'frontend/package-lock.json'):
        if json.loads(git('show', f'{commit}:{name}'))['version'] != tag[1:]:
            raise ValueError('Tag and frontend version differ')
    notes = git('show', f'{commit}:docs/releases/{tag}.md')
    if '{{TAG}}' in notes or '## 📥 Installation' not in notes or '## 📚 Documentation' not in notes:
        raise ValueError('Release notes must include actual installation and documentation sections')
    # Published releases and their immutable assets are never overwritten by this workflow.
    releases = api(f'repos/{repository}/releases?per_page=100')
    if any(r['tag_name'] == tag and not r['draft'] for r in releases):
        raise ValueError('This version is already published; use a new tag')
    tree = git('rev-parse', f'{commit}^{{tree}}')
    run = None
    if not force:
        runs = api(f'repos/{repository}/actions/workflows/ci.yml/runs?status=success&per_page=100')['workflow_runs']
        run = reusable_run(
            runs,
            repository,
            tree,
            lambda run_id: api(f'repos/{repository}/actions/runs/{run_id}/jobs?per_page=100')['jobs'],
        )
    return {
        'tag': tag,
        'commit': commit,
        'tree': tree,
        'validate': str(run is None).lower(),
        'reused_run': str(run or ''),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    result = preflight(args.tag, os.environ['GITHUB_REPOSITORY'], args.force)
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream:
        stream.writelines(f'{key}={value}\n' for key, value in result.items())
    with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as stream:
        stream.write('## Release preflight\n\n' + '\n'.join(f'- {k}: {v}' for k, v in result.items()) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
