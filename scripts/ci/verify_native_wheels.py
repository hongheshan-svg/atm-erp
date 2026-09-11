"""Exercise the exact offline install command on each native CI platform."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_install import native_dependencies

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wheels', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        shutil.copytree(args.wheels, root / 'wheelhouse')
        (root / 'INSTALL-MANIFEST.json').write_text(json.dumps({'native_prebuilt': True}))
        subprocess.run([sys.executable, '-m', 'venv', str(root / 'venv')], check=True)
        python = root / 'venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        subprocess.run([str(python), '-m', 'pip', 'install', *native_dependencies(root)], check=True)
        subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
        subprocess.run(
            [
                str(python),
                '-c',
                'import django, daphne, psycopg2, redis, cryptography; print("Offline native runtime verified")',
            ],
            check=True,
        )
