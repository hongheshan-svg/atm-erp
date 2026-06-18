import hashlib
import json

import fakeredis

from deploy.updater.agent import Agent, verify_sha256


def test_verify_sha256(tmp_path):
    f = tmp_path / 'a.bin'
    f.write_bytes(b'hello')
    digest = hashlib.sha256(b'hello').hexdigest()
    verify_sha256(str(f), digest)  # 不抛
    try:
        verify_sha256(str(f), 'deadbeef')
        assert False
    except ValueError:
        pass


def test_native_apply_dry_run():
    r = fakeredis.FakeStrictRedis()
    job = {'id': 'n1', 'action': 'upgrade', 'mode': 'native', 'target_version': '0.3.0',
           'from_version': '0.2.0',
           'manifest': {'native': {'tarball_url': 'https://github.com/x/y/releases/download/v0.3.0/erp.tar.gz', 'sha256': 'x'}}}
    Agent(r, dry_run=True)._apply_native(job, '/tmp/b.sql')
    steps = json.loads(r.get('erp:upgrade:progress:n1') or '{"steps":[]}')['steps']
    assert any(s['stage'] == 'apply' for s in steps)
