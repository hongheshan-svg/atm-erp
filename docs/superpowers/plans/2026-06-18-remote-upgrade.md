# ERP 软件版本远程升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 管理员在 ERP 后台一键远程升级整套系统(Docker 与原生 systemd 双形态),由宿主升级代理执行拉取/迁移/重启,失败自动回滚。

**Architecture:** 厂商发布公开清单(raw JSON)→ 后端 `upgrade_service` 检查版本/校验/单飞锁/建 `UpgradeJob`/向 Redis 投递任务 → 宿主特权代理(Docker:`erp-updater` 容器挂 docker.sock;原生:root systemd)取任务执行(pg_dump 备份 → 拉新 → 迁移 → 健康门 → 失败回滚),进度持久写 Redis+DB,前端断线后读持久 job。

**Tech Stack:** Django 4.2 + DRF + Channels(已用)、PostgreSQL、Redis(django-redis)、requests、Vue 3 + Element Plus + Pinia、Docker Compose、systemd。

## Global Constraints

- 清单默认 URL:`https://raw.githubusercontent.com/hongheshan-svg/atm-erp/main/manifest.json`,env `ERP_UPDATE_MANIFEST_URL` 可覆盖。
- SSRF 可信主机白名单(仅 HTTPS):`raw.githubusercontent.com`、`github.com`、`objects.githubusercontent.com`、`ghcr.io`。
- 版本比较:去前导 `v` 后按 semver 整型分段比较,函数 `compare_versions(a,b)->int` 返回 -1/0/1。
- 权限标识 `system:upgrade`(前端 `meta.permission` / `v-permission` / 后端 `PermissionMixin` 三处一致)。
- Redis 键:任务队列 `erp:upgrade:queue`;进度 `erp:upgrade:progress:<job_id>`;单飞锁 `erp:upgrade:lock`;进度频道 `erp:upgrade:events`。
- **Redis DB 必须一致**:后端 `get_redis_connection('default')` 用 CACHES 的 `REDIS_URL`(默认 `redis://redis:6379/1`,即 **DB 1**)。升级代理与 relay 必须连同一个 DB——Docker:`redis://redis:6379/1`;原生:`redis://127.0.0.1:6379/1`(原生 redis 在宿主 6379,非 Docker 的 6380)。切勿用 Celery 的 DB 0。
- `UpgradeJob.status` 取值:`pending|running|healthcheck|success|failed|rolled_back`;`action`:`upgrade|rollback`;`mode`:`docker|native`。
- 业务模型继承 `apps.core.models.BaseModel`;删除走 `soft_delete()`;查询走默认 `objects`。
- 视图保留 `PermissionMixin`;前端网络调用走 `frontend/src/api/system.ts`,不在组件内 `import axios`。
- core app 用**扁平文件**(如 `backup_service.py`),不建 `views/`/`services/` 子目录。
- 提交在 feature 分支 `feat/remote-upgrade`(禁止直接提交 main);commit message 结尾含
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- 后端测试:`python manage.py test apps.core.tests.<module>`;前端:`npm run test`。

---

## File Structure

| 文件 | 责任 |
|------|------|
| `backend/apps/core/version.py` | `APP_VERSION` / `DEPLOY_MODE` 读取 + `compare_versions` |
| `backend/config/urls.py`(改) | health 返回 `APP_VERSION` |
| `backend/apps/core/models.py`(追加 `UpgradeJob`) | 升级任务持久记录 |
| `backend/apps/core/manifest_client.py` | 拉取/校验/解析发布清单(SSRF 白名单) |
| `backend/apps/core/upgrade_service.py` | check_update(缓存)/perform/rollback/单飞锁/投递任务/查 job |
| `backend/apps/core/upgrade_views.py` | admin API(权限 `system:upgrade`) |
| `backend/apps/core/urls.py`(改) | 挂载 `/api/v1/system/...` |
| `backend/apps/core/consumers.py`(追加) | `UpgradeProgressConsumer` |
| `backend/apps/core/routing.py`(改) | 进度 WS 路由 |
| `backend/apps/core/management/commands/init_permissions.py`(改) | 追加 `system:upgrade` |
| `backend/apps/core/tests/test_upgrade_*.py` | 单测 |
| `deploy/updater/agent.py` | 代理核心循环 + 通用步骤 + 两分支 |
| `docker/updater/Dockerfile` | updater 容器镜像 |
| `docker-compose.yml`(改) | 追加 `erp-updater` 服务 |
| `deploy/updater/erp-updater.service` | 原生 systemd 单元 |
| `frontend/src/views/system/Upgrade.vue` | 升级页 |
| `frontend/src/api/system.ts`(追加) | 升级 API 封装 |
| `frontend/src/router/index.ts`(改) | 升级路由 |

---

## Task 1: 版本与部署模式管线 + 版本比较

**Files:**
- Create: `backend/apps/core/version.py`
- Modify: `backend/config/urls.py:17-19`
- Test: `backend/apps/core/tests/test_version.py`

**Interfaces:**
- Produces: `get_app_version() -> str`、`get_deploy_mode() -> str`、`compare_versions(a: str, b: str) -> int`。

- [ ] **Step 1: 写失败测试**

```python
# backend/apps/core/tests/test_version.py
from django.test import SimpleTestCase
from apps.core.version import compare_versions, get_app_version, get_deploy_mode


class CompareVersionsTest(SimpleTestCase):
    def test_basic_ordering(self):
        self.assertEqual(compare_versions('0.1.0', '0.2.0'), -1)
        self.assertEqual(compare_versions('0.2.0', '0.2.0'), 0)
        self.assertEqual(compare_versions('1.0.0', '0.9.9'), 1)

    def test_strips_leading_v(self):
        self.assertEqual(compare_versions('v0.2.0', '0.2.0'), 0)

    def test_uneven_segments(self):
        self.assertEqual(compare_versions('0.2', '0.2.0'), 0)
        self.assertEqual(compare_versions('0.2.1', '0.2'), 1)

    def test_env_defaults(self):
        # 未设置 env 时有稳妥默认值
        self.assertIsInstance(get_app_version(), str)
        self.assertIn(get_deploy_mode(), ('docker', 'native', 'unknown'))
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && python manage.py test apps.core.tests.test_version -v 2`
Expected: FAIL(ImportError: cannot import name ... from apps.core.version)

- [ ] **Step 3: 实现 version.py**

```python
# backend/apps/core/version.py
"""应用版本与部署模式来源,以及 semver 比较。"""
from __future__ import annotations

import os


def get_app_version() -> str:
    """当前运行版本。Docker 由 compose 注入 APP_VERSION=<image tag>;
    原生由部署脚本写入。缺省回退 '0.0.0'(开发态)。"""
    return os.environ.get('APP_VERSION', '0.0.0').strip() or '0.0.0'


def get_deploy_mode() -> str:
    """部署模式:docker | native | unknown。"""
    mode = os.environ.get('DEPLOY_MODE', '').strip().lower()
    return mode if mode in ('docker', 'native') else 'unknown'


def _parse(v: str) -> list[int]:
    v = v.strip()
    if v.startswith('v'):
        v = v[1:]
    parts = []
    for seg in v.split('.'):
        num = ''.join(ch for ch in seg if ch.isdigit())
        parts.append(int(num) if num else 0)
    return parts


def compare_versions(a: str, b: str) -> int:
    """返回 -1 (a<b) / 0 (a==b) / 1 (a>b),按 semver 整型分段比较。"""
    pa, pb = _parse(a), _parse(b)
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    for x, y in zip(pa, pb):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0
```

- [ ] **Step 4: 改 health 返回 APP_VERSION**

`backend/config/urls.py` 顶部加导入,并改 `api_health_check`:

```python
from apps.core.version import get_app_version  # 顶部导入区

def api_health_check(request):
    """Simple health check for Docker/Kubernetes."""
    return Response({'status': 'healthy', 'version': get_app_version()})
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `cd backend && python manage.py test apps.core.tests.test_version -v 2`
Expected: PASS(4 tests)

- [ ] **Step 6: 提交**

```bash
git add backend/apps/core/version.py backend/config/urls.py backend/apps/core/tests/test_version.py
git commit -m "feat(upgrade): APP_VERSION/DEPLOY_MODE 来源与 semver 比较,health 返回真实版本

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: UpgradeJob 模型 + 迁移

**Files:**
- Modify: `backend/apps/core/models.py`(文件末尾追加)
- Test: `backend/apps/core/tests/test_upgrade_model.py`

**Interfaces:**
- Produces: `UpgradeJob` 模型,字段见 Global Constraints;`UpgradeJob.STATUS_*`、`ACTION_*`、`MODE_*` 常量;方法 `append_step(stage, message, level='info')`。

- [ ] **Step 1: 写失败测试**

