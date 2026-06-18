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


def test_rollback_docker_dry_run_emits_step():
    r = fakeredis.FakeStrictRedis()
    job = {'id': 'd3', 'action': 'upgrade', 'mode': 'docker', 'target_version': '0.3.0',
           'from_version': '0.2.0', '_old_tag': '0.2.0',
           'manifest': {'docker': {'image_tag': '0.3.0'}}}
    Agent(r, dry_run=True)._rollback(job, '/tmp/b.sql')
    import json
    steps = json.loads(r.get('erp:upgrade:progress:d3') or '{"steps":[]}')['steps']
    assert any('rollback' in s['stage'] for s in steps)
