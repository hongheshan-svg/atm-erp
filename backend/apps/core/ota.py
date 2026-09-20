"""Admin-only, durable OTA workflow for container and legacy host deployments."""

import hashlib
import hmac
import json
import re
import urllib.error
import urllib.request

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .actions import perform
from .api import Conflict
from .models import AuditLog, Company, UpgradeJob
from .permissions import ADMIN, PermissionMixin, has_role, require_role
from .version import VERSION

REPO = 'hongheshan-svg/atm-erp'
ACTIVE = ('queued', 'downloading', 'ready', 'restarting', 'backing_up', 'installing', 'verifying')
STEPS = ('downloading', 'backing_up', 'installing', 'verifying', 'succeeded')
CONTAINER_STEPS = ('downloading', 'ready', 'restarting', 'backing_up', 'installing', 'verifying', 'succeeded')
RELEASE_CACHE = 'ota.release.v1'


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValidationError('仅支持正式语义版本号。')
    return tuple(map(int, value.lstrip('v').split('.')))


def release_info():
    request = urllib.request.Request(
        f'https://api.github.com/repos/{REPO}/releases/latest',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'Lean-ERP-version-check'},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('返回内容过大')
        data = json.loads(raw)
        tag = data['tag_name']
        version(tag)
        if data.get('draft') or data.get('prerelease'):
            raise ValueError('不是正式发布版本')
        assets = []
        for asset in data.get('assets', []):
            name = asset.get('name', '')
            url = asset.get('browser_download_url', '')
            digest = asset.get('digest') or ''
            size = asset.get('size', 0)
            if (
                url == f'https://github.com/{REPO}/releases/download/{tag}/{name}'
                and re.fullmatch(r'sha256:[a-f0-9]{64}', digest)
                and isinstance(size, int)
                and 0 < size <= 500_000_000
            ):
                assets.append({'name': name, 'url': url, 'sha256': digest[7:], 'size': size})
        return {
            'version': tag,
            'name': str(data.get('name') or tag)[:200],
            'notes': str(data.get('body') or '')[:30000],
            'published_at': str(data.get('published_at') or '')[:40],
            'url': f'https://github.com/{REPO}/releases/tag/{tag}',
            'assets': assets,
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValidationError('无法读取发布信息，请稍后重试或检查服务器网络。') from exc


def job_data(job):
    if not job:
        return None
    return {
        'id': job.pk,
        'target': job.target,
        'status': job.status,
        'need_restart': job.status == 'ready',
        'execution': job.asset.get('_execution', 'host'),
        'detail': job.detail,
        'backup': job.backup,
        'created_at': job.created_at.isoformat(),
        'updated_at': job.updated_at.isoformat(),
    }


def runner_state():
    state = cache.get('ota.runner')
    return state if (state and state['seen'] > timezone.now().timestamp() - 45
                     and state.get('execution', 'host') == settings.OTA_MODE) else None


class UpgradeView(PermissionMixin, APIView):
    read_roles = write_roles = ADMIN

    def get(self, request):
        result = {
            'current': VERSION,
            'runner': runner_state(),
            'configured': len(settings.OTA_AGENT_TOKEN) >= 32,
            'execution': settings.OTA_MODE,
            'job': job_data(UpgradeJob.objects.order_by('-id').first()),
        }
        if request.query_params.get('check') == '1':
            saved = cache.get(RELEASE_CACHE)
            now = timezone.now().timestamp()
            try:
                cached = bool(saved and now - saved['checked_at'] < 1200)
                if not cached or request.query_params.get('force') == '1':
                    saved = {'release': release_info(), 'checked_at': now}
                    cache.set(RELEASE_CACHE, saved, 86400)
                    cached = False
                result.update(**saved, cached=cached, available=version(saved['release']['version']) > version(VERSION))
            except ValidationError:
                if saved:
                    result.update(**saved, cached=True)
                result.update(check_error='暂时无法检查新版本，请检查服务器网络后重试。', available=False)
        return Response(result)

    def post(self, request):
        payload = request.data
        if not isinstance(payload, dict) or set(payload) != {'target', 'confirmed'} or payload['confirmed'] is not True:
            raise ValidationError('请确认升级期间暂停业务操作及升级前自动备份。')
        version(payload['target'])

        def execute(actor):
            Company.objects.select_for_update().get(pk=1)
            if UpgradeJob.objects.filter(status__in=ACTIVE).exists():
                raise Conflict('已有升级任务，请等待当前任务结束。')
            runner = runner_state()
            if not runner or len(settings.OTA_AGENT_TOKEN) < 32:
                raise Conflict('升级执行器未连接，请检查部署服务日志。')
            release = release_info()
            if release['version'] != payload['target'] or version(payload['target']) <= version(VERSION):
                raise Conflict('版本已变化或不是新版本，请重新检查。')
            name = f'atm-erp-{payload["target"]}-{runner["platform"]}-{runner["mode"]}.zip'
            asset = next((asset for asset in release['assets'] if asset['name'] == name), None)
            if not asset:
                raise Conflict('该版本尚未发布匹配部署方式且有 SHA256 校验的升级包。')
            job = UpgradeJob.objects.create(
                target=payload['target'],
                mode=runner['mode'],
                platform=runner['platform'],
                asset={**asset, '_runner_id': runner['id'], '_execution': runner.get('execution', 'host'),
                       '_source_version': VERSION},
                created_by=actor,
                updated_by=actor,
                detail='等待升级服务下载并准备新版本',
            )
            AuditLog.objects.create(
                actor=actor,
                operation='system.upgrade.request',
                resource=f'upgrade:{job.pk}',
                detail={'target': job.target},
            )
            return job_data(job)

        return Response(
            perform(
                actor=request.user,
                key=request.headers.get('Idempotency-Key'),
                operation='system.upgrade',
                payload=payload,
                authorize=lambda actor: require_role(actor, ADMIN),
                execute=execute,
            )
        )


class RestartView(PermissionMixin, APIView):
    read_roles = write_roles = ADMIN

    def post(self, request):
        payload = request.data
        if (not isinstance(payload, dict) or set(payload) != {'id', 'confirmed'}
                or type(payload['id']) is not int or payload['confirmed'] is not True):
            raise ValidationError('请确认暂停业务操作，备份后重启升级。')

        def execute(actor):
            Company.objects.select_for_update().get(pk=1)
            job = UpgradeJob.objects.select_for_update().filter(pk=payload['id']).first()
            runner = runner_state()
            if (not job or job.status != 'ready' or job.asset.get('_execution') != 'container'
                    or settings.OTA_MODE != 'container'):
                raise Conflict('没有可重启生效的更新，请刷新升级状态。')
            if not runner or runner['id'] != job.asset.get('_runner_id'):
                raise Conflict('升级服务未连接，请等待连接恢复后重试。')
            if job.asset.get('_source_version') != VERSION or version(job.target) <= version(VERSION):
                raise Conflict('运行版本已变化，不能应用之前准备的更新。')
            job.status, job.detail = 'restarting', '已确认重启，等待备份并切换新版本'
            job.updated_by = actor
            job.save()
            AuditLog.objects.create(actor=actor, operation='system.upgrade.restart',
                                    resource=f'upgrade:{job.pk}', detail={'target': job.target})
            return job_data(job)

        return Response(perform(actor=request.user, key=request.headers.get('Idempotency-Key'),
                                operation='system.upgrade.restart', payload=payload,
                                authorize=lambda actor: require_role(actor, ADMIN), execute=execute))


class AgentView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        token = request.headers.get('X-OTA-Token', '')
        if len(settings.OTA_AGENT_TOKEN) < 32 or not hmac.compare_digest(
            token.encode(), settings.OTA_AGENT_TOKEN.encode()
        ):
            raise PermissionDenied('执行器认证失败。')
        data = request.data
        if not isinstance(data, dict):
            raise ValidationError('无效执行器请求。')
        if data.get('action') == 'poll':
            mode, platform = data.get('mode'), data.get('platform')
            execution = data.get('execution', 'host')
            if execution != settings.OTA_MODE or execution not in ('host', 'container'):
                raise Conflict('升级执行方式不匹配，请停止旧执行器并核对部署配置。')
            if execution == 'container' and (mode, platform) != ('native', 'linux'):
                raise ValidationError('容器内升级仅使用 Linux 程序包。')
            runner_id = data.get('runner_id', '')
            if not isinstance(runner_id, str) or not re.fullmatch(r'[a-f0-9]{32}', runner_id):
                raise ValidationError('执行器标识无效。')
            if mode not in ('native', 'docker') or platform not in ('macos', 'linux', 'windows'):
                raise ValidationError('不支持的部署方式。')
            previous = runner_state()
            if previous and previous['id'] != runner_id:
                raise Conflict('已有其他执行器连接，请停止原执行器后重试。')
            cache.set(
                'ota.runner',
                {'id': runner_id, 'mode': mode, 'platform': platform, 'execution': execution,
                 'seen': timezone.now().timestamp()},
                60,
            )
            with transaction.atomic():
                Company.objects.select_for_update().get(pk=1)
                active = UpgradeJob.objects.filter(status__in=ACTIVE[1:]).order_by('id').first()
                if active:
                    if active.asset.get('_runner_id') != runner_id:
                        return Response({'job': None})
                    claim = hmac.new(
                        settings.OTA_AGENT_TOKEN.encode(), f'{active.pk}:{runner_id}'.encode(), hashlib.sha256
                    ).hexdigest()
                    return Response(
                        {'job': {**job_data(active), 'claim': claim, 'asset': active.asset, 'recovered': True}}
                    )
                job = UpgradeJob.objects.filter(status='queued').order_by('id').first()
                if not job:
                    return Response({'job': None})
                if job.mode != mode or job.platform != platform or job.asset.get('_runner_id') != runner_id:
                    raise Conflict('执行器与任务部署方式不一致。')
                if not job.created_by or not job.created_by.is_active or not has_role(job.created_by, ADMIN):
                    job.status, job.detail = 'failed', '发起人已失去管理员权限，任务未执行'
                    job.save()
                    return Response({'job': None})
                claim = hmac.new(
                    settings.OTA_AGENT_TOKEN.encode(), f'{job.pk}:{runner_id}'.encode(), hashlib.sha256
                ).hexdigest()
                job.claim = hashlib.sha256(claim.encode()).hexdigest()
                job.status, job.detail = 'downloading', '校验并下载升级包'
                job.save()
                return Response({'job': {**job_data(job), 'claim': claim, 'asset': job.asset}})
        if data.get('action') != 'report':
            raise ValidationError('未知执行器动作。')
        if type(data.get('id')) is not int or data['id'] <= 0:
            raise ValidationError('任务编号无效。')
        with transaction.atomic():
            job = UpgradeJob.objects.select_for_update().filter(pk=data.get('id')).first()
            claim = data.get('claim')
            if (
                not job
                or not isinstance(claim, str)
                or not job.claim
                or not hmac.compare_digest(job.claim, hashlib.sha256(claim.encode()).hexdigest())
            ):
                raise PermissionDenied('任务凭据无效。')
            status = data.get('status')
            if job.status in ('succeeded', 'failed'):
                if status != job.status:
                    raise Conflict('已结束的升级任务不可覆盖。')
                return Response(job_data(job))
            steps = CONTAINER_STEPS if job.asset.get('_execution') == 'container' else STEPS
            if status not in (*steps, 'failed'):
                raise ValidationError('升级状态无效。')
            if status == 'restarting' and job.status != 'restarting':
                raise Conflict('必须由管理员确认重启，执行器不能代替确认。')
            if status == 'ready' and job.status == 'restarting' and steps == CONTAINER_STEPS:
                # A lost ready-report response may be retried after the admin confirmed restart.
                # Acknowledge it without moving the durable state backwards.
                return Response(job_data(job))
            if status != 'failed' and (
                steps.index(status) < steps.index(job.status) or steps.index(status) > steps.index(job.status) + 1
            ):
                raise Conflict('升级步骤不可跳过或回退。')
            previous_status = job.status
            # A long build reports progress instead of polling for another job.
            # Refresh presence only after the job claim has been authenticated.
            cache.set(
                'ota.runner',
                {
                    'id': job.asset['_runner_id'],
                    'mode': job.mode,
                    'platform': job.platform,
                    'execution': job.asset.get('_execution', 'host'),
                    'seen': timezone.now().timestamp(),
                },
                60,
            )
            job.status = status
            job.detail = str(data.get('detail', ''))[:500]
            job.backup = str(data.get('backup', job.backup))[:500]
            job.save()
            if previous_status != status:
                AuditLog.objects.create(
                    actor=job.created_by,
                    operation='system.upgrade.progress',
                    resource=f'upgrade:{job.pk}',
                    detail={'status': status, 'target': job.target},
                )
            return Response(job_data(job))
