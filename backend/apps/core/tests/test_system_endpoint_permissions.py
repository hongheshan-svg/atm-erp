from django.test import SimpleTestCase

from apps.core.permissions import IsSystemAdmin
from apps.core.views import NotificationChannelViewSet


class SystemEndpointPermissionTests(SimpleTestCase):
    def test_notification_channel_management_requires_system_admin(self):
        self.assertIn(IsSystemAdmin, NotificationChannelViewSet.permission_classes)
