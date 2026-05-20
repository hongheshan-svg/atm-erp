"""
URL configuration for accounts app.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .attendance import AttendanceConfigViewSet, AttendanceRecordViewSet, LeaveRequestViewSet, OvertimeRequestViewSet
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

    # Router URLs
    path('', include(router.urls)),
]

