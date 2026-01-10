"""
OA协同办公模块 URL 配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .im import IMConversationViewSet, IMMessageViewSet

router = DefaultRouter()
router.register(r'conversations', IMConversationViewSet, basename='im-conversation')
router.register(r'messages', IMMessageViewSet, basename='im-message')

urlpatterns = [
    path('', include(router.urls)),
]
