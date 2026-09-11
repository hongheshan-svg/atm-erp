"""Resolve binary-only CPython 3.11 dependencies on CI, never on user machines."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from email.parser import BytesParser
from pathlib import Path

TARGETS = {
    'linux': {
        'x86_64': ['manylinux_2_28_x86_64', 'manylinux2014_x86_64'],
        'aarch64': ['manylinux_2_28_aarch64', 'manylinux2014_aarch64'],
    },
    'macos': {
        'x86_64': [
            'macosx_12_0_x86_64',
            'macosx_11_0_x86_64',
            'macosx_10_9_x86_64',
            'macosx_10_9_universal2',
            'macosx_11_0_universal2',
        ],
        'arm64': ['macosx_14_0_arm64', 'macosx_11_0_arm64', 'macosx_10_9_universal2', 'macosx_11_0_universal2'],
    },
    'windows': {'amd64': ['win_amd64']},
}


def build(platform, output):
    root = Path(__file__).resolve().parents[2]
    for arch, tags in TARGETS[platform].items():
        directory = output / platform / arch
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)
        args = [
            sys.executable,
            '-m',
            'pip',
            'download',
            '--only-binary=:all:',
            '--python-version',
            '311',
            '--implementation',
            'cp',
            '--abi',
            'cp311',
            '-r',
            str(root / 'backend/requirements.txt'),
            '-d',
            str(directory),
        ]
        for tag in tags:
            args.extend(['--platform', tag])
        subprocess.run(args, check=True)
        pins = []
        for wheel in sorted(directory.glob('*.whl')):
            with zipfile.ZipFile(wheel) as archive:
                meta = BytesParser().parsebytes(
                    archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA')))
                )
            pins.append(f'{meta["Name"]}=={meta["Version"]}')
        (directory / 'requirements.lock').write_text('\n'.join(sorted(pins)) + '\n')
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
        (directory / 'SHA256.json').write_text(json.dumps(hashes, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', choices=TARGETS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.platform, args.output)