```python
# backend/apps/core/tests/test_upgrade_model.py
from django.test import TestCase
from apps.core.models import UpgradeJob


class UpgradeJobTest(TestCase):
    def test_create_defaults(self):
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_UPGRADE, mode=UpgradeJob.MODE_DOCKER,
            from_version='0.1.0', target_version='0.2.0',
        )
        self.assertEqual(job.status, UpgradeJob.STATUS_PENDING)
        self.assertEqual(job.steps, [])

    def test_append_step(self):
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_UPGRADE, mode=UpgradeJob.MODE_DOCKER,
            from_version='0.1.0', target_version='0.2.0',
        )
        job.append_step('backup', 'pg_dump done')
        job.refresh_from_db()
        self.assertEqual(len(job.steps), 1)
        self.assertEqual(job.steps[0]['stage'], 'backup')
        self.assertEqual(job.steps[0]['level'], 'info')
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && python manage.py test apps.core.tests.test_upgrade_model -v 2`
Expected: FAIL(ImportError: cannot import name 'UpgradeJob')

- [ ] **Step 3: 在 `backend/apps/core/models.py` 末尾追加模型**

```python
class UpgradeJob(BaseModel):
    """远程升级任务(持久记录,供进度/审计/回滚)。"""

    ACTION_UPGRADE = 'upgrade'
    ACTION_ROLLBACK = 'rollback'
    ACTION_CHOICES = [(ACTION_UPGRADE, '升级'), (ACTION_ROLLBACK, '回滚')]

    MODE_DOCKER = 'docker'
    MODE_NATIVE = 'native'
    MODE_CHOICES = [(MODE_DOCKER, 'Docker'), (MODE_NATIVE, '原生')]

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_HEALTHCHECK = 'healthcheck'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_ROLLED_BACK = 'rolled_back'
    STATUS_CHOICES = [
        (STATUS_PENDING, '排队中'), (STATUS_RUNNING, '执行中'),
        (STATUS_HEALTHCHECK, '健康检查'), (STATUS_SUCCESS, '成功'),
        (STATUS_FAILED, '失败'), (STATUS_ROLLED_BACK, '已回滚'),
    ]

    action = models.CharField('动作', max_length=16, choices=ACTION_CHOICES)
    mode = models.CharField('部署模式', max_length=16, choices=MODE_CHOICES)
    from_version = models.CharField('升级前版本', max_length=32)
    target_version = models.CharField('目标版本', max_length=32)
    status = models.CharField('状态', max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    steps = models.JSONField('步骤日志', default=list, blank=True)
    db_backup_path = models.CharField('DB 备份路径', max_length=512, blank=True, default='')
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    finished_at = models.DateTimeField('结束时间', null=True, blank=True)
    triggered_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='upgrade_jobs', verbose_name='触发人',
    )

    class Meta:
        verbose_name = '升级任务'
        verbose_name_plural = '升级任务'
        ordering = ['-created_at']

    def append_step(self, stage: str, message: str, level: str = 'info') -> None:
        from django.utils import timezone
        entry = {'ts': timezone.now().isoformat(), 'stage': stage, 'message': message, 'level': level}
        self.steps = (self.steps or []) + [entry]
        self.save(update_fields=['steps', 'updated_at'])
```

> 注:`accounts.User` 为实际用户模型;若 app label 不同,先 `grep -n "class User" backend/apps/accounts/models.py` 确认并用 `settings.AUTH_USER_MODEL`。

- [ ] **Step 4: 生成并应用迁移**

Run:
```bash
cd backend && python manage.py makemigrations core && python manage.py migrate
```
Expected: 生成 `core/migrations/00xx_upgradejob.py`,migrate OK。

- [ ] **Step 5: 运行测试,确认通过**

Run: `cd backend && python manage.py test apps.core.tests.test_upgrade_model -v 2`
Expected: PASS(2 tests)

- [ ] **Step 6: 提交**

```bash
git add backend/apps/core/models.py backend/apps/core/migrations/ backend/apps/core/tests/test_upgrade_model.py
git commit -m "feat(upgrade): UpgradeJob 模型与迁移

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 发布清单客户端(SSRF 白名单 + 解析)

**Files:**
- Create: `backend/apps/core/manifest_client.py`
- Test: `backend/apps/core/tests/test_manifest_client.py`

**Interfaces:**
- Consumes: 无。
- Produces:
  - `ALLOWED_HOSTS: set[str]`
  - `validate_url(url: str) -> None`(非法抛 `ManifestError`)
  - `Manifest`(dataclass: `latest_version, published_at, release_notes_md, min_upgradable_from, docker: dict, native: dict, raw: dict`)
  - `fetch_manifest(url: str, *, timeout=10) -> Manifest`
  - `ManifestError`(异常)

- [ ] **Step 1: 写失败测试**

```python
# backend/apps/core/tests/test_manifest_client.py
import json
from unittest import mock
from django.test import SimpleTestCase
from apps.core.manifest_client import validate_url, fetch_manifest, ManifestError

SAMPLE = {
    "latest_version": "0.3.0", "published_at": "2026-07-01T00:00:00Z",
    "release_notes_md": "## 0.3.0", "min_upgradable_from": "0.2.0",
    "docker": {"registry": "ghcr.io", "owner": "hongheshan-svg", "image_tag": "0.3.0",
               "digests": {"backend": "sha256:a", "frontend": "sha256:b"}},
    "native": {"tarball_url": "https://github.com/hongheshan-svg/atm-erp/releases/download/v0.3.0/erp-0.3.0.tar.gz",
               "sha256": "deadbeef"},
}


class ValidateUrlTest(SimpleTestCase):
    def test_rejects_non_https(self):
        with self.assertRaises(ManifestError):
            validate_url('http://raw.githubusercontent.com/x')

    def test_rejects_untrusted_host(self):
        with self.assertRaises(ManifestError):
            validate_url('https://evil.example.com/manifest.json')

    def test_allows_trusted(self):
        validate_url('https://raw.githubusercontent.com/hongheshan-svg/atm-erp/main/manifest.json')


