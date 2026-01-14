"""
OA协同办公模块 URL 配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .im import IMConversationViewSet, IMMessageViewSet
from .archive import (
    ArchiveCategoryViewSet, ArchiveViewSet, ArchiveBorrowViewSet,
    ArchiveTransferViewSet, ArchiveDestructionViewSet
)
from .electronic_signature import (
    SignatureSealViewSet, SignatureDocumentViewSet, SignatureLogViewSet
)
from .vehicle import VehicleViewSet, VehicleRequestViewSet, VehicleMaintenanceViewSet
from .asset import (
    AssetCategoryViewSet, AssetViewSet, AssetBorrowViewSet,
    AssetTransferViewSet, AssetMaintenanceViewSet
)
from apps.core.schedule import ScheduleViewSet, MeetingViewSet, MeetingRoomViewSet
from apps.core.announcement import AnnouncementViewSet
from apps.accounts.attendance import (
    AttendanceRecordViewSet, AttendanceConfigViewSet,
    LeaveRequestViewSet, OvertimeRequestViewSet
)

router = DefaultRouter()
router.register(r'conversations', IMConversationViewSet, basename='im-conversation')
router.register(r'messages', IMMessageViewSet, basename='im-message')

# 档案管理
router.register(r'archive-categories', ArchiveCategoryViewSet, basename='archive-category')
router.register(r'archives', ArchiveViewSet, basename='archive')
router.register(r'archive-borrows', ArchiveBorrowViewSet, basename='archive-borrow')
router.register(r'archive-transfers', ArchiveTransferViewSet, basename='archive-transfer')
router.register(r'archive-destructions', ArchiveDestructionViewSet, basename='archive-destruction')

# 电子签章
router.register(r'signature-seals', SignatureSealViewSet, basename='signature-seal')
router.register(r'signature-documents', SignatureDocumentViewSet, basename='signature-document')
router.register(r'signature-logs', SignatureLogViewSet, basename='signature-log')

# 日程会议(从core模块引入)
router.register(r'schedules', ScheduleViewSet, basename='oa-schedule')
router.register(r'meetings', MeetingViewSet, basename='oa-meeting')
router.register(r'meeting-rooms', MeetingRoomViewSet, basename='oa-meeting-room')
router.register(r'announcements', AnnouncementViewSet, basename='oa-announcement')

# 考勤管理
router.register(r'attendance-records', AttendanceRecordViewSet, basename='oa-attendance-record')
router.register(r'attendance-configs', AttendanceConfigViewSet, basename='oa-attendance-config')
router.register(r'leave-requests', LeaveRequestViewSet, basename='oa-leave-request')
router.register(r'overtime-requests', OvertimeRequestViewSet, basename='oa-overtime-request')

# 车辆管理
router.register(r'vehicles', VehicleViewSet, basename='oa-vehicle')
router.register(r'vehicle-requests', VehicleRequestViewSet, basename='oa-vehicle-request')
router.register(r'vehicle-maintenance', VehicleMaintenanceViewSet, basename='oa-vehicle-maintenance')

# 资产管理
router.register(r'asset-categories', AssetCategoryViewSet, basename='oa-asset-category')
router.register(r'assets', AssetViewSet, basename='oa-asset')
router.register(r'asset-borrows', AssetBorrowViewSet, basename='oa-asset-borrow')
router.register(r'asset-transfers', AssetTransferViewSet, basename='oa-asset-transfer')
router.register(r'asset-maintenance', AssetMaintenanceViewSet, basename='oa-asset-maintenance')

urlpatterns = [
    path('', include(router.urls)),
]
