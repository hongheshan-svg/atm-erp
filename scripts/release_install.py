"""Use immutable CI-built artifacts; release installs never compile application code."""
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import tarfile
from pathlib import Path

REPOSITORY = 'ghcr.io/hongheshan-svg/atm-erp'


def manifest(root):
    path = root / 'INSTALL-MANIFEST.json'
    return json.loads(path.read_text()) if path.exists() else None


def digest_file(path, expected):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError(f'发布文件校验失败：{path.name}')


def docker_image(root):
    data = manifest(root)
    if not data or data.get('mode') != 'docker' or not data.get('docker_image'):
        raise ValueError('此发布包没有预构建镜像，请使用新版发布包；不会回退为本地构建')
    image = data['docker_image']
    if not re.fullmatch(re.escape(REPOSITORY) + r'@sha256:[a-f0-9]{64}', image):
        raise ValueError('发布镜像必须来自固定仓库并锁定 digest')
    return image, data


def archive_image_ids(path, expected, arch):
    """Resolve config/manifest/index identities from the same verified docker-save archive.

    Classic Docker identifies an image by its config; containerd uses its manifest
    or index. Only accept content-addressed aliases connected to the expected image,
    never a tag from docker load output or an unrelated image already on the host.
    """
    with tarfile.open(path, 'r:*') as archive:
        members = {}
        for member in archive.getmembers():
            if member.name in members:
                raise ValueError('镜像归档包含重复条目')
            members[member.name] = member

        def metadata(name):
            member = members.get(name)
            if not member or not member.isfile() or member.size > 1024 * 1024:
                raise ValueError('镜像归档元数据缺失或非法')
            with archive.extractfile(member) as stream:
                content = stream.read()
            return 'sha256:' + hashlib.sha256(content).hexdigest(), json.loads(content)

        identities = {}
        _, entries = metadata('manifest.json')
        for entry in entries:
            config_path = entry['Config']
            if not re.fullmatch(r'(?:blobs/sha256/[a-f0-9]{64}|[a-f0-9]{64}\.json)', config_path):
                raise ValueError('镜像归档配置路径非法')
            config_id, config = metadata(config_path)
            if config_path.rsplit('/', 1)[-1].removesuffix('.json') != config_id.removeprefix('sha256:'):
                raise ValueError('镜像归档配置校验失败')
            if config.get('os') == 'linux' and config.get('architecture') == arch:
                identities[config_id] = {config_id}

        def visit(descriptor, parents=()):
            digest = descriptor.get('digest', '')
            if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest) or digest in parents or len(parents) >= 8:
                raise ValueError('镜像归档描述符非法')
            platform_info = descriptor.get('platform')
            if platform_info and (platform_info.get('os') != 'linux' or platform_info.get('architecture') != arch):
                return  # Other platforms and attestations are not runnable target images.
            name = 'blobs/sha256/' + digest.removeprefix('sha256:')
            if name not in members:
                return  # A saved multi-platform index may reference platforms not exported.
            actual, value = metadata(name)
            if actual != digest:
                raise ValueError('镜像归档描述符校验失败')
            chain = (*parents, digest)
            if 'manifests' in value:
                for child in value['manifests']:
                    visit(child, chain)
            else:
                config_id = value.get('config', {}).get('digest')
                if config_id in identities:
                    identities[config_id].update(chain)

        if 'index.json' in members:
            _, index = metadata('index.json')
            for descriptor in index['manifests']:
                visit(descriptor)
            # containerd imports the OCI layout when present, not manifest.json.
            identities = {config: ids for config, ids in identities.items() if len(ids) > 1}
        matches = [ids for ids in identities.values() if expected in ids]
        if len(matches) != 1:
            raise ValueError('镜像归档身份或架构不符')
        ambiguous = set().union(*(ids for ids in identities.values() if ids is not matches[0]))
        return [expected, *sorted(matches[0] - ambiguous - {expected})]


def prepare_docker(root):
    image, data = docker_image(root)
    arch = subprocess.check_output(['docker', 'info', '--format', '{{.Architecture}}'], text=True).strip()
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(arch, arch)
    record = data.get('docker_archives', {}).get(arch)
    if not record or not re.fullmatch(r'sha256:[a-f0-9]{64}', record.get('image_id', '')):
        raise ValueError('没有匹配 Docker 架构的预构建镜像')
    path = root / 'images' / f'{arch}.tar.gz'
    if not path.exists():
        subprocess.run(['docker', 'pull', image], check=True)
        return image
    digest_file(path, record['sha256'])
    identities = archive_image_ids(path, record['image_id'], arch)
    subprocess.run(['docker', 'load', '-i', str(path)], check=True)
    for identity in identities:
        try:
            result = subprocess.check_output(
                ['docker', 'image', 'inspect', identity, '--format', '{{.Id}} {{.Os}} {{.Architecture}}'],
                text=True, stderr=subprocess.PIPE,
            ).strip().split()
        except subprocess.CalledProcessError:
            continue  # This store may use a different content-addressed identity.
        if len(result) != 3 or result[0] not in identities or result[1:] != ['linux', arch]:
            raise ValueError('导入后的镜像身份或架构不符')
        return result[0]
    raise ValueError('导入后未找到经校验的镜像，请检查 Docker 镜像存储及升级日志')


def set_image(config, image):
    content = config.read_text(encoding='utf-8-sig')
    content = re.sub(r'^LEAN_IMAGE=.*\n?', '', content, flags=re.M)
    temporary = config.with_name(config.name + '.image.tmp')
    temporary.write_text(content.rstrip() + '\nLEAN_IMAGE=' + image + '\n', encoding='utf-8')
    temporary.chmod(0o600)
    if os.name == 'nt':
        identity = subprocess.check_output(['whoami'], text=True).strip()
        subprocess.run(['icacls', str(temporary), '/inheritance:r', '/grant:r', identity + ':F'], check=True, stdout=subprocess.DEVNULL)
    os.replace(temporary, config)


def native_dependencies(root):
    data = manifest(root)
    if not data or not data.get('native_prebuilt'):
        raise ValueError('原生发布包必须包含预编译依赖，不允许现场下载或编译')
    arch = platform.machine().lower()
    if platform.system() == 'Windows':
        arch = {'x86_64': 'amd64'}.get(arch, arch)
    elif platform.system() == 'Linux':
        arch = {'arm64': 'aarch64', 'amd64': 'x86_64'}.get(arch, arch)
    directory = root / 'wheelhouse' / arch
    hashes = json.loads((directory / 'SHA256.json').read_text())
    for name, expected in hashes.items():
        if Path(name).name != name:
            raise ValueError('非法依赖路径')
        digest_file(directory / name, expected)
    return ['--no-index', '--only-binary=:all:', '--force-reinstall', '--find-links', str(directory),
            '-r', str(directory / 'requirements.lock')]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    set_image(args.config, prepare_docker(args.root))
