"""Consistent database + attachment backup; restore only to an empty deployment."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
GENERATION = 'lean-erp-v1'
# 与容器启动器 container_runtime.selected() 一致：runtime 卷中网页升级安装的程序不旧于镜像时运行它，
# 否则运行镜像自带程序；早于容器内升级的镜像没有启动器，只运行镜像自带程序。
VERSION_PROBE = r"""
import pathlib, re, sys
sys.path.insert(0, '/opt/erp')
try:
    import container_runtime
except ModuleNotFoundError:
    backend = pathlib.Path('/app')
else:
    backend = container_runtime.selected()[0]
text = (backend / 'apps/core/version.py').read_text()
print(re.search(r"VERSION\s*=\s*['\"](\d+\.\d+\.\d+)['\"]", text)[1])
"""


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


def parse_version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('程序版本格式无效')
    return tuple(map(int, value.split('.')))


def default_env_file(root=ROOT):
    """与 install.sh 一致：默认使用 .env；只有旧部署仅存在 .env.lean 时才沿用它。"""
    current, legacy = root / '.env', root / '.env.lean'
    return legacy if legacy.is_file() and not current.is_file() else current


def main():
    parser = argparse.ArgumentParser(description='备份数据库与附件；恢复只允许写入全新的空部署')
    parser.add_argument('operation', choices=['backup', 'restore'])
    parser.add_argument(
        '--env-file', type=Path, default=default_env_file(), help='默认 .env；仅存在旧 .env.lean 时沿用 .env.lean'
    )
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

    def program_version():
        """容器实际运行的程序版本；网页升级后为 runtime 卷中的程序，不是镜像自带版本。"""
        output = run(
            'run',
            '--rm',
            '-T',
            '--no-deps',
            '--pull',
            'never',
            '--entrypoint',
            'python',
            'app',
            '-c',
            VERSION_PROBE,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.split()
        value = output[-1] if output else ''
        parse_version(value)
        return value

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
            # 恢复端据此拒绝较旧的程序，避免还原后才以“旧迁移历史”拒绝启动。
            # 无法确认时仍完成备份（部署损坏时更需要备份），清单如实不写版本并明确警告。
            try:
                version = program_version()
            except (subprocess.CalledProcessError, ValueError):
                version = None
                print(
                    '警告：无法确认部署实际运行的程序版本，本次备份清单不含程序版本，恢复时无法核对目标程序是否足够新。',
                    file=sys.stderr,
                )
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
                if version:
                    manifest['version'] = version
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
            print(f'备份完成：{archive}（程序版本 {version or "未知"}，包含数据库及附件，不含环境密钥）')
            return

        # Validate the full bundle before starting or modifying the target deployment.
        with ZipFile(archive) as bundle:
            if sorted(bundle.namelist()) != ['database.dump', 'manifest.json', 'uploads.tar']:
                parser.error('备份结构不正确。')
            manifest = json.loads(bundle.read('manifest.json'))
            if manifest.get('schema') != GENERATION:
                parser.error('备份版本不匹配。')
            source_version = manifest.get('version')
            if source_version is not None:
                try:
                    parse_version(source_version)
                except ValueError:
                    parser.error('备份清单中的程序版本无效。')
            for source in (dump, uploads):
                with bundle.open(source.name) as src, source.open('wb') as dst:
                    while chunk := src.read(1024 * 1024):
                        dst.write(chunk)
                if digest(source) != manifest.get('sha256', {}).get(source.name):
                    parser.error('备份校验和不匹配。')
        validate_uploads(uploads)
        if 'app' in run('ps', '--status', 'running', '--services', capture_output=True, text=True).stdout.split():
            parser.error('恢复目标必须为全新部署，不能覆盖正在运行的系统。')
        # 较旧的程序不认识备份中较新的迁移，还原后会以“旧迁移历史”拒绝启动；必须在写入数据库前拒绝。
        if source_version is None:
            print('提示：该备份未记录程序版本（早期备份或备份时无法确认），恢复前不核对程序版本。', file=sys.stderr)
        else:
            try:
                target_version = program_version()
            except (subprocess.CalledProcessError, ValueError):
                target_version = None
                print(
                    f'警告：无法确认目标部署的程序版本，未核对备份的程序版本 {source_version}。'
                    '请自行确认目标镜像不低于该版本，否则恢复后应用会以“旧迁移历史”拒绝启动。',
                    file=sys.stderr,
                )
            if target_version and parse_version(target_version) < parse_version(source_version):
                parser.error(
                    f'备份来自程序版本 {source_version}，目标部署的程序版本为 {target_version}，'
                    '较旧的程序无法识别备份中的数据库迁移。'
                    f'请改用 {source_version} 或更新版本的 Docker 包或镜像（LEAN_IMAGE）后重新恢复；目标数据库与附件未改动。'
                )
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