class FetchManifestTest(SimpleTestCase):
    def test_parses(self):
        resp = mock.Mock(status_code=200, text=json.dumps(SAMPLE))
        resp.json.return_value = SAMPLE
        resp.raise_for_status = mock.Mock()
        with mock.patch('apps.core.manifest_client.requests.get', return_value=resp) as g:
            m = fetch_manifest('https://raw.githubusercontent.com/x/y/main/manifest.json')
        g.assert_called_once()
        self.assertEqual(m.latest_version, '0.3.0')
        self.assertEqual(m.min_upgradable_from, '0.2.0')
        self.assertEqual(m.docker['image_tag'], '0.3.0')
        self.assertEqual(m.native['sha256'], 'deadbeef')
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && python manage.py test apps.core.tests.test_manifest_client -v 2`
Expected: FAIL(ImportError)

- [ ] **Step 3: 实现 manifest_client.py**

```python
# backend/apps/core/manifest_client.py
"""发布清单拉取与校验。仅允许 HTTPS + 可信主机(防 SSRF)。"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

ALLOWED_HOSTS = {
    'raw.githubusercontent.com', 'github.com',
    'objects.githubusercontent.com', 'ghcr.io',
}


class ManifestError(Exception):
    pass


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != 'https':
        raise ManifestError(f'only HTTPS allowed: {url}')
    host = parsed.hostname or ''
    if host not in ALLOWED_HOSTS and not any(host.endswith('.' + h) for h in ALLOWED_HOSTS):
        raise ManifestError(f'untrusted host: {host}')


@dataclass
class Manifest:
    latest_version: str
    published_at: str = ''
    release_notes_md: str = ''
    min_upgradable_from: str = ''
    docker: dict = field(default_factory=dict)
    native: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


def fetch_manifest(url: str, *, timeout: int = 10) -> Manifest:
    validate_url(url)
    try:
        resp = requests.get(url, timeout=timeout, headers={'Accept': 'application/json'})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise ManifestError(f'failed to fetch manifest: {exc}') from exc
    if not isinstance(data, dict) or 'latest_version' not in data:
        raise ManifestError('invalid manifest: missing latest_version')
    return Manifest(
        latest_version=str(data['latest_version']),
        published_at=str(data.get('published_at', '')),
        release_notes_md=str(data.get('release_notes_md', '')),
        min_upgradable_from=str(data.get('min_upgradable_from', '')),
        docker=data.get('docker') or {},
        native=data.get('native') or {},
        raw=data,
    )
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `cd backend && python manage.py test apps.core.tests.test_manifest_client -v 2`
Expected: PASS(4 tests)

- [ ] **Step 5: 提交**

```bash
git add backend/apps/core/manifest_client.py backend/apps/core/tests/test_manifest_client.py
git commit -m "feat(upgrade): 发布清单客户端(SSRF 白名单 + 解析)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 升级服务(检查缓存 / 单飞锁 / 投递任务 / 查 job)

**Files:**
- Create: `backend/apps/core/upgrade_service.py`
- Test: `backend/apps/core/tests/test_upgrade_service.py`

**Interfaces:**
- Consumes: `version.get_app_version/get_deploy_mode/compare_versions`、`manifest_client.fetch_manifest`、`models.UpgradeJob`。
- Produces:
  - `MANIFEST_URL`(从 `settings.ERP_UPDATE_MANIFEST_URL`)
  - `check_update(force=False) -> dict`(键:`current_version,latest_version,has_update,deploy_mode,release_notes_md,min_upgradable_from,cached,warning`)
  - `perform_upgrade(user) -> UpgradeJob`(建 job + 单飞锁 + LPUSH 队列;锁占用抛 `UpgradeBusy`;无更新抛 `NoUpdateAvailable`;不满足 min 抛 `UpgradeNotAllowed`)
  - `perform_rollback(user) -> UpgradeJob`
  - `get_job(job_id) -> UpgradeJob | None`、`list_jobs(limit=20)`
  - 异常类:`UpgradeBusy, NoUpdateAvailable, UpgradeNotAllowed`

- [ ] **Step 1: 在 settings 增加配置**

`backend/config/settings.py` 增加(env 读取区,用 `config()`):

```python
ERP_UPDATE_MANIFEST_URL = config(
    'ERP_UPDATE_MANIFEST_URL',
    default='https://raw.githubusercontent.com/hongheshan-svg/atm-erp/main/manifest.json',
)
```

- [ ] **Step 2: 写失败测试**

```python
# backend/apps/core/tests/test_upgrade_service.py
from unittest import mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.core import upgrade_service as svc
from apps.core.manifest_client import Manifest
from apps.core.models import UpgradeJob

User = get_user_model()


def _manifest(latest='0.3.0', minfrom='0.0.0'):
    return Manifest(latest_version=latest, min_upgradable_from=minfrom,
                    docker={'image_tag': latest}, native={'sha256': 'x'},
                    release_notes_md='notes')


class CheckUpdateTest(TestCase):
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest')
    def test_has_update(self, fetch, _v):
        fetch.return_value = _manifest('0.3.0')
        info = svc.check_update(force=True)
        self.assertTrue(info['has_update'])
        self.assertEqual(info['latest_version'], '0.3.0')

    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.3.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest')
    def test_no_update(self, fetch, _v):
        fetch.return_value = _manifest('0.3.0')
        info = svc.check_update(force=True)
        self.assertFalse(info['has_update'])


class PerformUpgradeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='admin', employee_id='A1')
        svc._release_lock()  # 保证干净

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest', return_value=_manifest('0.3.0'))
    @mock.patch('apps.core.upgrade_service._enqueue')
    def test_creates_job_and_enqueues(self, enq, *_):
        job = svc.perform_upgrade(self.user)
        self.assertEqual(job.action, UpgradeJob.ACTION_UPGRADE)
        self.assertEqual(job.target_version, '0.3.0')
        enq.assert_called_once()

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest', return_value=_manifest('0.3.0'))
    @mock.patch('apps.core.upgrade_service._enqueue')
    def test_single_flight(self, *_):
        svc.perform_upgrade(self.user)
        with self.assertRaises(svc.UpgradeBusy):
            svc.perform_upgrade(self.user)

    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.3.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest', return_value=_manifest('0.3.0'))
    def test_no_update_raises(self, *_):
        with self.assertRaises(svc.NoUpdateAvailable):
            svc.perform_upgrade(self.user)
```

- [ ] **Step 3: 运行,确认失败**

Run: `cd backend && python manage.py test apps.core.tests.test_upgrade_service -v 2`
Expected: FAIL(ImportError)

- [ ] **Step 4: 实现 upgrade_service.py**

```python
# backend/apps/core/upgrade_service.py
"""升级编排:检查更新(缓存)、单飞锁、建 job、投递任务到 Redis 队列。"""
from __future__ import annotations

import json

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django_redis import get_redis_connection

from .manifest_client import ManifestError, fetch_manifest
from .models import UpgradeJob
from .version import compare_versions, get_app_version, get_deploy_mode

MANIFEST_URL = settings.ERP_UPDATE_MANIFEST_URL
CACHE_KEY = 'erp:upgrade:check'
CACHE_TTL = 1200  # 20min
QUEUE_KEY = 'erp:upgrade:queue'
LOCK_KEY = 'erp:upgrade:lock'
LOCK_TTL = 3600  # 安全上限,避免死锁


class UpgradeBusy(Exception):
    pass


class NoUpdateAvailable(Exception):
    pass


class UpgradeNotAllowed(Exception):
    pass


def _redis():
    return get_redis_connection('default')


def _acquire_lock() -> bool:
    return bool(_redis().set(LOCK_KEY, '1', nx=True, ex=LOCK_TTL))


def _release_lock() -> None:
    _redis().delete(LOCK_KEY)


def _enqueue(job: UpgradeJob, manifest_raw: dict) -> None:
    payload = {
        'id': str(job.id), 'action': job.action, 'mode': job.mode,
        'target_version': job.target_version, 'from_version': job.from_version,
        'manifest': manifest_raw,
    }
    _redis().lpush(QUEUE_KEY, json.dumps(payload))


def check_update(force: bool = False) -> dict:
    current = get_app_version()
    if not force:
        cached = cache.get(CACHE_KEY)
        if cached:
            cached['cached'] = True
            return cached
    try:
        m = fetch_manifest(MANIFEST_URL)
    except ManifestError as exc:
        return {
            'current_version': current, 'latest_version': current, 'has_update': False,
            'deploy_mode': get_deploy_mode(), 'release_notes_md': '',
            'min_upgradable_from': '', 'cached': False, 'warning': str(exc),
        }
    info = {
        'current_version': current, 'latest_version': m.latest_version,
        'has_update': compare_versions(current, m.latest_version) < 0,
        'deploy_mode': get_deploy_mode(), 'release_notes_md': m.release_notes_md,
        'min_upgradable_from': m.min_upgradable_from, 'cached': False, 'warning': '',
    }
    cache.set(CACHE_KEY, info, CACHE_TTL)
    return info


def perform_upgrade(user) -> UpgradeJob:
    current = get_app_version()
    m = fetch_manifest(MANIFEST_URL)
    if compare_versions(current, m.latest_version) >= 0:
        raise NoUpdateAvailable('current version is latest')
    if m.min_upgradable_from and compare_versions(current, m.min_upgradable_from) < 0:
        raise UpgradeNotAllowed(
            f'must upgrade to {m.min_upgradable_from} first (current {current})')
    if not _acquire_lock():
        raise UpgradeBusy('another upgrade is in progress')
    try:
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_UPGRADE, mode=get_deploy_mode(),
            from_version=current, target_version=m.latest_version,
            status=UpgradeJob.STATUS_PENDING, triggered_by=user,
            started_at=timezone.now(),
        )
        _enqueue(job, m.raw)
        return job
    except Exception:
        _release_lock()
        raise


def perform_rollback(user) -> UpgradeJob:
    last = (UpgradeJob.objects.filter(action=UpgradeJob.ACTION_UPGRADE,
                                      status=UpgradeJob.STATUS_SUCCESS)
            .order_by('-created_at').first())
    if last is None:
        raise NoUpdateAvailable('no successful upgrade to roll back')
    if not _acquire_lock():
        raise UpgradeBusy('another upgrade is in progress')
    try:
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_ROLLBACK, mode=get_deploy_mode(),
            from_version=get_app_version(), target_version=last.from_version,
            status=UpgradeJob.STATUS_PENDING, triggered_by=user, started_at=timezone.now(),
        )
        _enqueue(job, {'rollback_to': last.from_version})
        return job
    except Exception:
        _release_lock()
        raise


def get_job(job_id):
    return UpgradeJob.objects.filter(id=job_id).first()


def list_jobs(limit: int = 20):
    return list(UpgradeJob.objects.all()[:limit])
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `cd backend && python manage.py test apps.core.tests.test_upgrade_service -v 2`
Expected: PASS(5 tests)

- [ ] **Step 6: 提交**

```bash
git add backend/apps/core/upgrade_service.py backend/apps/core/tests/test_upgrade_service.py backend/config/settings.py
git commit -m "feat(upgrade): 升级服务(检查缓存/单飞锁/投递任务/查 job)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: API 视图 + 路由 + 权限种子

**Files:**
- Create: `backend/apps/core/upgrade_views.py`
- Modify: `backend/apps/core/urls.py`、`backend/apps/core/management/commands/init_permissions.py`
- Test: `backend/apps/core/tests/test_upgrade_api.py`

**Interfaces:**
- Consumes: `upgrade_service` 全部公开函数。
- Produces: 端点(见 Global Constraints §6 spec):`GET /api/v1/system/version`、`GET /api/v1/system/check-update`、`POST /api/v1/system/upgrade`、`GET /api/v1/system/upgrade/jobs/<id>`、`GET /api/v1/system/upgrade/jobs`、`POST /api/v1/system/rollback`。权限 `system:upgrade`。

- [ ] **Step 1: 写失败测试**

```python
# backend/apps/core/tests/test_upgrade_api.py
from unittest import mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.core import upgrade_service as svc
from apps.core.manifest_client import Manifest

User = get_user_model()


class UpgradeApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='admin', employee_id='A1',
                                        is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        svc._release_lock()

    @mock.patch('apps.core.upgrade_views.upgrade_service.get_app_version', return_value='0.2.0')
    def test_version_endpoint(self, _v):
        r = self.client.get('/api/v1/system/version')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['version'], '0.2.0')

    @mock.patch('apps.core.upgrade_views.upgrade_service.check_update')
    def test_check_update(self, chk):
        chk.return_value = {'current_version': '0.2.0', 'latest_version': '0.3.0',
                            'has_update': True, 'deploy_mode': 'docker',
                            'release_notes_md': 'n', 'min_upgradable_from': '',
                            'cached': False, 'warning': ''}
        r = self.client.get('/api/v1/system/check-update?force=1')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['has_update'])

    @mock.patch('apps.core.upgrade_views.upgrade_service.perform_upgrade')
    def test_upgrade_returns_job(self, perform):
        perform.return_value = mock.Mock(id='abc', status='pending')
        r = self.client.post('/api/v1/system/upgrade')
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()['job_id'], 'abc')

    @mock.patch('apps.core.upgrade_views.upgrade_service.perform_upgrade',
                side_effect=svc.UpgradeBusy('busy'))
    def test_upgrade_busy_409(self, _p):
        r = self.client.post('/api/v1/system/upgrade')
        self.assertEqual(r.status_code, 409)
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && python manage.py test apps.core.tests.test_upgrade_api -v 2`
Expected: FAIL(404 / ImportError)

- [ ] **Step 3: 实现 upgrade_views.py**

```python
# backend/apps/core/upgrade_views.py
"""远程升级 admin API。权限 system:upgrade。"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import upgrade_service
from .permission_mixin import PermissionMixin
from .version import get_app_version, get_deploy_mode


