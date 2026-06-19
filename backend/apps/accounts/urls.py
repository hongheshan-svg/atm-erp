"""
URL configuration for accounts app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .attendance import AttendanceConfigViewSet, AttendanceRecordViewSet, LeaveRequestViewSet, OvertimeRequestViewSet
from .oauth.views import (
    OAuthBindingsView,
    OAuthBindView,
    OAuthCallbackView,
    OAuthLoginURLView,
    OAuthProvidersView,
)
from .views import CustomTokenObtainPairView, DepartmentViewSet, RoleViewSet, UserViewSet

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'users', UserViewSet, basename='user')

# 考勤管理
router.register(r'attendance-configs', AttendanceConfigViewSet, basename='attendance-config')
router.register(r'attendance-records', AttendanceRecordViewSet, basename='attendance-record')
router.register(r'leave-requests', LeaveRequestViewSet, basename='leave-request')
router.register(r'overtime-requests', OvertimeRequestViewSet, basename='overtime-request')

urlpatterns = [
    # JWT Authentication
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # 企业 IM 扫码登录(企业微信/钉钉/飞书)
    path('oauth/providers', OAuthProvidersView.as_view(), name='oauth-providers'),
    path('oauth/bindings', OAuthBindingsView.as_view(), name='oauth-bindings'),
    path('oauth/<str:platform>/login-url', OAuthLoginURLView.as_view(), name='oauth-login-url'),
    path('oauth/<str:platform>/callback', OAuthCallbackView.as_view(), name='oauth-callback'),
    path('oauth/<str:platform>/bind', OAuthBindView.as_view(), name='oauth-bind'),
    # Router URLs
    path('', include(router.urls)),
]
