from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .search_views import GlobalSearchViewSet

router = DefaultRouter()
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-log')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'attachments', views.AttachmentViewSet, basename='attachment')
router.register(r'search', GlobalSearchViewSet, basename='search')
router.register(r'notification-channels', views.NotificationChannelViewSet, basename='notification-channel')

urlpatterns = [
    path('', include(router.urls)),
]

