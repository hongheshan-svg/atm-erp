"""Use immutable CI-built artifacts; release installs never compile application code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess

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
    subprocess.run(['docker', 'load', '-i', str(path)], check=True)
    actual = subprocess.check_output(['docker', 'image', 'inspect', record['image_id'], '--format', '{{.Id}}'], text=True).strip()
    if actual != record['image_id']:
        raise ValueError('镜像归档身份不符')
    return actual


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
