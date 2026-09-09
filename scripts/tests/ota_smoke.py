"""Isolated Docker OTA rehearsal. v9.0.0 is a local fixture, never published."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('ota', ROOT / 'scripts/ota_runner.py')
ota = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ota)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18490)
    args = parser.parse_args()
    task = Path(tempfile.mkdtemp(prefix='lean-ota-smoke-'))
    project = 'lean-ota-smoke-' + secrets.token_hex(4)
    env_file = task / '.env.lean'
    password = 'Ota-isolated-test-' + secrets.token_hex(12)
    token = secrets.token_hex(32)
    values = {'LEAN_PROJECT_NAME': project, 'LEAN_IMAGE': project + ':initial', 'LEAN_HTTP_PORT': str(args.port),
              'LEAN_BIND_ADDRESS': '127.0.0.1', 'LEAN_ALLOWED_HOSTS': 'localhost,127.0.0.1',
              'LEAN_ENVIRONMENT': 'production', 'LEAN_DB_PASSWORD': secrets.token_hex(32),
              'LEAN_SECRET_KEY': secrets.token_hex(32), 'LEAN_ADMIN_PASSWORD': password, 'LEAN_OTA_AGENT_TOKEN': token}
    env_file.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
    os.chmod(env_file, 0o600)
    compose = ['docker', 'compose', '--env-file', str(env_file), '-f', str(ROOT / 'docker-compose.yml')]
    url = f'http://127.0.0.1:{args.port}'
    log = (task / 'rehearsal.log').open('w', encoding='utf-8')

    def command(argv):
        subprocess.run([str(arg) for arg in argv], check=True, stdout=log, stderr=log)

    def shell(code):
        command([*compose, 'exec', '-T', 'app', 'python', 'manage.py', 'shell', '-c', code])

    try:
        command(['bash', ROOT / 'install.sh', '--env-file', env_file])
        shell("from apps.core.models import Company; Company.objects.filter(pk=1).update(name='OTA 保留数据测试')")
        stage = task / 'fixture'
        stage.mkdir()
        files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
        for name in files:
            source = ROOT / name
            if source.is_file():
                destination = stage / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        shutil.copytree(ROOT / 'frontend/dist', stage / 'frontend/dist', dirs_exist_ok=True)
        (stage / 'backend/apps/core/version.py').write_text("VERSION = '9.0.0'\n")
        models = stage / 'backend/apps/core/models.py'
        models.write_text(models.read_text().replace('class Company(models.Model):',
                          "class Company(models.Model):\n    ota_test_marker = models.CharField(max_length=40, default='ota-smoke-marker')"))
        (stage / 'backend/apps/core/migrations/0005_ota_smoke.py').write_text(
            "from django.db import migrations, models\n"
            "class Migration(migrations.Migration):\n"
            "    dependencies = [('core', '0004_upgradejob')]\n"
            "    operations = [migrations.AddField(model_name='company', name='ota_test_marker', field=models.CharField(max_length=40, default='ota-smoke-marker'))]\n")
        (stage / 'INSTALL-MANIFEST.json').write_text(json.dumps({'version': 'v9.0.0', 'mode': 'docker', 'platform': ota.PLATFORM}))
        archive = task / 'fixture.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for source in stage.rglob('*'):
                if source.is_file():
                    bundle.write(source, 'fixture/' + source.relative_to(stage).as_posix())
        asset = {'url': f'https://github.com/{ota.REPO}/releases/download/v9.0.0/fixture.zip',
                 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'size': archive.stat().st_size,
                 'name': 'fixture.zip'}
        runner = ota.Runner(argparse.Namespace(mode='docker', root=ROOT, config=env_file, state_dir=task / 'state', url=url))
        assigned_asset = {**asset, '_runner_id': runner.state['runner_id']}
        # Test fixture creation only; admin authorization/idempotency is covered by API tests.
        shell("from apps.core.models import UpgradeJob; from apps.accounts.models import User; "
              f"UpgradeJob.objects.create(target='v9.0.0', mode='docker', platform={ota.PLATFORM!r}, "
              f"asset={assigned_asset!r}, created_by=User.objects.get(username='admin'))")
        original = urllib.request.urlopen

        def fixture_download(request, *positional, **kwargs):
            if getattr(request, 'full_url', request) == asset['url']:
                return archive.open('rb')
            return original(request, *positional, **kwargs)

        with patch.object(ota, 'trusted_asset', return_value=asset), patch.object(ota.urllib.request, 'urlopen', side_effect=fixture_download):
            runner.serve(once=True)
        runner.flush()
        with original(url + '/api/health/') as response:
            assert json.load(response)['version'] == '9.0.0'
        request = urllib.request.Request(url + '/api/auth/login/', data=json.dumps({'username': 'admin', 'password': password}).encode(), headers={'Content-Type': 'application/json'})
        with original(request) as response:
            access = json.load(response)['access']
        with original(urllib.request.Request(url + '/api/core/upgrade/', headers={'Authorization': 'Bearer ' + access})) as response:
            state = json.load(response)
        assert state['job']['status'] == 'succeeded', state
        backup = Path(state['job']['backup']) / 'database-and-uploads.zip'
        with zipfile.ZipFile(backup) as bundle:
            manifest = json.loads(bundle.read('manifest.json'))
            for name, digest in manifest['sha256'].items():
                assert hashlib.sha256(bundle.read(name)).hexdigest() == digest
        new_compose = runner.compose()
        proof = subprocess.check_output([*new_compose, 'exec', '-T', 'app', 'python', 'manage.py', 'shell', '-c',
            "from apps.core.models import Company; c=Company.objects.get(pk=1); assert c.name=='OTA 保留数据测试'; assert c.ota_test_marker=='ota-smoke-marker'; print('DATA_AND_MIGRATION_OK')"], text=True)
        assert 'DATA_AND_MIGRATION_OK' in proof
        print(f'OTA rehearsal passed: download hash, stop, backup hash, forward migration, retained company/admin, restart, target version, completed job. Evidence: {task}', flush=True)
    finally:
        log.close()
        # Only the newly generated isolated project/volumes are removed.
        subprocess.run([*compose, 'down', '-v'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
