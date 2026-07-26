from django.test import SimpleTestCase

from apps.analytics.views import AnalyticsViewSet
from apps.core.permission_mixin import PermissionMixin


class AnalyticsPermissionArchitectureTests(SimpleTestCase):
    def test_analytics_endpoints_use_unified_permission_mixin(self):
        self.assertTrue(issubclass(AnalyticsViewSet, PermissionMixin))
        self.assertEqual(AnalyticsViewSet.permission_module, 'reports')
        self.assertEqual(AnalyticsViewSet.permission_resource, 'analytics')
