"""Consistent database + attachment backup; restore only to an empty deployment."""

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
GENERATION = 'lean-erp-v1'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def validate_uploads(path):
    with tarfile.open(path) as tar:
        for entry in tar:
            name = PurePosixPath(entry.name)
            if name.is_absolute() or '..' in name.parts or not (entry.isfile() or entry.isdir()):
                raise ValueError('附件归档包含不安全路径或链接。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['backup', 'restore'])
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env.lean')
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    compose = ['docker', 'compose', '--env-file', str(args.env_file.resolve()), '-f', str(ROOT / 'docker-compose.yml')]

    def run(*command, **kwargs):
        return subprocess.run([*compose, *command], check=True, **kwargs)

    def sql(query):
        return run(
            'exec',
            '-T',
            'postgres',
            'psql',
            '-U',
            'atm_erp_lean',
            '-d',
            'atm_erp_lean',
            '-Atc',
            query,
            capture_output=True,
            text=True,
        ).stdout.strip()

    # Resolve in memory; never print Compose environment secrets. Require the
    # configured image locally so `compose run` cannot implicitly build it.
    config = json.loads(run('config', '--format', 'json', capture_output=True, text=True).stdout)
    subprocess.run(
        ['docker', 'image', 'inspect', config['services']['app']['image']], check=True, stdout=subprocess.DEVNULL
    )

    archive = args.archive.resolve()
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='lean-backup-') as temporary:
        folder = Path(temporary)
        dump, uploads = folder / 'database.dump', folder / 'uploads.tar'
        if args.operation == 'backup':
            if archive.exists():
                parser.error('备份目标已存在；请使用新文件名。')
            if sql('SELECT generation FROM lean_schema WHERE id=1') != GENERATION:
                parser.error('源数据库不是当前精简版。')
            running = (
                'app' in run('ps', '--status', 'running', '--services', capture_output=True, text=True).stdout.split()
            )
            run('stop', 'app')
            try:
                with dump.open('wb') as stream:
                    run(
                        'exec',
                        '-T',
                        'postgres',
                        'pg_dump',
                        '-U',
                        'atm_erp_lean',
                        '-d',
                        'atm_erp_lean',
                        '-Fc',
                        '--no-owner',
                        '--no-acl',
                        stdout=stream,
                    )
                with uploads.open('wb') as stream:
                    run(
                        'run',
                        '--rm',
                        '-T',
                        '--no-deps',
                        '--pull',
                        'never',
                        '--entrypoint',
                        'tar',
                        'app',
                        '-C',
                        '/app/uploads',
                        '-cf',
                        '-',
                        '.',
                        stdout=stream,
                    )
                validate_uploads(uploads)
                manifest = {'schema': GENERATION, 'sha256': {p.name: digest(p) for p in (dump, uploads)}}
                archive.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation prevents replacing an existing backup.
                with archive.open('xb') as output, ZipFile(output, 'w', compression=ZIP_STORED) as bundle:
                    bundle.writestr('manifest.json', json.dumps(manifest))
                    for source in (dump, uploads):
                        bundle.write(source, source.name)
            except BaseException:
                # Preserve any incomplete file for diagnosis; its checksums will not validate.
                raise
            finally:
                if running:
                    run('start', '--wait', '--wait-timeout', '180', 'app')
            print(f'备份完成：{archive}（包含数据库及附件，不含环境密钥）')
            return

        # Validate the full bundle before starting or modifying the target deployment.
        with ZipFile(archive) as bundle:
            if sorted(bundle.namelist()) != ['database.dump', 'manifest.json', 'uploads.tar']:
                parser.error('备份结构不正确。')
            manifest = json.loads(bundle.read('manifest.json'))
            if manifest.get('schema') != GENERATION:
                parser.error('备份版本不匹配。')
            for source in (dump, uploads):
                with bundle.open(source.name) as src, source.open('wb') as dst:
                    while chunk := src.read(1024 * 1024):
                        dst.write(chunk)
                if digest(source) != manifest.get('sha256', {}).get(source.name):
                    parser.error('备份校验和不匹配。')
        validate_uploads(uploads)
        if 'app' in run('ps', '--status', 'running', '--services', capture_output=True, text=True).stdout.split():
            parser.error('恢复目标必须为全新部署，不能覆盖正在运行的系统。')
        run('up', '-d', '--wait', '--wait-timeout', '120', 'postgres', 'redis')
        if sql("SELECT count(*) FROM pg_tables WHERE schemaname='public'") != '0':
            parser.error('目标数据库非空，拒绝覆盖。请使用全新独立项目与新卷。')
        archive_digest = digest(archive)
        # Extraction and disk-space failures must occur before pg_restore commits.
        # The helper permits an exact, verified retry while the database is empty.
        with uploads.open('rb') as stream:
            run(
                'run',
                '--rm',
                '-T',
                '--no-deps',
                '--pull',
                'never',
                '--entrypoint',
                'python',
                'app',
                '/restore_uploads.py',
                'prepare',
                archive_digest,
                stdin=stream,
            )
        with dump.open('rb') as stream:
            run(
                'exec',
                '-T',
                'postgres',
                'pg_restore',
                '-U',
                'atm_erp_lean',
                '-d',
                'atm_erp_lean',
                '--no-owner',
                '--no-acl',
                '--exit-on-error',
                '--single-transaction',
                stdin=stream,
            )
        run(
            'run',
            '--rm',
            '-T',
            '--no-deps',
            '--pull',
            'never',
            '--entrypoint',
            'python',
            'app',
            '/restore_uploads.py',
            'finish',
            archive_digest,
        )
        run('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180', 'app')
        print('恢复完成。账户密码保持备份时的值，环境密钥使用目标配置。')


if __name__ == '__main__':
    main()
