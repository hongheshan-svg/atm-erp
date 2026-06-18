"""订阅代理进度频道,落库 UpgradeJob 并转发到 WebSocket 组。"""
import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand
from django_redis import get_redis_connection

from apps.core.models import UpgradeJob


def relay_event(event: dict) -> None:
    """处理单条代理进度事件: 更新 UpgradeJob 并转发到 WS 组。

    Args:
        event: 字典,必须含 job_id(str UUID)和 state(dict,含 status/steps)。
    """
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
    terminal = (UpgradeJob.STATUS_SUCCESS, UpgradeJob.STATUS_FAILED, UpgradeJob.STATUS_ROLLED_BACK)
    if job.status in terminal:
        job.finished_at = timezone.now()

    job.save(update_fields=['status', 'steps', 'finished_at', 'updated_at'])

    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(
            f'upgrade_{job_id}',
            {'type': 'upgrade.progress', 'data': state},
        )


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
