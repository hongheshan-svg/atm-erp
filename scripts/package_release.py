#!/usr/bin/env python3
"""Package immutable tag sources plus explicitly identified installer additions."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ("scripts/native_install.py", "install-native.sh", "install-native.ps1", "docs/INSTALL_PLATFORMS.md")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def build(tag, output):
    if tag not in ("v1.0.0", "v1.1.0"):
        raise ValueError("Only the requested immutable releases may be packaged")
    commit = git("rev-parse", f"{tag}^{{}}")
    installer_commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--", *OVERLAY, "scripts/package_release.py"):
        raise ValueError("Commit installer sources before packaging for provenance")
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
            raise ValueError("Node.js 22 / npm required to build release frontend")
        for command in ([npm, "ci"], [npm, "run", "build"]):
            subprocess.run(command, cwd=source / "frontend", check=True)
        shutil.rmtree(source / "frontend/node_modules")
        for relative in OVERLAY:
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        for mode in ("native", "docker"):
            for platform in ("macos", "linux", "windows"):
                name = f"atm-erp-{tag}-{platform}-{mode}"
                manifest = {
                    "version": tag, "source_commit": commit, "installer_commit": installer_commit,
                    "platform": platform, "mode": mode,
                    "architecture": "host-native dependencies (x86_64 or arm64 where available)",
                    "offline": False, "overlay_files": list(OVERLAY),
                    "note": "Original tag business code; supplementary installers, no tag rewrite.",
                }
                (source / "INSTALL-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                command = (".\\install-native.ps1 configure" if platform == "windows" else "bash install-native.sh configure") if mode == "native" else (".\\install.ps1" if platform == "windows" else "bash install.sh")
                (source / "INSTALL-START-HERE.txt").write_text(
                    f"Lean ERP {tag} / {platform} / {mode}\n\n"
                    f"先阅读 docs/INSTALL_PLATFORMS.md，安装前置依赖。\n入口：{command}\n"
                    "这是联网安装包，不内置 Python、数据库、Nginx 或 Docker 镜像。\n"
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", choices=("v1.0.0", "v1.1.0"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.tag, args.output.resolve())
