"""One explicit backup run for a host scheduler; no automatic schedule installation."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backup import digest
from ops_check import inspect


def cycle(env_file, backup_dir, offsite_dir, data_path, health_url, status_file):
    os.umask(0o077)
    result = {'ok': False, 'started_at': datetime.now(timezone.utc).isoformat()}
    lock = backup_dir / '.backup-cycle.lock'
    acquired = False
    try:
        for directory in (backup_dir, offsite_dir):
            if not directory.is_dir():
                raise ValueError('本地和异地挂载目录必须预先建立并验证，脚本不会自动创建或挂载。')
        if backup_dir.resolve() == offsite_dir.resolve():
            raise ValueError('备份目录和异地目录不能相同。')
        try:
            lock.mkdir()
        except FileExistsError:
            raise ValueError('备份任务已在运行或上次异常退出；请核对现场后处理锁目录，禁止重叠运行。')
        acquired = True
        name = f'lean-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}.zip'
        archive = backup_dir / name
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name('backup.py')),
                'backup',
                '--env-file',
                str(env_file),
                '--archive',
                str(archive),
            ],
            check=True,
        )
        check = inspect(backup_dir, data_path, health_url=health_url)
        if not check['ok']:
            raise ValueError('；'.join(check['failures']))
        remote = offsite_dir / name
        with archive.open('rb') as source, remote.open('xb') as target:
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        if digest(archive) != digest(remote):
            raise ValueError('异地副本校验失败，保留现场文件。')
        result.update(ok=True, archive=str(archive), offsite=str(remote), sha256=digest(archive))
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        if acquired:
            lock.rmdir()
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    temporary = status_file.with_name(status_file.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(status_file)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in (
        'env-file',
        'backup-dir',
        'offsite-dir',
        'data-path',
        'status-file',
    ):
        parser.add_argument('--' + argument, type=Path, required=True)
    parser.add_argument('--health-url', required=True)
    args = parser.parse_args()
    result = cycle(**vars(args))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
