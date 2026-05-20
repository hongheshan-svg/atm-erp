"""
WebSocket utility functions for sending real-time notifications
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class WebSocketNotifier:
    """Utility class for sending WebSocket notifications"""

    @staticmethod
    def send_notification_to_user(user_id, notification_data):
        """
        Send notification to a specific user via WebSocket

        Args:
            user_id: User ID to send notification to
            notification_data: Dictionary containing notification data
        """
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'user_{user_id}', {'type': 'notification_message', 'data': notification_data}
            )

    @staticmethod
    def send_notification_to_users(user_ids, notification_data):
        """
        Send notification to multiple users

        Args:
            user_ids: List of user IDs
            notification_data: Dictionary containing notification data
        """
        for user_id in user_ids:
            WebSocketNotifier.send_notification_to_user(user_id, notification_data)

    @staticmethod
    def send_system_alert(alert_data, user_ids=None):
        """
        Send system alert to users

        Args:
            alert_data: Dictionary containing alert data
            user_ids: Optional list of specific user IDs. If None, send to all connected users.
        """
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        if user_ids:
            for user_id in user_ids:
                async_to_sync(channel_layer.group_send)(f'user_{user_id}', {'type': 'system_alert', 'data': alert_data})
        else:
            # Broadcast to all (would need a global broadcast group)
            pass

    @staticmethod
    def update_dashboard(dashboard_data):
        """
        Send dashboard update to all connected dashboard clients

        Args:
            dashboard_data: Dictionary containing updated dashboard data
        """
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'dashboard_updates', {'type': 'dashboard_update', 'data': dashboard_data}
            )
