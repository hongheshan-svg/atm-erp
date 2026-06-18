import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from apps.core.consumers import UpgradeProgressConsumer

JOB_UUID = '12345678-1234-5678-1234-567812345678'


class UpgradeWsTest(TransactionTestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create(
            username='wsadmin',
            employee_id='WS1',
            is_superuser=True,
            is_staff=True,
            is_active=True,
        )

    def test_receives_group_message(self):
        async def run():
            comm = WebsocketCommunicator(
                UpgradeProgressConsumer.as_asgi(),
                f'/ws/system/upgrade/{JOB_UUID}/',
            )
            comm.scope['user'] = self.superuser
            comm.scope['url_route'] = {'kwargs': {'job_id': JOB_UUID}}
            connected, _ = await comm.connect()
            assert connected, 'Expected connection to be accepted for superuser'
            layer = get_channel_layer()
            await layer.group_send(
                f'upgrade_{JOB_UUID}',
                {'type': 'upgrade.progress', 'data': {'stage': 'pull'}},
            )
            msg = await comm.receive_json_from(timeout=3)
            assert msg['stage'] == 'pull'
            await comm.disconnect()

        async_to_sync(run)()

    def test_rejects_anonymous(self):
        async def run():
            comm = WebsocketCommunicator(
                UpgradeProgressConsumer.as_asgi(),
                f'/ws/system/upgrade/{JOB_UUID}/',
            )
            comm.scope['user'] = AnonymousUser()
            comm.scope['url_route'] = {'kwargs': {'job_id': JOB_UUID}}
            connected, _ = await comm.connect()
            assert not connected, 'Expected connection to be rejected for anonymous user'

        async_to_sync(run)()
