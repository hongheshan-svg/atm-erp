import json
import fakeredis
from deploy.updater.agent import Agent


def test_dry_run_upgrade_emits_progress():
    r = fakeredis.FakeStrictRedis()
    job = {'id': 'j1', 'action': 'upgrade', 'mode': 'docker',
           'target_version': '0.3.0', 'from_version': '0.2.0',
           'manifest': {'docker': {'image_tag': '0.3.0'}}}
    r.lpush('erp:upgrade:queue', json.dumps(job))
    agent = Agent(r, dry_run=True)
    assert agent.run_once() is True
    # 进度写入了 progress key
    raw = r.get('erp:upgrade:progress:j1')
    assert raw is not None
    prog = json.loads(raw)
    assert prog['status'] in ('success', 'running', 'healthcheck')
    assert any(s['stage'] == 'plan' for s in prog['steps'])


def test_run_once_empty_returns_false():
    r = fakeredis.FakeStrictRedis()
    assert Agent(r, dry_run=True).run_once() is False
