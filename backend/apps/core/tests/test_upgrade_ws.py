from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

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
