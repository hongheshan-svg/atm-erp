"""Read-only operational checks; explicit target, no production configuration discovery."""

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile


def inspect(backup_dir, data_path, max_age_hours=26, min_free_gb=5, health_url=None):
    failures = []
    backups = [p for p in backup_dir.glob('*.zip') if p.is_file() and p.stat().st_size > 0]
    newest = max(backups, key=lambda p: p.stat().st_mtime) if backups else None
    age = (time.time() - newest.stat().st_mtime) / 3600 if newest else None
    if age is None or age > max_age_hours:
        failures.append('备份缺失或超过允许时长；检查备份任务退出码及归档目录。')
    if newest:
        try:
            with ZipFile(newest) as archive:
                manifest = json.loads(archive.read('manifest.json'))
                for name in ('database.dump', 'uploads.tar'):
                    digest = hashlib.sha256()
                    with archive.open(name) as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            digest.update(block)
                    if digest.hexdigest() != manifest['sha256'][name]:
                        raise ValueError('checksum mismatch')
        except Exception:
            failures.append('最新归档不完整或校验值不匹配；保留现场并重新备份。')
    free_gb = shutil.disk_usage(data_path).free / (1024**3)
    if free_gb < min_free_gb:
        failures.append('数据所在磁盘可用空间低于阈值。')
    if health_url:
        try:
            with urlopen(health_url, timeout=10) as response:
                if response.status != 200:
                    failures.append('健康检查未返回200。')
        except Exception:
            failures.append('健康检查连接失败。')
    return {
        'ok': not failures,
        'failures': failures,
        'latest_backup': str(newest) if newest else None,
        'backup_age_hours': age,
        'free_gb': round(free_gb, 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-dir', type=Path, required=True)
    parser.add_argument('--data-path', type=Path, required=True)
    parser.add_argument('--health-url')
    parser.add_argument('--max-age-hours', type=float, default=26)
    parser.add_argument('--min-free-gb', type=float, default=5)
    args = parser.parse_args()
    if not args.backup_dir.is_dir() or not args.data_path.exists() or args.max_age_hours <= 0 or args.min_free_gb < 0:
        parser.error('目录必须存在，备份时限须为正数，可用空间阈值不能为负。')
    result = inspect(args.backup_dir, args.data_path, args.max_age_hours, args.min_free_gb, args.health_url)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result['ok'] else 1)


if __name__ == '__main__':
    main()
