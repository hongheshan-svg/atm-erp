"""Isolated in-container OTA rehearsal; only release discovery is a local fixture."""
import argparse
import base64
import csv
import functools
import hashlib
import http.server
import importlib.metadata
import io
import json
import os
import platform
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch


def pack_fixture_wheels(output):
    """Offline fallback fixture, NOT CI artifact validation: repack installed image dependencies."""
    output = output / platform.machine()
    output.mkdir(parents=True, exist_ok=True)
    pins = []
    for dist in importlib.metadata.distributions():
        wheel_metadata = dist.read_text('WHEEL')
        if not wheel_metadata:
            continue
        tags = [line[5:] for line in wheel_metadata.splitlines() if line.startswith('Tag: ') and not line[5:].startswith('py2-')]
        if not tags:
            continue
        name = re.sub(r'[-_.]+', '_', dist.metadata['Name'])
        filename = f'{name}-{dist.version}-{tags[0]}.whl'
        record = []
        record_path = next(str(file) for file in dist.files or []
                           if len(file.parts) == 2 and str(file).endswith('.dist-info/RECORD'))
        with zipfile.ZipFile(output / filename, 'w', zipfile.ZIP_DEFLATED) as wheel:
            for file in dist.files or []:
                if '..' in file.parts or '__pycache__' in file.parts:
                    continue
                if not dist.locate_file(file).is_file():
                    continue  # Slim base images may remove dependency test files.
                if str(file) == record_path:
                    continue
                data = dist.locate_file(file).read_bytes()
                wheel.writestr(str(file), data)
                digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
                record.append([str(file), 'sha256=' + digest, str(len(data))])
            assert record_path
            record.append([record_path, '', ''])
            stream = io.StringIO()
            csv.writer(stream).writerows(record)
            wheel.writestr(record_path, stream.getvalue())
        pins.append(f'{dist.metadata["Name"]}=={dist.version}')
    (output / 'requirements.lock').write_text('\n'.join(pins) + '\n')
    (output / 'SHA256.json').write_text(json.dumps({
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir() if path.is_file()
    }))


