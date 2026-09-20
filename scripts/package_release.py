#!/usr/bin/env python3
"""Package immutable tag sources plus explicitly identified installer additions."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ("scripts/native_install.py", "scripts/native_service.py", "install-native.sh", "install-native.ps1", "docs/INSTALL_PLATFORMS.md")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def docker_compose(source, image):
    """A downloaded release starts with Compose alone; no host Python bootstrap."""
    if not re.fullmatch(r'ghcr\.io/hongheshan-svg/atm-erp@sha256:[a-f0-9]{64}', image):
        raise ValueError('发布镜像必须是固定仓库的完整摘要')
    compose = source.replace('    build:\n      context: .\n      dockerfile: docker/app/Dockerfile\n', '')
    marker = '${LEAN_IMAGE:-atm-erp-lean:local}'
    if marker not in compose:
        raise ValueError('Compose 镜像占位符变化，拒绝生成未锁定的发布包')
    return compose.replace(marker, '${LEAN_IMAGE:-' + image + '}')


def build(tag, output, artifacts):
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError("只能打包正式语义版本号的 tag")
    commit = git("rev-parse", f"{tag}^{{}}")
    installer_commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--", *OVERLAY, "scripts/package_release.py"):
        raise ValueError("打包前请先提交安装器源码，保证发布来源可追溯")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lean-release-") as temporary:
        temporary = Path(temporary)
        archive = temporary / "source.tar"
        with archive.open("wb") as stream:
            subprocess.run(["git", "archive", tag], cwd=ROOT, stdout=stream, check=True)
        source = temporary / "source"
        source.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(source, filter="data")
        npm = shutil.which("npm")
        if not npm:
            raise ValueError("构建发布前端需要 Node.js 22 与 npm")
        for command in ([npm, "ci"], [npm, "run", "build"]):
            subprocess.run(command, cwd=source / "frontend", check=True)
        shutil.rmtree(source / "frontend/node_modules")
        for relative in OVERLAY:
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        compose_template = (source / 'docker-compose.yml').read_text()
        for mode in ("native", "docker"):
            for platform in ("macos", "linux", "windows"):
                for folder in ('wheelhouse', 'images'):
                    shutil.rmtree(source / folder, ignore_errors=True)
                name = f"atm-erp-{tag}-{platform}-{mode}"
                manifest = {
                    "version": tag, "source_commit": commit, "installer_commit": installer_commit,
                    "platform": platform, "mode": mode,
                    "architecture": "amd64/arm64 Docker; native wheelhouse architectures listed below",
                    "offline": False, "overlay_files": list(OVERLAY),
                    "note": "Original tag business code; supplementary installers, no tag rewrite.",
                }
                if mode == 'docker':
                    images = json.loads((artifacts / 'images/manifest.json').read_text())
                    manifest.update(docker_image=images['docker_image'], docker_archives=images['docker_archives'])
                    shutil.copytree(artifacts / 'images', source / 'images')
                    # A release package physically has no build directive.
                    compose = docker_compose(compose_template, images['docker_image'])
                    (source / 'docker-compose.yml').write_text(compose)
                else:
                    shutil.copytree(artifacts / 'wheels' / platform, source / 'wheelhouse')
                    manifest.update(native_prebuilt=True, native_architectures=sorted(p.name for p in (source / 'wheelhouse').iterdir()))
                    protocol = source / 'docker/app/runtime-protocol.json'
                    if platform == 'linux' and protocol.exists():
                        manifest['container_runtime'] = json.loads(protocol.read_text())['version']
                (source / "INSTALL-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                command = (".\\install-native.ps1 configure" if platform == "windows" else "bash install-native.sh configure") if mode == "native" else '复制 .env.example 为 .env 并填写密钥，然后 docker compose up -d'
                (source / "INSTALL-START-HERE.txt").write_text(
                    f"Lean ERP {tag} / {platform} / {mode}\n\n"
                    f"先阅读 README.md 的安装说明，安装前置依赖。\n入口：{command}\n"
                    "包含 CI 预构建镜像或原生依赖，无需本地编译。仍需对应宿主机运行环境。\n"
                    "业务源码保持原 tag；安装器补充版本见 INSTALL-MANIFEST.json。\n",
                    encoding="utf-8")
                with zipfile.ZipFile(output / (name + ".zip"), "w", zipfile.ZIP_DEFLATED) as bundle:
                    for path in sorted(source.rglob("*")):
                        if path.is_file():
                            bundle.write(path, name + "/" + path.relative_to(source).as_posix())
        checksums = output / f"atm-erp-{tag}-SHA256SUMS.txt"
        checksums.write_text("".join(
            hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
            for path in sorted(output.glob(f"atm-erp-{tag}-*.zip"))), encoding="ascii")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='打包指定 tag 的源码与显式声明的安装器附加文件')
    parser.add_argument("tag")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    build(args.tag, args.output.resolve(), args.artifacts.resolve())