class _UpgradePermission(PermissionMixin):
    permission_module = 'system'
    permission_resource = 'upgrade'


class SystemVersionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'version': upgrade_service.get_app_version(),
                         'deploy_mode': get_deploy_mode()})


class CheckUpdateView(_UpgradePermission, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        force = request.query_params.get('force') in ('1', 'true', 'True')
        return Response(upgrade_service.check_update(force=force))


class PerformUpgradeView(_UpgradePermission, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            job = upgrade_service.perform_upgrade(request.user)
        except upgrade_service.UpgradeBusy as e:
            return Response({'detail': str(e), 'code': 'UPGRADE_BUSY'}, status=status.HTTP_409_CONFLICT)
        except upgrade_service.NoUpdateAvailable as e:
            return Response({'detail': str(e), 'code': 'ALREADY_UP_TO_DATE'}, status=status.HTTP_409_CONFLICT)
        except upgrade_service.UpgradeNotAllowed as e:
            return Response({'detail': str(e), 'code': 'UPGRADE_NOT_ALLOWED'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'job_id': str(job.id), 'status': job.status}, status=status.HTTP_202_ACCEPTED)


class RollbackView(_UpgradePermission, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            job = upgrade_service.perform_rollback(request.user)
        except upgrade_service.UpgradeBusy as e:
            return Response({'detail': str(e), 'code': 'UPGRADE_BUSY'}, status=status.HTTP_409_CONFLICT)
        except upgrade_service.NoUpdateAvailable as e:
            return Response({'detail': str(e), 'code': 'NO_ROLLBACK'}, status=status.HTTP_409_CONFLICT)
        return Response({'job_id': str(job.id), 'status': job.status}, status=status.HTTP_202_ACCEPTED)


def _job_dict(job):
    return {
        'id': str(job.id), 'action': job.action, 'mode': job.mode,
        'from_version': job.from_version, 'target_version': job.target_version,
        'status': job.status, 'steps': job.steps,
        'started_at': job.started_at, 'finished_at': job.finished_at,
    }


class UpgradeJobDetailView(_UpgradePermission, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        job = upgrade_service.get_job(job_id)
        if job is None:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_job_dict(job))


class UpgradeJobListView(_UpgradePermission, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([_job_dict(j) for j in upgrade_service.list_jobs()])
```

> 注:若 `PermissionMixin` 要求设置 `context_role_fields` 或其它类属性,按 `code_rule_views.py` 的既有用法补齐;先 `sed -n '1,40p' backend/apps/core/code_rule_views.py` 参考。

- [ ] **Step 4: 挂路由**

`backend/apps/core/urls.py`:导入并在 `urlpatterns` 追加(放在 router 之外的显式 path 区):

```python
from .upgrade_views import (
    CheckUpdateView, PerformUpgradeView, RollbackView,
    SystemVersionView, UpgradeJobDetailView, UpgradeJobListView,
)

# urlpatterns 内追加:
    path('system/version', SystemVersionView.as_view()),
    path('system/check-update', CheckUpdateView.as_view()),
    path('system/upgrade', PerformUpgradeView.as_view()),
    path('system/upgrade/jobs', UpgradeJobListView.as_view()),
    path('system/upgrade/jobs/<uuid:job_id>', UpgradeJobDetailView.as_view()),
    path('system/rollback', RollbackView.as_view()),
```

> 注:确认 core urls 的总前缀是否已是 `/api/v1/`;若 core 已挂在 `api/v1/` 下(见 `config/urls.py`),此处用相对 `system/...` 即可。先 `grep -n "apps.core.urls\|include" backend/config/urls.py`。

- [ ] **Step 5: 种入权限**

在 `init_permissions.py` 的 system 模块树下,按既有 `ops()`/节点写法追加一个操作权限节点,code 为 `system:upgrade`(菜单/页面访问)与 `system:upgrade:execute`(执行)。最小追加(贴合现有 `node()/ops()` 风格):

```python
# 在 system 模块子节点列表中加入:
{'code': 'system:upgrade', 'name': '系统升级', 'type': 'menu', 'sort_order': 95,
 'children': [
     {'code': 'system:upgrade:execute', 'name': '执行升级', 'type': 'operation', 'sort_order': 1},
 ]},
```

> 注:实际字段名/嵌套以文件现有写法为准;先 `sed -n '1,120p' backend/apps/core/management/commands/init_permissions.py` 找到 system 模块定义处对齐。前端 `meta.permission` 与 `v-permission` 统一用 `system:upgrade`。

- [ ] **Step 6: 运行测试,确认通过**

Run: `cd backend && python manage.py test apps.core.tests.test_upgrade_api -v 2`
Expected: PASS(4 tests)

- [ ] **Step 7: 提交**

```bash
git add backend/apps/core/upgrade_views.py backend/apps/core/urls.py backend/apps/core/management/commands/init_permissions.py backend/apps/core/tests/test_upgrade_api.py
git commit -m "feat(upgrade): admin API + 路由 + system:upgrade 权限

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 进度 WebSocket 消费者

**Files:**
- Modify: `backend/apps/core/consumers.py`、`backend/apps/core/routing.py`
- Test: `backend/apps/core/tests/test_upgrade_ws.py`

**Interfaces:**
- Consumes: 现有 `JWTAuthMiddlewareStack`(asgi)。
- Produces: WS 路由 `ws/system/upgrade/<job_id>/`;`UpgradeProgressConsumer` 加入组 `upgrade_<job_id>`;辅助 `push_upgrade_progress(job_id, payload)`(供后端把 Redis 进度转发到组——由一个轮询任务或 perform 时不直接用,主用途是 UI 直连)。

- [ ] **Step 1: 写测试(连接 + 接收)**

```python
# backend/apps/core/tests/test_upgrade_ws.py
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from django.test import TransactionTestCase
from asgiref.sync import async_to_sync
from apps.core.consumers import UpgradeProgressConsumer


class UpgradeWsTest(TransactionTestCase):
    def test_receives_group_message(self):
        async def run():
            comm = WebsocketCommunicator(
                UpgradeProgressConsumer.as_asgi(), '/ws/system/upgrade/job1/')
            comm.scope['url_route'] = {'kwargs': {'job_id': 'job1'}}
            connected, _ = await comm.connect()
            assert connected
            layer = get_channel_layer()
            await layer.group_send('upgrade_job1',
                                   {'type': 'upgrade.progress', 'data': {'stage': 'pull'}})
            msg = await comm.receive_json_from(timeout=3)
            assert msg['stage'] == 'pull'
            await comm.disconnect()
        async_to_sync(run)()
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && python manage.py test apps.core.tests.test_upgrade_ws -v 2`
Expected: FAIL(ImportError: UpgradeProgressConsumer)

- [ ] **Step 3: 在 `consumers.py` 追加消费者**

```python
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class UpgradeProgressConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.job_id = self.scope['url_route']['kwargs']['job_id']
        self.group = f'upgrade_{self.job_id}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def upgrade_progress(self, event):
        await self.send_json(event['data'])
```

- [ ] **Step 4: 在 `routing.py` 追加路由**

```python
from .consumers import UpgradeProgressConsumer  # 顶部
# websocket_urlpatterns 内追加:
    re_path(r'ws/system/upgrade/(?P<job_id>[^/]+)/$', UpgradeProgressConsumer.as_asgi()),
```

> 注:若 `routing.py` 用 `path` 而非 `re_path`,按现有写法用 `path('ws/system/upgrade/<job_id>/', ...)`。先看文件首行导入。

- [ ] **Step 5: 运行测试,确认通过**

Run: `cd backend && python manage.py test apps.core.tests.test_upgrade_ws -v 2`
Expected: PASS(1 test)

- [ ] **Step 6: 提交**

```bash
git add backend/apps/core/consumers.py backend/apps/core/routing.py backend/apps/core/tests/test_upgrade_ws.py
git commit -m "feat(upgrade): 进度 WebSocket 消费者

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 宿主升级代理 — 核心循环 + 通用步骤(dry-run)

**Files:**
- Create: `deploy/updater/agent.py`、`deploy/updater/__init__.py`
- Test: `deploy/updater/test_agent.py`

**Interfaces:**
- Consumes: Redis 队列 `erp:upgrade:queue`、进度键、Django `UpgradeJob`(代理以独立进程导入 Django ORM,或仅写 Redis——本计划:代理通过 Redis 写进度,并通过 Redis 频道通知后端;DB 写入由后端轮询落库)。
- Produces:
  - `class Agent`(`__init__(redis_client, *, dry_run=False)`)
  - `Agent.run_once() -> bool`(取一个任务并处理,无任务返回 False)
  - `Agent.handle(job: dict)`(分派 upgrade/rollback)
  - 钩子方法(子步骤):`backup_db(job)`、`health_gate(job)->bool`、`report(job_id, stage, message, level='info')`
  - `progress_channel(job_id)`、`group_send_progress(...)`(写 `erp:upgrade:progress:<id>` + publish)

- [ ] **Step 1: 写测试(dry-run 处理一个任务,产出进度)**

```python
# deploy/updater/test_agent.py
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
```

- [ ] **Step 2: 安装测试依赖并运行,确认失败**

Run: `pip install fakeredis && cd /Users/zhengshan/projects/atm-erp && python -m pytest deploy/updater/test_agent.py -v`
Expected: FAIL(ModuleNotFoundError: deploy.updater.agent)

- [ ] **Step 3: 实现 agent.py(核心 + dry-run;Docker/native 具体命令在 Task 8/9 填充)**

```python
# deploy/updater/agent.py
"""宿主升级代理:从 Redis 取升级任务,执行备份/拉新/迁移/健康门/回滚,
进度持久写 Redis(后端轮询落库 + 转发 WS)。本文件含核心循环与通用步骤;
Docker/native 具体执行在 _apply_docker / _apply_native。"""
from __future__ import annotations

import json
import os
import subprocess
import time

QUEUE_KEY = 'erp:upgrade:queue'
PROGRESS_PREFIX = 'erp:upgrade:progress:'
LOCK_KEY = 'erp:upgrade:lock'
HEALTH_URL = os.environ.get('ERP_HEALTH_URL', 'http://localhost/api/v1/health/')
HEALTH_TIMEOUT = int(os.environ.get('ERP_HEALTH_TIMEOUT', '600'))
PROJECT_DIR = os.environ.get('ERP_PROJECT_DIR', '/app')


class Agent:
    def __init__(self, redis_client, *, dry_run: bool = False):
        self.r = redis_client
        self.dry_run = dry_run

    # ---- 进度 ----
    def _progress_key(self, job_id: str) -> str:
        return PROGRESS_PREFIX + job_id

    def report(self, job: dict, stage: str, message: str, level: str = 'info',
               status: str | None = None) -> None:
        key = self._progress_key(job['id'])
        raw = self.r.get(key)
        state = json.loads(raw) if raw else {'id': job['id'], 'steps': [], 'status': 'running'}
        state['steps'].append({'stage': stage, 'message': message, 'level': level, 'ts': time.time()})
        if status:
            state['status'] = status
        self.r.set(key, json.dumps(state), ex=86400)
        # 通知后端(后端订阅此频道,落库 + 转发 WS)
        self.r.publish('erp:upgrade:events', json.dumps({'job_id': job['id'], 'state': state}))

    # ---- 通用步骤 ----
    def backup_db(self, job: dict) -> str:
        ts = time.strftime('%Y%m%d-%H%M%S')
        path = f'/var/backups/erp/pre-upgrade-{ts}.sql'
        self.report(job, 'backup', f'pg_dump -> {path}')
        if self.dry_run:
            return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._run(['pg_dump', '-f', path], env_db=True)
        return path

    def health_gate(self, job: dict) -> bool:
        self.report(job, 'healthcheck', f'polling {HEALTH_URL}', status='healthcheck')
        if self.dry_run:
            return True
        import requests
        deadline = time.time() + HEALTH_TIMEOUT
        while time.time() < deadline:
            try:
                resp = requests.get(HEALTH_URL, timeout=5)
                if resp.status_code == 200 and \
                        resp.json().get('version') == job['target_version']:
                    return True
            except Exception:
                pass
            time.sleep(5)
        return False

    def _run(self, cmd: list[str], *, cwd: str | None = None, env_db: bool = False) -> None:
        env = dict(os.environ)
        subprocess.run(cmd, cwd=cwd or PROJECT_DIR, env=env, check=True)

    # ---- 分派 ----
    def handle(self, job: dict) -> None:
        self.report(job, 'plan', f"{job['action']} -> {job.get('target_version')} (mode={job['mode']}, dry_run={self.dry_run})", status='running')
        try:
            backup = self.backup_db(job)
            if job['mode'] == 'docker':
                self._apply_docker(job, backup)
            else:
                self._apply_native(job, backup)
            if self.health_gate(job):
                self.report(job, 'done', 'health OK', status='success')
            else:
                self.report(job, 'healthcheck', 'health gate failed, rolling back', level='error')
                self._rollback(job, backup)
                self.report(job, 'done', 'rolled back', status='rolled_back')
        except Exception as exc:  # noqa: BLE001
            self.report(job, 'error', str(exc), level='error')
            try:
                self._rollback(job, locals().get('backup', ''))
                self.report(job, 'done', 'rolled back after error', status='rolled_back')
            except Exception as rexc:  # noqa: BLE001
                self.report(job, 'error', f'rollback failed: {rexc}', level='error', status='failed')
        finally:
            self.r.delete(LOCK_KEY)

    # ---- 占位:Task 8/9 实现 ----
    def _apply_docker(self, job: dict, backup: str) -> None:
        self.report(job, 'apply', 'docker apply (placeholder)')
        if self.dry_run:
            return
        raise NotImplementedError('docker apply implemented in Task 8')

    def _apply_native(self, job: dict, backup: str) -> None:
        self.report(job, 'apply', 'native apply (placeholder)')
        if self.dry_run:
            return
        raise NotImplementedError('native apply implemented in Task 9')

    def _rollback(self, job: dict, backup: str) -> None:
        self.report(job, 'rollback', f'rollback (dry_run={self.dry_run})')
        if self.dry_run:
            return
        # Docker/native 各自回滚在 Task 8/9 覆盖
        pass

    # ---- 循环 ----
    def run_once(self) -> bool:
        item = self.r.rpop(QUEUE_KEY)
        if not item:
            return False
        job = json.loads(item)
        self.handle(job)
        return True

    def run_forever(self, poll: float = 2.0) -> None:  # pragma: no cover
        while True:
            if not self.run_once():
                time.sleep(poll)


def _main() -> None:  # pragma: no cover
    import redis
    url = os.environ.get('REDIS_URL', 'redis://redis:6379/1')
    Agent(redis.Redis.from_url(url)).run_forever()


if __name__ == '__main__':  # pragma: no cover
    _main()
```

`deploy/updater/__init__.py` 为空文件。

- [ ] **Step 4: 运行测试,确认通过**

Run: `cd /Users/zhengshan/projects/atm-erp && python -m pytest deploy/updater/test_agent.py -v`
Expected: PASS(2 tests)

- [ ] **Step 5: 提交**

```bash
git add deploy/updater/agent.py deploy/updater/__init__.py deploy/updater/test_agent.py
git commit -m "feat(upgrade): 宿主升级代理核心循环 + 通用步骤(dry-run)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 代理 Docker 分支 + updater 容器 + compose 服务

**Files:**
- Modify: `deploy/updater/agent.py`(`_apply_docker` / `_rollback` 的 docker 部分)
- Create: `docker/updater/Dockerfile`
- Modify: `docker-compose.yml`(追加 `erp-updater` 服务)
- Test: `deploy/updater/test_agent_docker.py`

**Interfaces:**
- Consumes: Task 7 的 `Agent`。
- Produces: docker 分支执行:改 `.env` IMAGE_TAG → `docker compose pull` → `up -d`;回滚恢复旧 tag。

- [ ] **Step 1: 写测试(dry-run docker 计划 + tag 改写函数)**

```python
# deploy/updater/test_agent_docker.py
import fakeredis
from deploy.updater.agent import Agent, set_env_image_tag


def test_set_env_image_tag(tmp_path):
    env = tmp_path / '.env'
    env.write_text('IMAGE_TAG=0.2.0\nDB_PASSWORD=x\n')
    old = set_env_image_tag(str(env), '0.3.0')
    assert old == '0.2.0'
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
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd /Users/zhengshan/projects/atm-erp && python -m pytest deploy/updater/test_agent_docker.py -v`
Expected: FAIL(ImportError: set_env_image_tag)

- [ ] **Step 3: 实现 docker 分支**

在 `agent.py` 顶部加辅助函数:

```python
def set_env_image_tag(env_path: str, new_tag: str) -> str:
    """把 .env 里的 IMAGE_TAG 改成 new_tag,返回旧值(没有则空串)。"""
    old = ''
    lines = []
    found = False
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('IMAGE_TAG='):
                old = line.split('=', 1)[1].strip()
                lines.append(f'IMAGE_TAG={new_tag}\n')
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f'IMAGE_TAG={new_tag}\n')
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    return old
```

把 `Agent` 的 docker 方法替换为:

```python
    def _compose(self, *args: str) -> None:
        self._run(['docker', 'compose', *args], cwd=PROJECT_DIR)

    def _apply_docker(self, job: dict, backup: str) -> None:
        new_tag = job['manifest']['docker']['image_tag']
        env_path = os.path.join(PROJECT_DIR, '.env')
        self.report(job, 'apply', f'set IMAGE_TAG={new_tag}; docker compose pull && up -d')
        if self.dry_run:
            job['_old_tag'] = '0.0.0'
            return
        job['_old_tag'] = set_env_image_tag(env_path, new_tag)
        self._compose('pull')
        self._compose('up', '-d')

    def _rollback(self, job: dict, backup: str) -> None:
        self.report(job, 'rollback', f'rollback (dry_run={self.dry_run})')
        if self.dry_run:
            return
        if job['mode'] == 'docker':
            old = job.get('_old_tag') or job.get('from_version')
            set_env_image_tag(os.path.join(PROJECT_DIR, '.env'), old)
            self._compose('up', '-d')
        else:
            self._rollback_native(job, backup)
```

- [ ] **Step 4: 写 updater 容器 Dockerfile**

```dockerfile
# docker/updater/Dockerfile
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io postgresql-client curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir redis requests
COPY deploy/updater/ /opt/updater/deploy/updater/
ENV PYTHONPATH=/opt/updater
WORKDIR /opt/updater
CMD ["python", "-m", "deploy.updater.agent"]
```

- [ ] **Step 5: compose 追加 erp-updater 服务**

在 `docker-compose.yml` services 末尾追加:

```yaml
  erp-updater:
    build:
      context: .
      dockerfile: docker/updater/Dockerfile
    image: ${REGISTRY:-ghcr.io}/${IMAGE_OWNER:-hongheshan-svg}/atm-erp-updater:${IMAGE_TAG:-latest}
    container_name: erp-updater
    restart: unless-stopped
    environment:
      - REDIS_URL=redis://redis:6379/1
      - ERP_HEALTH_URL=http://nginx/api/v1/health/
      - ERP_PROJECT_DIR=/project
      - PGHOST=postgres
      - PGUSER=${DB_USER:-erp_user}
      - PGPASSWORD=${DB_PASSWORD:-erp_password}
      - PGDATABASE=${DB_NAME:-erp_db}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - .:/project
      - backend_logs:/var/backups/erp
    depends_on:
      - redis
    networks:
      - erp-network
```

> 注:`_run` 的 `pg_dump` 用 `PG*` 环境变量;`backup_db` 的 path 改为 `/var/backups/erp/...`(已与卷一致)。docker 分支在容器内调用宿主 `docker compose`,`cwd=/project`(挂载的项目目录),故 `ERP_PROJECT_DIR=/project`。

- [ ] **Step 6: 运行测试,确认通过**

Run: `cd /Users/zhengshan/projects/atm-erp && python -m pytest deploy/updater/test_agent_docker.py -v && docker compose config -q && echo COMPOSE_OK`
Expected: PASS(2 tests) + `COMPOSE_OK`

- [ ] **Step 7: 提交**

```bash
git add deploy/updater/agent.py docker/updater/Dockerfile docker-compose.yml deploy/updater/test_agent_docker.py
git commit -m "feat(upgrade): 代理 Docker 分支 + erp-updater 容器/compose 服务

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 代理原生分支 + systemd 单元

**Files:**
- Modify: `deploy/updater/agent.py`(`_apply_native`、`_rollback_native`)
- Create: `deploy/updater/erp-updater.service`
- Modify: `scripts/deploy-native-ubuntu.sh`(安装 updater 单元 + 写 `DEPLOY_MODE=native`/`APP_VERSION`)
- Test: `deploy/updater/test_agent_native.py`

**Interfaces:**
- Consumes: Task 7 的 `Agent`、Task 8 的 `_rollback`。
- Produces: native 分支:下载 tar(校验 sha256)→ 解到新发布目录 → migrate/collectstatic → `systemctl restart` → 回滚切回旧目录。

- [ ] **Step 1: 写测试(sha256 校验 + dry-run native 计划)**

```python
# deploy/updater/test_agent_native.py
import hashlib, fakeredis
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
    import json
    steps = json.loads(r.get('erp:upgrade:progress:n1') or '{"steps":[]}')['steps']
    assert any(s['stage'] == 'apply' for s in steps)
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd /Users/zhengshan/projects/atm-erp && python -m pytest deploy/updater/test_agent_native.py -v`
Expected: FAIL(ImportError: verify_sha256)

- [ ] **Step 3: 实现 native 分支**

`agent.py` 顶部加:

```python
import hashlib

def verify_sha256(path: str, expected: str) -> None:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    actual = h.hexdigest()
    if actual.lower() != expected.lower():
        raise ValueError(f'sha256 mismatch: {actual} != {expected}')
```

`Agent` 加:

```python
    RELEASES_DIR = os.environ.get('ERP_RELEASES_DIR', '/opt/erp/releases')
    CURRENT_LINK = os.environ.get('ERP_CURRENT_LINK', '/opt/erp/current')

    def _apply_native(self, job: dict, backup: str) -> None:
        nat = job['manifest']['native']
        target = job['target_version']
        self.report(job, 'apply', f"download {nat['tarball_url']} -> release {target}, migrate, restart")
        if self.dry_run:
            return
        import requests
        rel_dir = os.path.join(self.RELEASES_DIR, target)
        os.makedirs(rel_dir, exist_ok=True)
        tar_path = os.path.join(rel_dir, 'release.tar.gz')
        with requests.get(nat['tarball_url'], stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(tar_path, 'wb') as f:
                for chunk in resp.iter_content(1024 * 1024):
                    f.write(chunk)
        verify_sha256(tar_path, nat['sha256'])
        self._run(['tar', '-xzf', tar_path, '-C', rel_dir, '--strip-components=1'])
        job['_old_link'] = os.path.realpath(self.CURRENT_LINK) if os.path.islink(self.CURRENT_LINK) else ''
        # 迁移与静态(在新发布目录)
        py = os.path.join(rel_dir, 'venv/bin/python')
        py = py if os.path.exists(py) else 'python'
        self._run([py, 'manage.py', 'migrate', '--noinput'], cwd=os.path.join(rel_dir, 'backend'))
        self._run([py, 'manage.py', 'collectstatic', '--noinput'], cwd=os.path.join(rel_dir, 'backend'))
        # 切换 current 软链 + 重启
        tmp_link = self.CURRENT_LINK + '.new'
        if os.path.islink(tmp_link):
            os.remove(tmp_link)
        os.symlink(rel_dir, tmp_link)
        os.replace(tmp_link, self.CURRENT_LINK)
        self._run(['systemctl', 'restart', 'erp-backend', 'erp-celery', 'erp-celery-beat'])

    def _rollback_native(self, job: dict, backup: str) -> None:
        old = job.get('_old_link')
        if old and os.path.isdir(old):
            tmp = self.CURRENT_LINK + '.rb'
            if os.path.islink(tmp):
                os.remove(tmp)
            os.symlink(old, tmp)
            os.replace(tmp, self.CURRENT_LINK)
            self._run(['systemctl', 'restart', 'erp-backend', 'erp-celery', 'erp-celery-beat'])
```

- [ ] **Step 4: 写 systemd 单元**

```ini
# deploy/updater/erp-updater.service
[Unit]
Description=ATM-ERP Remote Upgrade Agent
After=network.target redis-server.service postgresql.service

[Service]
Type=simple
User=root
Environment=DEPLOY_MODE=native
Environment=REDIS_URL=redis://127.0.0.1:6379/1
Environment=ERP_HEALTH_URL=http://127.0.0.1/api/v1/health/
ExecStart=/usr/bin/python3 -m deploy.updater.agent
WorkingDirectory=/opt/erp/updater
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 5: 在 deploy-native 脚本注册(在文末服务注册区追加)**

`scripts/deploy-native-ubuntu.sh` 追加(贴合现有 systemd 注册风格):
```bash
# 安装升级代理
mkdir -p /opt/erp/updater/deploy/updater
cp -r "$APP_DIR/deploy/updater/." /opt/erp/updater/deploy/updater/
pip install redis requests >/dev/null 2>&1 || true
cp "$APP_DIR/deploy/updater/erp-updater.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now erp-updater
# 写入版本与模式(被 backend 读取)
echo "DEPLOY_MODE=native" >> "$APP_DIR/.env"
echo "APP_VERSION=$(git -C "$APP_DIR" describe --tags --abbrev=0 2>/dev/null || echo 0.0.0)" >> "$APP_DIR/.env"
```

- [ ] **Step 6: 运行测试,确认通过**

Run: `cd /Users/zhengshan/projects/atm-erp && python -m pytest deploy/updater/test_agent_native.py -v && bash -n scripts/deploy-native-ubuntu.sh && echo SH_OK`
Expected: PASS(2 tests) + `SH_OK`

- [ ] **Step 7: 提交**

```bash
git add deploy/updater/agent.py deploy/updater/erp-updater.service scripts/deploy-native-ubuntu.sh deploy/updater/test_agent_native.py
git commit -m "feat(upgrade): 代理原生分支 + erp-updater systemd 单元

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: 后端进度落库订阅(把代理进度写回 UpgradeJob + 转发 WS)

**Files:**
- Create: `backend/apps/core/management/commands/upgrade_progress_relay.py`
- Modify: `docker-compose.yml`(backend 容器额外不需要;relay 由 celery 或独立命令运行——本计划用独立命令,Docker 由 updater 之外的 backend sidecar 命令运行)
- Test: `backend/apps/core/tests/test_progress_relay.py`

**Interfaces:**
- Consumes: Redis 频道 `erp:upgrade:events`、`models.UpgradeJob`、channel layer 组 `upgrade_<job_id>`。
- Produces: `relay_event(event: dict)`(落库 job.status/steps + `group_send` 到 WS 组)。

- [ ] **Step 1: 写测试**

```python
# backend/apps/core/tests/test_progress_relay.py
from django.test import TestCase
from apps.core.models import UpgradeJob
from apps.core.management.commands.upgrade_progress_relay import relay_event


class RelayTest(TestCase):
    def test_relay_updates_job(self):
        job = UpgradeJob.objects.create(action='upgrade', mode='docker',
                                        from_version='0.2.0', target_version='0.3.0')
        relay_event({'job_id': str(job.id),
                     'state': {'status': 'success',
                               'steps': [{'stage': 'done', 'message': 'ok', 'level': 'info'}]}})
        job.refresh_from_db()
        self.assertEqual(job.status, 'success')
        self.assertEqual(len(job.steps), 1)
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && python manage.py test apps.core.tests.test_progress_relay -v 2`
Expected: FAIL(ImportError)

- [ ] **Step 3: 实现 relay 命令**

```python
# backend/apps/core/management/commands/upgrade_progress_relay.py
"""订阅代理进度频道,落库 UpgradeJob 并转发到 WebSocket 组。"""
import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand
from django_redis import get_redis_connection

from apps.core.models import UpgradeJob


def relay_event(event: dict) -> None:
    job_id = event.get('job_id')
    state = event.get('state') or {}
    job = UpgradeJob.objects.filter(id=job_id).first()
    if not job:
        return
    if state.get('status'):
        job.status = state['status']
    if state.get('steps') is not None:
        job.steps = state['steps']
    from django.utils import timezone
    if job.status in (UpgradeJob.STATUS_SUCCESS, UpgradeJob.STATUS_FAILED, UpgradeJob.STATUS_ROLLED_BACK):
        job.finished_at = timezone.now()
    job.save(update_fields=['status', 'steps', 'finished_at', 'updated_at'])
    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(
            f'upgrade_{job_id}', {'type': 'upgrade.progress', 'data': state})


class Command(BaseCommand):
    help = 'Relay upgrade agent progress to DB + WebSocket'

    def handle(self, *args, **opts):  # pragma: no cover
        conn = get_redis_connection('default')
        pubsub = conn.pubsub()
        pubsub.subscribe('erp:upgrade:events')
        self.stdout.write('upgrade_progress_relay listening...')
        for msg in pubsub.listen():
            if msg['type'] != 'message':
                continue
            try:
                relay_event(json.loads(msg['data']))
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f'relay error: {exc}')
```

- [ ] **Step 4: compose 让 backend 之外跑 relay(追加一个轻量服务复用 backend 镜像)**

`docker-compose.yml` 追加:
```yaml
  erp-upgrade-relay:
    image: ${REGISTRY:-ghcr.io}/${IMAGE_OWNER:-hongheshan-svg}/atm-erp-backend:${IMAGE_TAG:-latest}
    container_name: erp-upgrade-relay
    restart: unless-stopped
    command: python manage.py upgrade_progress_relay
    environment:
      - RUN_BOOTSTRAP=0
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME:-erp_db}
      - DB_USER=${DB_USER:-erp_user}
      - DB_PASSWORD=${DB_PASSWORD:-erp_password}
      - REDIS_URL=redis://redis:6379/1
      - SECRET_KEY=${SECRET_KEY:-django-insecure-change-this-in-production-123456}
    depends_on:
      - redis
      - postgres
    networks:
      - erp-network
```
> 原生模式下 relay 由一个 systemd 单元运行同一命令(可复用 erp-backend 的 venv);本计划不强制,Docker 覆盖主路径。

- [ ] **Step 5: 运行测试,确认通过**

Run: `cd backend && python manage.py test apps.core.tests.test_progress_relay -v 2 && cd .. && docker compose config -q && echo OK`
Expected: PASS(1 test) + `OK`

- [ ] **Step 6: 提交**

```bash
git add backend/apps/core/management/commands/upgrade_progress_relay.py docker-compose.yml backend/apps/core/tests/test_progress_relay.py
git commit -m "feat(upgrade): 进度落库 relay(代理->UpgradeJob+WS)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: 前端「系统升级」页 + API + 路由

**Files:**
- Modify: `frontend/src/api/system.ts`(追加升级 API)
- Create: `frontend/src/views/system/Upgrade.vue`
- Modify: `frontend/src/router/index.ts`(追加路由,`meta.permission='system:upgrade'`)
- Test: `frontend/src/views/system/__tests__/Upgrade.spec.ts`

**Interfaces:**
- Consumes: 后端端点(Task 5)。
- Produces: 页面;`system.ts` 新增 `getVersion/checkUpdate/performUpgrade/getUpgradeJob/listUpgradeJobs/rollback`。

- [ ] **Step 1: 在 `frontend/src/api/system.ts` 追加**

```typescript
import request from '@/utils/request'

export const upgradeApi = {
  getVersion: () => request.get('/system/version'),
  checkUpdate: (force = false) => request.get('/system/check-update', { params: { force: force ? 1 : 0 } }),
  performUpgrade: () => request.post('/system/upgrade'),
  getJob: (id: string) => request.get(`/system/upgrade/jobs/${id}`),
  listJobs: () => request.get('/system/upgrade/jobs'),
  rollback: () => request.post('/system/rollback'),
}
```
> 注:若 `request` 的 baseURL 已含 `/api/v1`,则路径用 `/system/...`(与现有 system.ts 一致);否则补前缀。先看文件首部其它调用。

- [ ] **Step 2: 写组件测试**

```typescript
// frontend/src/views/system/__tests__/Upgrade.spec.ts
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Upgrade from '../Upgrade.vue'

vi.mock('@/api/system', () => ({
  upgradeApi: {
    getVersion: vi.fn().mockResolvedValue({ data: { version: '0.2.0', deploy_mode: 'docker' } }),
    checkUpdate: vi.fn().mockResolvedValue({ data: { current_version: '0.2.0', latest_version: '0.3.0', has_update: true, release_notes_md: '## 0.3.0', deploy_mode: 'docker', warning: '' } }),
    performUpgrade: vi.fn(), getJob: vi.fn(), listJobs: vi.fn().mockResolvedValue({ data: [] }), rollback: vi.fn(),
  },
}))

describe('Upgrade.vue', () => {
  it('shows current version and detects update', async () => {
    const wrapper = mount(Upgrade, { global: { stubs: { 'el-card': false, 'el-button': false, 'el-table': true, 'el-table-column': true, 'el-tag': false } } })
    await flushPromises()
    expect(wrapper.text()).toContain('0.2.0')
    await wrapper.find('[data-test="check-btn"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('0.3.0')
  })
})
```

- [ ] **Step 3: 运行,确认失败**

Run: `cd frontend && npx vitest run src/views/system/__tests__/Upgrade.spec.ts`
Expected: FAIL(无法解析 ../Upgrade.vue)

- [ ] **Step 4: 实现 `frontend/src/views/system/Upgrade.vue`**

```vue
<template>
  <div class="upgrade-page">
    <el-card>
      <template #header>系统升级</template>
      <p>当前版本：<el-tag>{{ version }}</el-tag> 部署模式：<el-tag type="info">{{ deployMode }}</el-tag></p>
      <el-button data-test="check-btn" :loading="checking" @click="onCheck">检查更新</el-button>
      <div v-if="info">
        <p v-if="info.warning" class="warn">{{ info.warning }}</p>
        <template v-if="info.has_update">
          <el-tag type="success">发现新版本 {{ info.latest_version }}</el-tag>
          <pre class="notes">{{ info.release_notes_md }}</pre>
          <el-button type="primary" data-test="upgrade-btn" :loading="upgrading" @click="onUpgrade">
            立即升级（将重启服务，已自动备份数据库）
          </el-button>
        </template>
        <el-tag v-else type="info">已是最新版本</el-tag>
      </div>
    </el-card>

    <el-card v-if="job" style="margin-top:16px">
      <template #header>升级进度（{{ job.status }}）</template>
      <ul>
        <li v-for="(s, i) in job.steps" :key="i" :class="s.level">[{{ s.stage }}] {{ s.message }}</li>
      </ul>
    </el-card>

    <el-card style="margin-top:16px">
      <template #header>升级历史</template>
      <el-table :data="history">
        <el-table-column prop="target_version" label="目标版本" />
        <el-table-column prop="action" label="动作" />
        <el-table-column prop="status" label="状态" />
      </el-table>
      <el-button data-test="rollback-btn" @click="onRollback">回滚到上一个版本</el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { upgradeApi } from '@/api/system'

const version = ref('')
const deployMode = ref('')
const checking = ref(false)
const upgrading = ref(false)
const info = ref<any>(null)
const job = ref<any>(null)
const history = ref<any[]>([])
let pollTimer: any = null

async function loadVersion() {
  const { data } = await upgradeApi.getVersion()
  version.value = data.version
  deployMode.value = data.deploy_mode
}
async function loadHistory() {
  const { data } = await upgradeApi.listJobs()
  history.value = data
}
async function onCheck() {
  checking.value = true
  try {
    const { data } = await upgradeApi.checkUpdate(true)
    info.value = data
  } finally {
    checking.value = false
  }
}
async function pollJob(id: string) {
  const { data } = await upgradeApi.getJob(id)
  job.value = data
  if (['success', 'failed', 'rolled_back'].includes(data.status)) {
    clearInterval(pollTimer)
    loadVersion(); loadHistory()
    ElMessage[data.status === 'success' ? 'success' : 'warning'](`升级${data.status}`)
  }
}
async function onUpgrade() {
  await ElMessageBox.confirm('升级会重启服务并可能中断访问，确认继续？', '确认升级', { type: 'warning' })
  upgrading.value = true
  try {
    const { data } = await upgradeApi.performUpgrade()
    // 断线/重启期间用轮询;job 持久,后端恢复后继续
    pollTimer = setInterval(() => pollJob(data.job_id).catch(() => {}), 4000)
  } finally {
    upgrading.value = false
  }
}
async function onRollback() {
  await ElMessageBox.confirm('确认回滚到上一个版本？', '确认回滚', { type: 'warning' })
  const { data } = await upgradeApi.rollback()
  pollTimer = setInterval(() => pollJob(data.job_id).catch(() => {}), 4000)
}
onMounted(() => { loadVersion(); loadHistory() })
</script>

<style scoped>
.notes { background:#f5f5f5; padding:8px; white-space:pre-wrap; }
.warn { color:#e6a23c; }
li.error { color:#f56c6c; }
</style>
```

- [ ] **Step 5: 加路由**

`frontend/src/router/index.ts` 在 system 子路由区追加(与现有 system 路由同风格):

```javascript
{
  path: '/system/upgrade',
  name: 'SystemUpgrade',
  component: () => import('@/views/system/Upgrade.vue'),
  meta: { title: '系统升级', permission: 'system:upgrade' },
},
```

- [ ] **Step 6: 运行测试,确认通过**

Run: `cd frontend && npx vitest run src/views/system/__tests__/Upgrade.spec.ts`
Expected: PASS(1 test)

- [ ] **Step 7: lint + typecheck**

Run: `cd frontend && npm run lint -- src/views/system/Upgrade.vue src/api/system.ts && npx vue-tsc --noEmit`
Expected: 无 error。

- [ ] **Step 8: 提交**

```bash
git add frontend/src/api/system.ts frontend/src/views/system/Upgrade.vue frontend/src/router/index.ts frontend/src/views/system/__tests__/Upgrade.spec.ts
git commit -m "feat(upgrade): 前端系统升级页 + API + 路由

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Docker 端到端集成 + 文档

**Files:**
- Create: `docs/REMOTE_UPGRADE.md`
- Modify: `README.md` / `README.zh-CN.md`(加「系统升级」一节,指向公开仓库)
- Modify: `docker-compose.yml`(backend/updater 注入 `APP_VERSION`/`DEPLOY_MODE`)

**Interfaces:** 无新代码接口;端到端验证 + 文档。

- [ ] **Step 1: compose 注入版本/模式**

`docker-compose.yml` 的 `backend` 与 `erp-updater` 环境追加:
```yaml
      - APP_VERSION=${IMAGE_TAG:-latest}
      - DEPLOY_MODE=docker
```

- [ ] **Step 2: 准备一份假清单 + 本地端到端验证(用本机 local 镜像)**

```bash
cd /Users/zhengshan/projects/atm-erp
# 假清单(指向已存在的 :local 镜像,latest_version 高于当前)
cat > /tmp/manifest.json <<'EOF'
{ "latest_version": "9.9.9", "release_notes_md": "## test", "min_upgradable_from": "0.0.0",
  "docker": { "image_tag": "local" } }
EOF
python3 -m http.server 8899 --directory /tmp &  # 仅本机访问;白名单需临时放开或用 mock
```
> 注:SSRF 白名单不含 localhost,端到端真实拉取需把假清单放到允许的主机,或在本测试用 `ERP_UPDATE_MANIFEST_URL` + 临时在 `ALLOWED_HOSTS` 加 `127.0.0.1`(仅本地验证,勿提交)。本步目的:确认 check-update→perform→agent→relay→job=success 全链路。完成后回滚临时改动。

- [ ] **Step 3: 全量后端测试 + 前端测试**

Run:
```bash
cd backend && python manage.py test apps.core.tests -v 1
cd ../frontend && npm run test
```
Expected: 全绿。

- [ ] **Step 4: 写 `docs/REMOTE_UPGRADE.md`**

内容:架构图、清单格式、公开仓库 `atm-erp` 的发布流程(生成 image digest / native tar sha256 / 更新 manifest)、`system:upgrade` 权限、回滚说明、安全说明(docker.sock 风险与收敛)。(完整文档,无占位。)

- [ ] **Step 5: README 双语加「系统升级」小节**

在两个 README 的功能/运维区追加一段:管理员后台「系统升级」→ 检查更新 → 一键升级(自动备份+健康门+失败回滚),并注明升级源为公开仓库清单。

- [ ] **Step 6: 提交**

```bash
git add docs/REMOTE_UPGRADE.md README.md README.zh-CN.md docker-compose.yml
git commit -m "docs(upgrade): 远程升级文档 + README + compose 注入版本/模式

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage(spec 各节 → 任务):**
- §3 架构 / §5 代理通用步骤 → Task 7;Docker 分支 → Task 8;原生分支 → Task 9 ✓
- §4 组件文件结构 → 全任务覆盖(version/model/manifest/service/views/consumer/agent/前端) ✓
- §6 API → Task 5 ✓
- §7 清单格式 + 完整性(digest/sha256/SSRF) → Task 3(SSRF/解析)+ Task 8(docker tag)+ Task 9(sha256) ✓
- §8 UpgradeJob → Task 2 ✓
- §9 版本/模式来源 + health → Task 1 + Task 12(compose 注入) ✓
- §10 进度熬过重启 → Task 6(WS)+ Task 10(落库 relay)+ Task 11(前端断线轮询) ✓
- §11 前端页面 → Task 11 ✓
- §12 测试 → 各任务 TDD + Task 12 集成 ✓
- §13 安全 → Task 3(SSRF)+ Task 4(单飞锁)+ Task 5(权限)+ Task 7(备份/健康门/回滚)+ Task 12 文档 ✓

**Placeholder scan:** 无 TODO/TBD;代码块均完整(已修正 Task 8 一处误植字符)。文中数处「先 grep/sed 确认现有写法」是针对**接入点对齐**(权限树插入处、urls 前缀、routing 写法、request baseURL),非实现占位。

**Type consistency:** Redis 键(`erp:upgrade:queue`/`:lock`/`progress:<id>`/频道 `erp:upgrade:events`)、`UpgradeJob` 字段与 `status/action/mode` 常量、`Agent` 方法名(`_apply_docker/_apply_native/_rollback/_rollback_native/health_gate/report`)、API 路径、`upgradeApi` 方法名在各任务间一致。

**已知约束(非占位,执行期需对齐):** 升级链路里「容器内 updater 调用宿主 `docker compose`」要求 updater 容器内有 docker CLI(Dockerfile 已装 `docker.io`)且 `cwd=/project`(挂载项目目录,含 `.env` 与 compose 文件);`backup_db` 路径与卷 `/var/backups/erp` 一致。
