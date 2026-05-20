"""
实时通知服务
Real-time Notification Service using Django Channels
"""

import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket消费者 - 处理实时通知
    """

    async def connect(self):
        """建立WebSocket连接"""
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        # 用户专属通知组
        self.user_group = f'notifications_{self.user.id}'

        # 加入用户专属组
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        # 加入广播组
        await self.channel_layer.group_add('notifications_broadcast', self.channel_name)

        await self.accept()

        # 发送未读通知数量
        unread_count = await self.get_unread_count()
        await self.send_json({'type': 'connection_established', 'unread_count': unread_count})

        logger.info(f'WebSocket connected for user {self.user.id}')

    async def disconnect(self, close_code):
        """断开WebSocket连接"""
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

        await self.channel_layer.group_discard('notifications_broadcast', self.channel_name)

        logger.info(f'WebSocket disconnected: {close_code}')

    async def receive_json(self, content):
        """接收客户端消息"""
        message_type = content.get('type')

        if message_type == 'mark_read':
            notification_id = content.get('notification_id')
            if notification_id:
                await self.mark_notification_read(notification_id)
                unread_count = await self.get_unread_count()
                await self.send_json(
                    {'type': 'notification_read', 'notification_id': notification_id, 'unread_count': unread_count}
                )

        elif message_type == 'mark_all_read':
            await self.mark_all_read()
            await self.send_json({'type': 'all_read', 'unread_count': 0})

        elif message_type == 'get_unread':
            unread_count = await self.get_unread_count()
            notifications = await self.get_recent_notifications()
            await self.send_json(
                {'type': 'unread_notifications', 'unread_count': unread_count, 'notifications': notifications}
            )

    async def notification_message(self, event):
        """处理通知消息（从channel layer接收）"""
        await self.send_json({'type': 'new_notification', 'notification': event['notification']})

    async def broadcast_message(self, event):
        """处理广播消息"""
        await self.send_json({'type': 'broadcast', 'message': event['message']})

    @database_sync_to_async
    def get_unread_count(self):
        """获取未读通知数量"""
        from apps.core.models import Notification

        return Notification.objects.filter(user=self.user, is_read=False).count()

    @database_sync_to_async
    def get_recent_notifications(self, limit=10):
        """获取最近通知"""
        from apps.core.models import Notification

        notifications = Notification.objects.filter(user=self.user).order_by('-created_at')[:limit]

        return [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'notification_type': n.notification_type,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
                'related_model': n.related_model,
                'related_id': n.related_id,
            }
            for n in notifications
        ]

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """标记通知已读"""
        from apps.core.models import Notification

        Notification.objects.filter(id=notification_id, user=self.user).update(is_read=True, read_at=timezone.now())

    @database_sync_to_async
    def mark_all_read(self):
        """标记所有通知已读"""
        from apps.core.models import Notification

        Notification.objects.filter(user=self.user, is_read=False).update(is_read=True, read_at=timezone.now())


async def send_notification_to_user(user_id, notification_data):
    """
    发送通知给指定用户
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    await channel_layer.group_send(
        f'notifications_{user_id}', {'type': 'notification_message', 'notification': notification_data}
    )


async def send_broadcast(message):
    """
    发送广播消息给所有在线用户
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    await channel_layer.group_send('notifications_broadcast', {'type': 'broadcast_message', 'message': message})


def send_notification_sync(user_id, notification_data):
    """
    同步发送通知（在普通Django视图中使用）
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f'notifications_{user_id}', {'type': 'notification_message', 'notification': notification_data}
    )
