import argparse
import json
from pathlib import Path
import subprocess

REPO = 'ghcr.io/hongheshan-svg/atm-erp'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--folder', type=Path, required=True)
    args = parser.parse_args()
    records = {arch: json.loads((args.folder / f'{arch}.json').read_text()) for arch in ('amd64', 'arm64')}
    subprocess.run(['docker', 'buildx', 'imagetools', 'create', '--tag', REPO + ':' + args.tag,
                    *(REPO + '@' + record['digest'] for record in records.values())], check=True)
    result = subprocess.check_output(['docker', 'buildx', 'imagetools', 'inspect', REPO + ':' + args.tag,
                                      '--format', '{{json .Manifest}}'], text=True)
    digest = json.loads(result)['digest']
    (args.folder / 'manifest.json').write_text(json.dumps({'docker_image': REPO + '@' + digest,
                                                         'docker_archives': records}, indent=2))
