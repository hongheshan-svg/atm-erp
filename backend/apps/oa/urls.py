"""
OA协同办公模块 URL 配置
"""
import json

from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from rest_framework.routers import DefaultRouter

from apps.accounts.attendance import (
    AttendanceConfigViewSet,
    AttendanceRecordViewSet,
    LeaveRequestViewSet,
    OvertimeRequestViewSet,
)
from apps.core.announcement import AnnouncementViewSet
from apps.core.schedule import MeetingRoomViewSet, MeetingViewSet, ScheduleViewSet

from .archive import (
    ArchiveBorrowViewSet,
    ArchiveCategoryViewSet,
    ArchiveDestructionViewSet,
    ArchiveTransferViewSet,
    ArchiveViewSet,
)
from .asset import AssetBorrowViewSet, AssetCategoryViewSet, AssetMaintenanceViewSet, AssetTransferViewSet, AssetViewSet
from .attendance_device import (
    AttendanceDeviceViewSet,
    DeviceAttendanceLogViewSet,
    DeviceSyncLogViewSet,
    DeviceUserMappingViewSet,
)
from .attendance_sync_service import ZKTECOWebhookHandler
from .electronic_signature import SignatureDocumentViewSet, SignatureLogViewSet, SignatureSealViewSet
from .im import IMConversationViewSet, IMMessageViewSet
from .vehicle import VehicleMaintenanceViewSet, VehicleRequestViewSet, VehicleViewSet
from .wechat_work import (
    WechatCheckinRecordViewSet,
    WechatSyncLogViewSet,
    WechatUserMappingViewSet,
    WechatWorkConfigViewSet,
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

# 考勤设备管理
router.register(r'attendance-devices', AttendanceDeviceViewSet, basename='oa-attendance-device')
router.register(r'device-user-mappings', DeviceUserMappingViewSet, basename='oa-device-user-mapping')
router.register(r'device-attendance-logs', DeviceAttendanceLogViewSet, basename='oa-device-attendance-log')
router.register(r'device-sync-logs', DeviceSyncLogViewSet, basename='oa-device-sync-log')

# 企业微信考勤同步
router.register(r'wechat-configs', WechatWorkConfigViewSet, basename='oa-wechat-config')
router.register(r'wechat-user-mappings', WechatUserMappingViewSet, basename='oa-wechat-user-mapping')
router.register(r'wechat-checkin-records', WechatCheckinRecordViewSet, basename='oa-wechat-checkin-record')
router.register(r'wechat-sync-logs', WechatSyncLogViewSet, basename='oa-wechat-sync-log')


# Webhook接收考勤机推送数据
@csrf_exempt
def device_webhook(request, device_sn):
    """
    接收ZKTECO考勤机推送的数据
    支持 iclock 协议和 JSON 格式
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        # 尝试解析JSON
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            # iclock 协议格式
            data = {}
            for key, value in request.POST.items():
                data[key] = value
            # 也检查 body 中的数据
            if request.body:
                body_str = request.body.decode('utf-8')
                for line in body_str.split('&'):
                    if '=' in line:
                        k, v = line.split('=', 1)
                        data[k] = v

        result = ZKTECOWebhookHandler.handle_push_data(device_sn, data)

        if result['success']:
            return JsonResponse({'OK': ''})  # iclock 协议要求返回 OK
        else:
            return JsonResponse({'error': result['message']}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def device_webhook_iclock(request):
    """
    iclock 协议兼容接口
    设备会以 GET 请求获取命令，POST 请求推送数据
    """
    device_sn = request.GET.get('SN', '') or request.POST.get('SN', '')

    if request.method == 'GET':
        # 设备请求命令
        return JsonResponse({'OK': ''})

    if request.method == 'POST':
        # 设备推送数据
        if device_sn:
            data = {}
            for key, value in request.POST.items():
                data[key] = value
            if request.body:
                body_str = request.body.decode('utf-8', errors='ignore')
                data['body'] = body_str

            result = ZKTECOWebhookHandler.handle_push_data(device_sn, data)
            return JsonResponse({'OK': ''})

    return JsonResponse({'error': 'Invalid request'}, status=400)


urlpatterns = [
    path('', include(router.urls)),
    # 考勤机推送接口
    path('webhook/attendance/<str:device_sn>/', device_webhook, name='attendance-device-webhook'),
    # iclock 协议兼容接口
    path('iclock/cdata', device_webhook_iclock, name='iclock-cdata'),
]
