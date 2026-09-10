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
            raise ValueError('Duplicate checksum entry')
        listed[name] = digest
    if set(listed) != names:
        raise ValueError('Expected exactly six installers')
    for name, digest in listed.items():
        path = folder / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Installer checksum mismatch')
        with zipfile.ZipFile(path) as archive:
            if archive.testzip():
                raise ValueError('Corrupt installer archive')
            manifest = json.loads(archive.read(path.stem + '/INSTALL-MANIFEST.json'))
            if (
                manifest['version'] != tag
                or manifest['source_commit'] != commit
                or manifest['installer_commit'] != commit
            ):
                raise ValueError('Installer provenance differs from tag')
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
        raise ValueError('Stable tag required')
    commit = git('rev-parse', f'refs/tags/{args.tag}^{{commit}}')
    if git('rev-parse', 'HEAD') != commit:
        raise ValueError('Checkout must be exactly the tagged commit')
    expected = verify(args.folder, args.tag, commit)
    if not args.upload:
        print('Six installers and SHA256 manifest verified')
        return
    repository = os.environ['GITHUB_REPOSITORY']
    releases = api(f'repos/{repository}/releases?per_page=100')
    existing = next((r for r in releases if r['tag_name'] == args.tag), None)
    if existing and not existing['draft']:
        raise ValueError('Published assets cannot be overwritten')
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
        raise ValueError('Unexpected draft assets')
    for asset in release['assets']:
        if asset['state'] != 'uploaded' or asset['digest'] != 'sha256:' + expected[asset['name']]:
            raise ValueError('Uploaded digest differs from local installer')
    if args.publish:
        subprocess.run(['gh', 'release', 'edit', args.tag, '--draft=false', '--latest'], check=True)
    print('Remote installer digests verified; ' + ('published' if args.publish else 'draft ready'))


if __name__ == '__main__':
    main()
