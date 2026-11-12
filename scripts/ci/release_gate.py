"""Release preflight: a release requires release validation of the exact tree, reused or rerun; no credentials in output."""

import argparse
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.ci.impact import plan, version_only_paths


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


# Release 工作流经 workflow_call 调用 ci.yml 时，子流程任务名带调用方任务 id 前缀。
NESTED_PREFIX = 'validate / '
LOOKUP_WORKERS = 8


def reusable_run(runs, repository, tree, jobs_for, fingerprint=None, nested=False):
    # 发版凭据：同一 Git tree 的 Release validation（计划指纹一致），或覆盖面更大的 Full validation。
    # 按影响范围的 Scoped validation 不含全部后端阶段与前端单测，不算发布凭据。
    # nested=True 查找此前 Release 运行内的发版验证：镜像推送或上传失败会让整次 Release 失败，但验证本身
    # 已通过；标记任务只在 CI gate 确认全部选中套件成功后运行，因此只认该任务成功，不看整次运行结论。
    prefix = NESTED_PREFIX if nested else ''
    expected = {f'{prefix}Full validation ({tree})'}
    if fingerprint:
        expected.add(f'{prefix}Release validation ({tree} {fingerprint})')
    candidates = []
    for run in runs:
        finished = run.get('status') == 'completed' if nested else run.get('conclusion') == 'success'
        if not finished or run.get('event') not in ('pull_request', 'workflow_dispatch', 'push'):
            continue
        if (run.get('head_repository') or {}).get('full_name') != repository:
            continue
        candidates.append(run['id'])
    # 每次运行的任务列表要单独请求一次。逐个查询时，没有可复用凭据（最常见）要查满 200 次、约 2～3 分钟，
    # 全部排在发版验证之前；改为并发请求。结果仍按原顺序判断，返回的是同一个最靠前的匹配，查询出错同样直接失败。
    pool = ThreadPoolExecutor(max_workers=LOOKUP_WORKERS)
    try:
        for run_id, jobs in zip(candidates, pool.map(jobs_for, candidates), strict=True):
            if any(job.get('name') in expected and job.get('conclusion') == 'success' for job in jobs):
                return run_id
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    return None


def release_base(commit, version=None):
    """发布比较基线：commit 历史中低于目标版本的最高正式 tag（预发布 tag 不算）。Release 与手动 suite=release
    共用这一选择，同一 tree 的计划指纹才会一致、凭据才可复用。未给版本时取该提交 version.py 中的版本。"""
    if version is None:
        match = re.fullmatch(r"VERSION = '(\d+\.\d+\.\d+)'", git('show', f'{commit}:backend/apps/core/version.py'))
        if not match:
            raise ValueError('无法从 backend/apps/core/version.py 读取正式版本号')
        version = match[1]
    target = tuple(map(int, version.split('.')))
    for value in git('tag', '--merged', commit, '--sort=-version:refname').splitlines():
        if re.fullmatch(r'v\d+\.\d+\.\d+', value) and tuple(map(int, value[1:].split('.'))) < target:
            return value
    raise ValueError('缺少之前的正式 tag，无法确定发布差异范围；请先明确首次发布验证基线')


def release_scope(commit, tag):
    base = release_base(commit, tag[1:])
    paths = git('diff', '--name-only', '-z', base, commit).split('\0')
    # 发版计划：浏览器按发布差异选择，未登记路径覆盖全部业务模块，不因此失败。
    return base, plan(
        [path for path in paths if path],
        release=True,
        version_only=version_only_paths(base, commit, paths, lambda ref, path: git('show', f'{ref}:{path}')),
    )


def preflight(tag, repository, force=False):
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
    base, scope = release_scope(commit, tag)
    run = None
    if not force:

        def jobs(run_id):
            return api(f'repos/{repository}/actions/runs/{run_id}/jobs?per_page=100')['jobs']

        runs = api(f'repos/{repository}/actions/workflows/ci.yml/runs?status=success&per_page=100')['workflow_runs']
        run = reusable_run(runs, repository, tree, jobs, scope['fingerprint'])
        if run is None:
            # 重新派发 Release（如草稿重试、GHCR 推送失败后）复用此前 Release 内同 tree 同计划的发版验证。
            releases = api(f'repos/{repository}/actions/workflows/release.yml/runs?status=completed&per_page=100')
            run = reusable_run(releases['workflow_runs'], repository, tree, jobs, scope['fingerprint'], nested=True)
    return {
        'tag': tag,
        'commit': commit,
        'tree': tree,
        'validate': str(run is None).lower(),
        'reused_run': str(run or ''),
        'base': base,
        'validation': 'release',
        'fingerprint': scope['fingerprint'],
        'changed_modules': ','.join(scope['modules']),
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
        stream.write('## 发布预检\n\n' + '\n'.join(f'- {k}: {v}' for k, v in result.items()) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
