"""
WebSocket consumers for real-time notifications
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer, AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications
    """

    async def connect(self):
        """Handle WebSocket connection"""
        # Get user from scope (set by AuthMiddlewareStack)
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        # Create user-specific group
        self.group_name = f'user_{self.user.id}'

        # Join user group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

        # Send connection confirmation
        await self.send(
            text_data=json.dumps(
                {'type': 'connection', 'message': 'Connected to notification service', 'user_id': self.user.id}
            )
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                # Respond to ping with pong
                await self.send(text_data=json.dumps({'type': 'pong', 'timestamp': data.get('timestamp')}))
            elif message_type == 'mark_read':
                # Mark notification as read
                notification_id = data.get('notification_id')
                if notification_id:
                    await self.mark_notification_read(notification_id)
        except json.JSONDecodeError:
            pass

    async def notification_message(self, event):
        """
        Handle notification messages from channel layer
        This method name must match the 'type' in channel_layer.group_send
        """
        # Send notification to WebSocket
        await self.send(text_data=json.dumps({'type': 'notification', 'data': event['data']}))

    async def system_alert(self, event):
        """Handle system alert messages"""
        await self.send(text_data=json.dumps({'type': 'alert', 'data': event['data']}))

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read in database"""
        from django.utils import timezone

        from .models import SystemNotification

        try:
            notification = SystemNotification.objects.get(id=notification_id, user=self.user)
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            return True
        except SystemNotification.DoesNotExist:
            return False


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time dashboard updates
    """

    async def connect(self):
        """Handle connection"""
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        # Join dashboard broadcast group
        self.group_name = 'dashboard_updates'

        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

        # Send initial dashboard data
        initial_data = await self.get_dashboard_data()
        await self.send(text_data=json.dumps({'type': 'dashboard_data', 'data': initial_data}))

    async def disconnect(self, close_code):
        """Handle disconnection"""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming messages"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'refresh':
                # Send updated dashboard data
                dashboard_data = await self.get_dashboard_data()
                await self.send(text_data=json.dumps({'type': 'dashboard_data', 'data': dashboard_data}))
        except json.JSONDecodeError:
            pass

    async def dashboard_update(self, event):
        """Handle dashboard update broadcasts"""
        await self.send(text_data=json.dumps({'type': 'dashboard_update', 'data': event['data']}))

    @database_sync_to_async
    def get_dashboard_data(self):
        """Get current dashboard KPIs"""
        from apps.analytics.services import DashboardKPIService

        return DashboardKPIService.get_all_kpis()


class UpgradeProgressConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for streaming remote-upgrade progress.

    Clients connect to ws/system/upgrade/<job_id>/.
    The relay task calls channel_layer.group_send('upgrade_<job_id>', {'type': 'upgrade.progress', 'data': {...}})
    and this consumer forwards `data` directly to the WebSocket client.

    Access control: requires authentication AND the system:upgrade permission.
    """

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self._can_watch(user):
            await self.close(code=4403)
            return
        self.job_id = self.scope['url_route']['kwargs']['job_id']
        self.group = f'upgrade_{self.job_id}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def upgrade_progress(self, event):
        """Handle upgrade.progress events from the channel layer and forward to client."""
        await self.send_json(event['data'])

    @database_sync_to_async
    def _can_watch(self, user):
        """Return True if user holds the system:upgrade permission (or is superuser)."""
        if user.is_superuser:
            return True
        from apps.core.permission_service import get_user_permissions
        perms = get_user_permissions(user)
        return any(p == 'system:upgrade' or p.startswith('system:upgrade:') for p in perms)
