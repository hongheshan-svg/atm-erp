"""Stage and verify attachments before committing a restored database."""
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

MARKER = '.lean-restore-state.json'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def prepare(root, stream, archive_digest):
    root = root.resolve()
    marker = root / MARKER
    if marker.is_symlink():
        raise ValueError('Restore marker cannot be a symlink')
    existing = list(root.iterdir())
    if existing and (not marker.is_file() or json.loads(marker.read_text()) != {'archive': archive_digest}):
        raise ValueError('Uploads are not empty or belong to another restore')
    with tempfile.TemporaryDirectory(prefix='lean-restore-') as temporary:
        stage = Path(temporary)
        with tarfile.open(fileobj=stream, mode='r|*') as tar:
            for entry in tar:
                name = PurePosixPath(entry.name)
                if name.is_absolute() or '..' in name.parts or '\\' in entry.name or ':' in entry.name or MARKER in name.parts or not (entry.isdir() or entry.isfile()):
                    raise ValueError('Unsafe attachment archive')
                target = stage.joinpath(*name.parts)
                if entry.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as output, tar.extractfile(entry) as source:
                        shutil.copyfileobj(source, output)
        expected = {p.relative_to(stage): p for p in stage.rglob('*')}
        for target in root.rglob('*'):
            if target == marker:
                continue
            relative = target.relative_to(root)
            source = expected.get(relative)
            if target.is_symlink() or source is None or target.is_dir() != source.is_dir() or (target.is_file() and digest(target) != digest(source)):
                raise ValueError('Existing uploads differ from this restore; refusing overwrite')
        # This marker authorizes retries of this exact archive only, while DB is empty.
        if not marker.exists():
            with marker.open('x') as output:
                json.dump({'archive': archive_digest}, output)
        for relative, source in expected.items():
            target = root / relative
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                # Publish complete files only; a failed copy remains outside uploads.
                with tempfile.NamedTemporaryFile(dir=root, prefix='.restore-copy-', delete=False) as output:
                    pending = Path(output.name)
                    try:
                        with source.open('rb') as input_file:
                            shutil.copyfileobj(input_file, output)
                    except BaseException:
                        output.close()
                        pending.unlink()
                        raise
                pending.replace(target)
        for relative, source in expected.items():
            if source.is_file() and digest(root / relative) != digest(source):
                raise ValueError('Restored attachment verification failed')


if __name__ == '__main__':
    directory = Path('/app/uploads')
    if sys.argv[1] == 'prepare':
        prepare(directory, sys.stdin.buffer, sys.argv[2])
    elif sys.argv[1] == 'finish':
        marker = directory / MARKER
        if json.loads(marker.read_text()) != {'archive': sys.argv[2]}:
            raise ValueError('Restore marker mismatch')
        marker.unlink()
    else:
        raise ValueError('Unknown restore action')