def inside(prepare_only=False, resume=False, crash_before_backup=False, crash_verifying=False):
    sys.path[:0] = ['/opt/erp', '/app']
    import container_ota
    import container_runtime
    from ota_runner import file_hash

    # docker exec does not inherit env changes made by PID 1; recover its internal capability.
    os.environ['OTA_AGENT_TOKEN'] = __import__('hmac').new(
        os.environ['SECRET_KEY'].encode(), b'erp-container-ota-v1', hashlib.sha256,
    ).hexdigest()
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    import django
    django.setup()
    from apps.accounts.models import User
    from apps.core.models import Company, UpgradeJob
    from rest_framework.test import APIClient

    if not resume:
        Company.objects.filter(pk=1).update(name='容器 OTA 保留数据')
        Path('/app/uploads/ota-proof.txt').write_text('attachment-preserved')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 18189), functools.partial(
        http.server.SimpleHTTPRequestHandler, directory='/tmp/ota-fixture'))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    package = Path('/tmp/ota-fixture/package.zip')
    client = APIClient()
    client.force_authenticate(User.objects.get(username='admin'))
    runner = container_ota.ContainerRunner()
    runner.api({'action': 'poll', 'mode': 'native', 'platform': 'linux', 'execution': 'container',
                'runner_id': runner.state['runner_id']})
    if not resume:
        asset = {'name': 'atm-erp-v9.0.0-linux-native.zip', 'url': 'http://127.0.0.1:18189/package.zip',
                 'sha256': file_hash(package), 'size': package.stat().st_size}
        with patch('apps.core.ota.release_info', return_value={'version': 'v9.0.0', 'assets': [asset]}):
            response = client.post('/api/core/upgrade/', {'target': 'v9.0.0', 'confirmed': True},
                                   format='json', HTTP_HOST='localhost', HTTP_IDEMPOTENCY_KEY=secrets.token_hex(16))
        assert response.status_code == 200, response.data
    job = runner.api({'action': 'poll', 'mode': 'native', 'platform': 'linux', 'execution': 'container',
                      'runner_id': runner.state['runner_id']})['job']
    asset = job['asset']
    # Production download, checksum, unpack, offline pip, backup, migration and switch all run.
    with patch.object(container_ota, 'trusted_asset', return_value=asset):
        if not resume:
            runner.execute(job)
        stored = UpgradeJob.objects.get(pk=job['id'])
        assert stored.status == 'ready', stored.detail
        assert not (runner.directory / f'job-{job["id"]}/backup').exists()
        assert not (runner.directory / 'active.json').exists()
        if prepare_only:
            assert runner.running_version() < (9, 0, 0)
            server.shutdown()
            print('Prepared update is durable; application is still on original version, no backup or migration.')
            return
        # Reload durable state just as a restarted worker does. No duplicate preparation.
        runner = container_ota.ContainerRunner()
        runner.recover()
        waiting = runner.api({'action': 'poll', 'mode': 'native', 'platform': 'linux', 'execution': 'container',
                              'runner_id': runner.state['runner_id']})['job']
        runner.dispatch(waiting)
        assert runner.running_version() < (9, 0, 0)
        response = client.post('/api/core/upgrade/restart/', {'id': job['id'], 'confirmed': True},
                               format='json', HTTP_HOST='localhost', HTTP_IDEMPOTENCY_KEY=secrets.token_hex(16))
        assert response.status_code == 200, response.data
        restarting = runner.api({'action': 'poll', 'mode': 'native', 'platform': 'linux', 'execution': 'container',
                                 'runner_id': runner.state['runner_id']})['job']
        if crash_before_backup:
            if not package.exists():
                shutil.copyfile(runner.directory / f'job-{job["id"]}/package.zip', package)
            pid = os.fork()
            if pid == 0:
                runner.backup = lambda *_: os.kill(os.getpid(), signal.SIGKILL)
                runner.dispatch(restarting)
                os._exit(1)
            _, result = os.waitpid(pid, 0)
            assert os.WIFSIGNALED(result) and os.WTERMSIG(result) == signal.SIGKILL
            assert container_runtime.journal()['phase'] == 'backup'
            runner = container_ota.ContainerRunner()
            runner.recover()
            for _ in range(30):
                try:
                    runner.flush()
                    assert runner.running_version() < (9, 0, 0)
                    break
                except OSError:
                    time.sleep(1)
            else:
                raise AssertionError('Old application did not recover after worker SIGKILL')
            assert UpgradeJob.objects.get(pk=job['id']).status == 'failed'
            assert not container_runtime.journal()
            server.shutdown()
            server.server_close()
            print('SIGKILL after application stop: worker recovery restored old service without migration.')
            return inside(crash_verifying=True)
        if crash_verifying:
            pid = os.fork()
            if pid == 0:
                original_phase = runner.phase
                def crash_after_switch(value, active_job):
                    original_phase(value, active_job)
                    if value == 'verifying':
                        os.kill(os.getpid(), signal.SIGKILL)
                runner.phase = crash_after_switch
                runner.dispatch(restarting)
                os._exit(1)
            _, result = os.waitpid(pid, 0)
            assert os.WIFSIGNALED(result) and os.WTERMSIG(result) == signal.SIGKILL
            assert container_runtime.journal()['phase'] == 'verifying'
            runner = container_ota.ContainerRunner()
            runner.recover()
            runner.flush()
            assert not container_runtime.journal()
            print('SIGKILL after version switch: recovery started and verified target, durable task succeeded.')
        else:
            runner.dispatch(restarting)
    stored = UpgradeJob.objects.get(pk=job['id'])
    if stored.status != 'succeeded':
        print((runner.directory / f'job-{job["id"]}/upgrade.log').read_text())
    assert stored.status == 'succeeded', stored.detail
    backup = Path(stored.backup)
    manifest = json.loads((backup / 'manifest.json').read_text())
    for name, digest in manifest['sha256'].items():
        assert file_hash(backup / name) == digest
    assert (backup / 'database.dump').stat().st_size > 0
    with tarfile.open(backup / 'uploads.tar') as archive:
        assert archive.extractfile('uploads/ota-proof.txt').read() == b'attachment-preserved'
    subprocess.run(['/opt/pg/bin/pg_restore', '--list', str(backup / 'database.dump')], check=True,
                   env={**os.environ, 'LD_LIBRARY_PATH': '/opt/pg/lib'}, stdout=subprocess.DEVNULL)
    import psycopg2
    from django.db import connection
    restored_name = 'ota_restore_' + secrets.token_hex(6)
    quoted = connection.ops.quote_name(restored_name)
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE {quoted}')
    try:
        subprocess.run(['/opt/pg/bin/pg_restore', '--exit-on-error', '--no-owner', '--no-acl',
                        '-h', os.environ['DB_HOST'], '-p', os.environ.get('DB_PORT', '5432'),
                        '-U', os.environ['DB_USER'], '-d', restored_name, str(backup / 'database.dump')],
                       check=True, env={**os.environ, 'PGPASSWORD': os.environ['DB_PASSWORD'],
                                        'LD_LIBRARY_PATH': '/opt/pg/lib'})
        restored = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT', '5432'),
                                    user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
                                    dbname=restored_name)
        try:
            with restored.cursor() as cursor:
                cursor.execute(f'SELECT name FROM {connection.ops.quote_name(Company._meta.db_table)} WHERE id=1')
                assert cursor.fetchone()[0] == '容器 OTA 保留数据'
                cursor.execute(f'SELECT COUNT(*) FROM {connection.ops.quote_name(User._meta.db_table)} WHERE username=%s',
                               ['admin'])
                assert cursor.fetchone()[0] == 1
        finally:
            restored.close()
        print('Backup restored into a separate empty database; original company and administrator verified.')
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE {quoted}')  # Only the disposable restore database created above.
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT ota_test_marker FROM {connection.ops.quote_name(Company._meta.db_table)} WHERE id=1')
        assert cursor.fetchone()[0] == 'container-ota-proof'
    assert Company.objects.get(pk=1).name == '容器 OTA 保留数据'
    assert container_runtime.selected()[0].name == 'backend'
    server.shutdown()
    print('Real container OTA: checksum, offline dependencies, backup, migration and target health passed.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inside', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--crash-before-backup', action='store_true')
    parser.add_argument('--image')
    parser.add_argument('--native-package', type=Path)
    parser.add_argument('--fixture-from-image', action='store_true')
    parser.add_argument('--pack-wheels', type=Path)
    parser.add_argument('--port', type=int, default=18515)
    args = parser.parse_args()
    if args.pack_wheels:
        pack_fixture_wheels(args.pack_wheels)
        return
    if args.inside:
        inside(args.prepare_only, args.resume, args.crash_before_backup)
        return
    if not args.image or not (args.native_package or args.fixture_from_image):
        parser.error('--image and either --native-package or --fixture-from-image are required')
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from scripts.package_release import docker_compose
    project = 'erp-inplace-smoke-' + secrets.token_hex(5)
    with tempfile.TemporaryDirectory(prefix=project) as temporary:
        task = Path(temporary)
        stage = task / 'atm-erp-v9.0.0-linux-native'
        shutil.copytree(root / 'backend', stage / 'backend', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(root / 'frontend/dist', stage / 'frontend/dist')
        shutil.copytree(root / 'scripts', stage / 'scripts', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copyfile(root / 'docker-compose.yml', stage / 'docker-compose.yml')
        if args.fixture_from_image:
            wheels = stage / 'wheelhouse'
            wheels.mkdir()
            subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--user', '0', '--entrypoint', 'python',
                            '-v', f'{Path(__file__).resolve()}:/fixture.py:ro', '-v', f'{wheels}:/out',
                            args.image, '/fixture.py', '--pack-wheels', '/out'], check=True)
        else:
            with zipfile.ZipFile(args.native_package) as package:
                for name in package.namelist():
                    relative = Path(*Path(name).parts[1:])
                    if relative.parts and relative.parts[0] == 'wheelhouse' and not name.endswith('/'):
                        if '..' in relative.parts:
                            raise ValueError('invalid fixture archive')
                        dest = stage / relative
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(package.read(name))
        (stage / 'backend/apps/core/version.py').write_text("VERSION = '9.0.0'\n")
        models = stage / 'backend/apps/core/models.py'
        models.write_text(models.read_text().replace('class Company(models.Model):',
                          "class Company(models.Model):\n    ota_test_marker = models.CharField(max_length=40, default='container-ota-proof')"))
        migrations = stage / 'backend/apps/core/migrations'
        latest = max(migrations.glob('[0-9]*_*.py'), key=lambda path: int(path.name.split('_')[0]))
        (migrations / f'{int(latest.name.split("_")[0]) + 1:04d}_container_ota.py').write_text(
            "from django.db import migrations, models\nclass Migration(migrations.Migration):\n"
            f"    dependencies = [('core', '{latest.stem}')]\n"
            "    operations = [migrations.AddField(model_name='company', name='ota_test_marker', "
            "field=models.CharField(max_length=40, default='container-ota-proof'))]\n")
        (stage / 'INSTALL-MANIFEST.json').write_text(json.dumps({
            'version': 'v9.0.0', 'mode': 'native', 'platform': 'linux', 'native_prebuilt': True, 'container_runtime': 1,
        }))
        with zipfile.ZipFile(task / 'package.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in stage.rglob('*'):
                if path.is_file():
                    archive.write(path, path.relative_to(task))
        (task / 'package.zip').chmod(0o644)  # Public fixture copied to the non-root container user.
        (task / 'docker-compose.yml').write_text(docker_compose((root / 'docker-compose.yml').read_text(),
                                               'ghcr.io/hongheshan-svg/atm-erp@sha256:' + 'a' * 64))
        password = 'isolated-' + secrets.token_hex(16)
        values = {'LEAN_PROJECT_NAME': project, 'LEAN_IMAGE': args.image, 'LEAN_HTTP_PORT': str(args.port),
                  'LEAN_DB_PASSWORD': secrets.token_hex(32), 'LEAN_SECRET_KEY': secrets.token_hex(32),
                  'LEAN_ADMIN_PASSWORD': password}
        (task / '.env').write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
        (task / '.env').chmod(0o600)
        compose = ['docker', 'compose', '--project-directory', str(task)]

        def command(*argv):
            subprocess.run([*compose, *argv], check=True)

        try:
            command('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180')
            command('exec', '-T', 'app', 'supervisorctl', '-c', '/etc/supervisord.conf', 'stop', 'ota')
            command('exec', '-T', 'app', 'mkdir', '-p', '/tmp/ota-fixture')
            command('cp', str(task / 'package.zip'), 'app:/tmp/ota-fixture/package.zip')
            command('cp', str(Path(__file__).resolve()), 'app:/tmp/ota-fixture/smoke.py')
            command('exec', '-T', 'app', 'python', '/tmp/ota-fixture/smoke.py', '--inside', '--prepare-only')
            command('up', '-d', '--no-build', '--pull', 'never', '--force-recreate', '--wait', 'app')
            command('exec', '-T', 'app', 'supervisorctl', '-c', '/etc/supervisord.conf', 'stop', 'ota')
            command('exec', '-T', 'app', 'mkdir', '-p', '/tmp/ota-fixture')
            command('cp', str(Path(__file__).resolve()), 'app:/tmp/ota-fixture/smoke.py')
            command('exec', '-T', 'app', 'python', '/tmp/ota-fixture/smoke.py', '--inside', '--resume', '--crash-before-backup')
            command('up', '-d', '--no-build', '--pull', 'never', '--force-recreate', '--wait', 'app')
            command('exec', '-T', 'app', 'python', '/opt/erp/container_runtime.py', 'manage', 'check')
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            url = f'http://127.0.0.1:{args.port}'
            with opener.open(url + '/api/health/', timeout=10) as response:
                assert json.load(response)['version'] == '9.0.0'
            request = urllib.request.Request(url + '/api/auth/login/',
                                             data=json.dumps({'username': 'admin', 'password': password}).encode(),
                                             headers={'Content-Type': 'application/json'})
            with opener.open(request, timeout=10) as response:
                token = json.load(response)['access']
            for _ in range(20):
                with opener.open(urllib.request.Request(url + '/api/core/upgrade/',
                                 headers={'Authorization': 'Bearer ' + token}), timeout=10) as response:
                    state = json.load(response)
                if state['runner']:
                    break
                time.sleep(1)
            assert state['runner']['execution'] == 'container' and state['job']['status'] == 'succeeded', state
            print('Container recreation preserved version, login and live OTA heartbeat; isolated project=' + project)
        finally:
            command('logs', '--tail', '30', 'app')
            command('down', '-v')  # Only this random isolated fixture project.


if __name__ == '__main__':
    os.umask(0o077)
    main()
