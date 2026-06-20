import fakeredis
from deploy.updater.agent import Agent, set_env_image_tag


def test_set_env_image_tag(tmp_path):
    env = tmp_path / '.env'
    env.write_text('IMAGE_TAG=0.2.0\nDB_PASSWORD=x\n')
    old = set_env_image_tag(str(env), '0.3.0')
    assert old == '0.2.0'
    assert 'IMAGE_TAG=0.3.0' in env.read_text()
    assert 'DB_PASSWORD=x' in env.read_text()


def test_set_env_image_tag_appends_if_missing(tmp_path):
    env = tmp_path / '.env'
    env.write_text('DB_PASSWORD=x\n')
    old = set_env_image_tag(str(env), '0.3.0')
    assert old == ''
    assert 'IMAGE_TAG=0.3.0' in env.read_text()
    assert 'DB_PASSWORD=x' in env.read_text()


def test_docker_apply_dry_run_emits_steps():
    r = fakeredis.FakeStrictRedis()
    job = {'id': 'd1', 'action': 'upgrade', 'mode': 'docker', 'target_version': '0.3.0',
           'from_version': '0.2.0', 'manifest': {'docker': {'image_tag': '0.3.0'}}}
    Agent(r, dry_run=True)._apply_docker(job, '/tmp/b.sql')
    import json
    steps = json.loads(r.get('erp:upgrade:progress:d1') or '{"steps":[]}')['steps']
    assert any('pull' in s['message'] or s['stage'] == 'apply' for s in steps)


def test_docker_apply_dry_run_sets_old_tag_placeholder():
    r = fakeredis.FakeStrictRedis()
    job = {'id': 'd2', 'action': 'upgrade', 'mode': 'docker', 'target_version': '0.3.0',
           'from_version': '0.2.0', 'manifest': {'docker': {'image_tag': '0.3.0'}}}
    Agent(r, dry_run=True)._apply_docker(job, '/tmp/b.sql')
    assert '_old_tag' in job


def test_docker_apply_excludes_updater_service(monkeypatch):
    """升级时 compose pull/up 必须排除 erp-updater 自身(否则重建会杀掉 agent)。"""
    r = fakeredis.FakeStrictRedis()
    calls = []
    job = {'id': 'd4', 'action': 'upgrade', 'mode': 'docker', 'target_version': '0.3.0',
           'from_version': '0.2.0', 'manifest': {'docker': {'image_tag': '0.3.0'}}}
    ag = Agent(r, dry_run=False)
    monkeypatch.setattr(ag, '_run', lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr('deploy.updater.agent.set_env_image_tag', lambda *a, **k: '0.2.0')
    ag._apply_docker(job, '/tmp/b.sql')
    flat = [' '.join(c) for c in calls]
    assert any('compose pull' in f for f in flat)
    assert any('compose up' in f for f in flat)
    assert all('erp-updater' not in f for f in flat)  # 不重建自身
    assert any(' app' in f for f in flat)              # 明确重建 app 服务


def test_docker_apply_rollback_uses_target_version(monkeypatch):
    """回滚 job 的 payload 无 manifest.docker;_apply_docker 应改用 target_version 作镜像 tag,
    而非读 manifest.docker.image_tag(否则 KeyError 'docker',回滚按钮形同虚设)。"""
    r = fakeredis.FakeStrictRedis()
    calls = []
    captured = {}
    job = {'id': 'rb1', 'action': 'rollback', 'mode': 'docker', 'target_version': '0.2.1',
           'from_version': '0.2.2', 'manifest': {'rollback_to': '0.2.1'}}
    ag = Agent(r, dry_run=False)
    monkeypatch.setattr(ag, '_run', lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr('deploy.updater.agent.set_env_image_tag',
                        lambda path, tag: captured.__setitem__('tag', tag) or '0.2.2')
    ag._apply_docker(job, '/tmp/b.sql')  # 不应抛 KeyError
    assert captured['tag'] == '0.2.1'           # 用 target_version 作新 tag
    assert job['_expected_version'] == '0.2.1'  # 健康门按回滚目标版本校验
    assert any('compose up' in ' '.join(c) for c in calls)


def test_rollback_docker_dry_run_emits_step():
    r = fakeredis.FakeStrictRedis()
    job = {'id': 'd3', 'action': 'upgrade', 'mode': 'docker', 'target_version': '0.3.0',
           'from_version': '0.2.0', '_old_tag': '0.2.0',
           'manifest': {'docker': {'image_tag': '0.3.0'}}}
    Agent(r, dry_run=True)._rollback(job, '/tmp/b.sql')
    import json
    steps = json.loads(r.get('erp:upgrade:progress:d3') or '{"steps":[]}')['steps']
    assert any('rollback' in s['stage'] for s in steps)
