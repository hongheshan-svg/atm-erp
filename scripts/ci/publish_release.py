"""Verify local and uploaded installer bytes before making a draft public."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path

from scripts.ci.release_gate import api, git


def verify(folder, tag, commit):
    names = {
        f'atm-erp-{tag}-{platform}-{mode}.zip'
        for platform in ('linux', 'macos', 'windows')
        for mode in ('docker', 'native')
    }
    checksum = folder / f'atm-erp-{tag}-SHA256SUMS.txt'
    listed = {}
    for line in checksum.read_text().splitlines():
        digest, name = line.split('  ', 1)
        if name in listed:
            raise ValueError('校验清单中存在重复条目')
        listed[name] = digest
    if set(listed) != names:
        raise ValueError('安装包数量必须正好为六个')
    for name, digest in listed.items():
        path = folder / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('安装包校验值不一致')
        with zipfile.ZipFile(path) as archive:
            if archive.testzip():
                raise ValueError('安装包归档已损坏')
            manifest = json.loads(archive.read(path.stem + '/INSTALL-MANIFEST.json'))
            if (
                manifest['version'] != tag
                or manifest['source_commit'] != commit
                or manifest['installer_commit'] != commit
            ):
                raise ValueError('安装包来源与 tag 不一致')
            prefix = path.stem + '/'
            if manifest.get('mode') not in ('native', 'docker'):
                raise ValueError('安装包缺少部署方式标识')
            if mode := manifest.get('mode'):
                if mode == 'docker':
                    if not re.fullmatch(
                        r'ghcr\.io/hongheshan-svg/atm-erp@sha256:[a-f0-9]{64}', manifest.get('docker_image', '')
                    ):
                        raise ValueError('Docker 发布必须锁定 CI 构建的镜像')
                    if set(manifest.get('docker_archives', {})) != {'amd64', 'arm64'}:
                        raise ValueError('必须同时提供两种 Docker 架构的镜像')
                    for arch, record in manifest['docker_archives'].items():
                        with archive.open(prefix + 'images/' + arch + '.tar.gz') as stream:
                            if hashlib.file_digest(stream, 'sha256').hexdigest() != record['sha256']:
                                raise ValueError('随包镜像的 digest 不一致')
                elif mode == 'native':
                    if not manifest.get('native_prebuilt') or not manifest.get('native_architectures'):
                        raise ValueError('原生发布包必须包含预编译依赖')
                    for arch in manifest['native_architectures']:
                        wheel_prefix = prefix + 'wheelhouse/' + arch + '/'
                        hashes = json.loads(archive.read(wheel_prefix + 'SHA256.json'))
                        for file, digest in hashes.items():
                            with archive.open(wheel_prefix + file) as stream:
                                if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                                    raise ValueError('原生依赖的校验值不一致')
            if path.stat().st_size > 500_000_000:
                raise ValueError('安装包超过 OTA 下载体积上限')
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [*(folder / name for name in names), checksum]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', args.tag):
        raise ValueError('必须使用正式版本 tag')
    commit = git('rev-parse', f'refs/tags/{args.tag}^{{commit}}')
    if git('rev-parse', 'HEAD') != commit:
        raise ValueError('当前检出必须正好是该 tag 对应的提交')
    expected = verify(args.folder, args.tag, commit)
    if not args.upload:
        print('六个安装包与 SHA256 清单校验通过')
        return
    repository = os.environ['GITHUB_REPOSITORY']
    releases = api(f'repos/{repository}/releases?per_page=100')
    existing = next((r for r in releases if r['tag_name'] == args.tag), None)
    if existing and not existing['draft']:
        raise ValueError('已发布的附件不能被覆盖')
    notes = Path(f'docs/releases/{args.tag}.md')
    if not existing:
        subprocess.run(
            [
                'gh',
                'release',
                'create',
                args.tag,
                '--verify-tag',
                '--draft',
                '--title',
                notes.read_text().splitlines()[0].removeprefix('# '),
                '--notes-file',
                str(notes),
            ],
            check=True,
        )
    subprocess.run(
        ['gh', 'release', 'upload', args.tag, '--clobber', *(str(args.folder / name) for name in sorted(expected))],
        check=True,
    )
    release = next(r for r in api(f'repos/{repository}/releases?per_page=100') if r['tag_name'] == args.tag)
    if not release['draft'] or {a['name'] for a in release['assets']} != set(expected):
        raise ValueError('草稿发布中存在预期之外的附件')
    for asset in release['assets']:
        if asset['state'] != 'uploaded' or asset['digest'] != 'sha256:' + expected[asset['name']]:
            raise ValueError('已上传附件的校验值与本地安装包不一致')
    if args.publish:
        subprocess.run(['gh', 'release', 'edit', args.tag, '--draft=false', '--latest'], check=True)
    print('远端安装包校验通过；' + ('已正式发布' if args.publish else '草稿已就绪'))


if __name__ == '__main__':
    main()
