"""Release preflight and exact-tree validation reuse, with no credentials in output."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

from scripts.ci.impact import plan, version_only_paths


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def reusable_run(runs, repository, tree, jobs_for, fingerprint=None):
    expected = {f'Full validation ({tree})'}
    if fingerprint:
        expected.add(f'Scoped validation ({tree} {fingerprint})')
    for run in runs:
        if run.get('conclusion') != 'success' or run.get('event') not in ('pull_request', 'workflow_dispatch', 'push'):
            continue
        if (run.get('head_repository') or {}).get('full_name') != repository:
            continue
        if any(job.get('name') in expected and job.get('conclusion') == 'success' for job in jobs_for(run['id'])):
            return run['id']
    return None


def release_scope(commit, tag, modules=()):
    tags = git('tag', '--merged', commit, '--sort=-version:refname').splitlines()
    version = tuple(map(int, tag[1:].split('.')))
    base = next(
        (
            value
            for value in tags
            if re.fullmatch(r'v\d+\.\d+\.\d+', value) and tuple(map(int, value[1:].split('.'))) < version
        ),
        None,
    )
    if not base:
        raise ValueError('缺少之前的正式 tag，无法确定发布差异范围；请先明确首次发布验证基线')
    paths = git('diff', '--name-only', '-z', base, commit).split('\0')
    return base, plan(
        [path for path in paths if path],
        modules=modules,
        version_only=version_only_paths(base, commit, paths, lambda ref, path: git('show', f'{ref}:{path}')),
    )


def preflight(tag, repository, force=False, modules=()):
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise ValueError('必须使用 v主版本.次版本.修订号 形式的正式 tag')
    commit = git('rev-parse', f'refs/tags/{tag}^{{commit}}')
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'origin/main'], check=True)
    version_file = git('show', f'{commit}:backend/apps/core/version.py')
    if version_file.strip() != f"VERSION = '{tag[1:]}'":
        raise ValueError('tag 与后端版本号不一致')
    for name in ('frontend/package.json', 'frontend/package-lock.json'):
        if json.loads(git('show', f'{commit}:{name}'))['version'] != tag[1:]:
            raise ValueError('tag 与前端版本号不一致')
    notes = git('show', f'{commit}:docs/releases/{tag}.md')
    if '{{TAG}}' in notes or '## 📥 Installation' not in notes or '## 📚 Documentation' not in notes:
        raise ValueError('发布说明必须包含实际的 Installation 与 Documentation 区块')
    # Published releases and their immutable assets are never overwritten by this workflow.
    releases = api(f'repos/{repository}/releases?per_page=100')
    if any(r['tag_name'] == tag and not r['draft'] for r in releases):
        raise ValueError('该版本已发布，请改用新的 tag')
    tree = git('rev-parse', f'{commit}^{{tree}}')
    base, scope = release_scope(commit, tag, modules)
    run = None
    if not force:
        runs = api(f'repos/{repository}/actions/workflows/ci.yml/runs?status=success&per_page=100')['workflow_runs']
        run = reusable_run(
            runs,
            repository,
            tree,
            lambda run_id: api(f'repos/{repository}/actions/runs/{run_id}/jobs?per_page=100')['jobs'],
            scope['fingerprint'],
        )
    return {
        'tag': tag,
        'commit': commit,
        'tree': tree,
        'validate': str(run is None).lower(),
        'reused_run': str(run or ''),
        'base': base,
        'fingerprint': scope['fingerprint'],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--modules', default='')
    args = parser.parse_args()
    result = preflight(
        args.tag, os.environ['GITHUB_REPOSITORY'], args.force, tuple(filter(None, args.modules.split(',')))
    )
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream:
        stream.writelines(f'{key}={value}\n' for key, value in result.items())
    with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as stream:
        stream.write('## 发布预检\n\n' + '\n'.join(f'- {k}: {v}' for k, v in result.items()) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
