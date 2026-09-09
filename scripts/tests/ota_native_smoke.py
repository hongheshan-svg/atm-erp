"""Native-process OTA inside an isolated Linux test host with real PostgreSQL/Redis."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    ota = module('ota', ROOT / 'scripts/ota_runner.py')
    native = module('native', ROOT / 'scripts/native_install.py')
    initial_version = module('version', ROOT / 'backend/apps/core/version.py').VERSION
    task = Path(tempfile.mkdtemp(prefix='native-ota-'))
    config = task / 'config.json'
    native.create_config(config)
    values = json.loads(config.read_text())
    values.update(DB_HOST='native-ota-pg', DB_PASSWORD='native-ota-isolated-only',
                  REDIS_URL='redis://native-ota-redis:6379/0', DATA_DIR=str(task / 'data'),
                  HTTP_PORT=18495, APP_PORT=18496)
    config.write_text(json.dumps(values))
    log_path = task / 'native.log'
    log = log_path.open('a')
    runner = None
    current = ROOT

    def command(root, action):
        return [sys.executable, str(root / 'scripts/native_install.py'), action, '--config', str(config)]

    def shell(code):
        subprocess.run([str(native.python_path(task / 'data')), str(current / 'backend/manage.py'), 'shell', '-c', code],
                       cwd=current / 'backend', env=native.environment(values, task / 'data'), check=True, stdout=log, stderr=log)

    try:
        subprocess.run(command(ROOT, 'install'), check=True, stdout=log, stderr=log)
        subprocess.Popen(command(ROOT, 'start'), stdout=log, stderr=log)
        url = 'http://127.0.0.1:18495'
        for _ in range(60):
            try:
                with urllib.request.urlopen(url + '/api/health/', timeout=2) as response:
                    if json.load(response)['version'] == initial_version:
                        break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError('Native application did not start')
        shell("from apps.core.models import Company; Company.objects.filter(pk=1).update(name='原生 OTA 数据保留')")
        stage = task / 'fixture'
        stage.mkdir()
        for directory in ('backend', 'scripts'):
            shutil.copytree(ROOT / directory, stage / directory, ignore=shutil.ignore_patterns('__pycache__', 'uploads', '.venv'))
        shutil.copytree(ROOT / 'frontend/dist', stage / 'frontend/dist')
        shutil.copyfile(ROOT / 'docker-compose.yml', stage / 'docker-compose.yml')
        (stage / 'backend/apps/core/version.py').write_text("VERSION = '9.0.0'\n")
        models = stage / 'backend/apps/core/models.py'
        models.write_text(models.read_text().replace('class Company(models.Model):',
                          "class Company(models.Model):\n    ota_test_marker = models.CharField(max_length=40, default='native-ota')"))
        (stage / 'backend/apps/core/migrations/0005_ota_smoke.py').write_text(
            "from django.db import migrations, models\nclass Migration(migrations.Migration):\n"
            "    dependencies = [('core', '0004_upgradejob')]\n"
            "    operations = [migrations.AddField(model_name='company', name='ota_test_marker', field=models.CharField(max_length=40, default='native-ota'))]\n")
        (stage / 'INSTALL-MANIFEST.json').write_text(json.dumps({'version': 'v9.0.0', 'mode': 'native', 'platform': 'linux'}))
        archive = task / 'fixture.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for source in stage.rglob('*'):
                if source.is_file():
                    bundle.write(source, 'fixture/' + source.relative_to(stage).as_posix())
        asset = {'url': 'https://github.com/hongheshan-svg/atm-erp/releases/download/v9.0.0/fixture.zip',
                 'sha256': ota.file_hash(archive), 'size': archive.stat().st_size, 'name': 'fixture.zip'}
        runner = ota.Runner(argparse.Namespace(mode='native', root=ROOT, config=config, state_dir=task / 'state', url=url))
        assigned = {**asset, '_runner_id': runner.state['runner_id']}
        shell("from apps.core.models import UpgradeJob; from apps.accounts.models import User; "
              f"UpgradeJob.objects.create(target='v9.0.0', mode='native', platform='linux', asset={assigned!r}, created_by=User.objects.get(username='admin'))")
        original = urllib.request.urlopen

        def download(request, *args, **kwargs):
            return archive.open('rb') if getattr(request, 'full_url', request) == asset['url'] else original(request, *args, **kwargs)

        with patch.object(ota, 'trusted_asset', return_value=asset), patch.object(ota.urllib.request, 'urlopen', side_effect=download):
            runner.serve(once=True)
        runner.flush()
        current = runner.root
        with original(url + '/api/health/') as response:
            assert json.load(response)['version'] == '9.0.0'
        shell("from apps.core.models import Company,UpgradeJob; c=Company.objects.get(pk=1); assert c.name=='原生 OTA 数据保留'; assert c.ota_test_marker=='native-ota'; assert UpgradeJob.objects.get().status=='succeeded'")
        backup = next((task / 'state').glob('job-*/backup'))
        for name, digest in json.loads((backup / 'manifest.json').read_text())['sha256'].items():
            assert ota.file_hash(backup / name) == digest
        print('Native OTA passed: real Daphne/Nginx stop/start, PostgreSQL backup and forward migration, retained data, verified target version and completed job.', flush=True)
    finally:
        subprocess.run(command(current, 'stop'), stdout=log, stderr=log, check=False)
        log.close()
        print(log_path.read_text()[-1500:], flush=True)
        if runner:
            for path in (task / 'state').glob('job-*/upgrade.log'):
                print(path.read_text()[-2000:], flush=True)


if __name__ == '__main__':
    main()
