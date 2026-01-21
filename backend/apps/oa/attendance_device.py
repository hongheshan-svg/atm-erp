"""
ZKTECO 考勤机集成模块
支持 WX3960WIFI 等型号的智能云指纹考勤机
"""
import logging
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin

logger = logging.getLogger(__name__)


# ============================================
# 模型定义
# ============================================

class AttendanceDevice(BaseModel):
    """
    考勤设备管理
    支持 ZKTECO WX3960WIFI 等型号
    """
    DEVICE_TYPE_CHOICES = [
        ('ZKTECO_CLOUD', 'ZKTECO智能云考勤机'),
        ('ZKTECO_LOCAL', 'ZKTECO本地考勤机'),
        ('FACE_RECOGNITION', '人脸识别考勤机'),
        ('OTHER', '其他'),
    ]
    
    CONNECTION_TYPE_CHOICES = [
        ('CLOUD_PUSH', '云端推送'),
        ('CLOUD_PULL', '云端拉取'),
        ('TCP_IP', 'TCP/IP直连'),
        ('HTTP_API', 'HTTP API'),
    ]
    
    STATUS_CHOICES = [
        ('ONLINE', '在线'),
        ('OFFLINE', '离线'),
        ('ERROR', '异常'),
        ('UNKNOWN', '未知'),
    ]
    
    # 基本信息
    name = models.CharField(max_length=100, verbose_name='设备名称')
    device_sn = models.CharField(max_length=100, unique=True, verbose_name='设备序列号')
    device_type = models.CharField(
        max_length=30, 
        choices=DEVICE_TYPE_CHOICES, 
        default='ZKTECO_CLOUD',
        verbose_name='设备类型'
    )
    model = models.CharField(max_length=50, blank=True, default='WX3960WIFI', verbose_name='设备型号')
    
    # 连接配置
    connection_type = models.CharField(
        max_length=20,
        choices=CONNECTION_TYPE_CHOICES,
        default='CLOUD_PUSH',
        verbose_name='连接方式'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    port = models.PositiveIntegerField(default=4370, verbose_name='端口号')
    
    # 云服务配置
    cloud_server = models.URLField(blank=True, verbose_name='云服务地址')
    cloud_key = models.CharField(max_length=200, blank=True, verbose_name='云服务密钥')
    api_token = models.CharField(max_length=500, blank=True, verbose_name='API Token')
    
    # 设备认证
    device_password = models.CharField(max_length=100, blank=True, verbose_name='设备通讯密码')
    
    # 位置信息
    location = models.CharField(max_length=200, blank=True, verbose_name='安装位置')
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_devices',
        verbose_name='所属部门'
    )
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='UNKNOWN',
        verbose_name='设备状态'
    )
    last_heartbeat = models.DateTimeField(null=True, blank=True, verbose_name='最后心跳时间')
    last_sync_time = models.DateTimeField(null=True, blank=True, verbose_name='最后同步时间')
    
    # 同步配置
    sync_enabled = models.BooleanField(default=True, verbose_name='启用自动同步')
    sync_interval = models.PositiveIntegerField(default=300, verbose_name='同步间隔(秒)')
    
    # 其他配置
    timezone_offset = models.IntegerField(default=8, verbose_name='时区偏移(小时)')
    firmware_version = models.CharField(max_length=50, blank=True, verbose_name='固件版本')
    config = models.JSONField(default=dict, blank=True, verbose_name='扩展配置')
    
    class Meta:
        db_table = 'oa_attendance_device'
        verbose_name = '考勤设备'
        verbose_name_plural = verbose_name
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.device_sn})"
    
    def update_status(self, new_status, heartbeat=True):
        """更新设备状态"""
        self.status = new_status
        if heartbeat:
            self.last_heartbeat = timezone.now()
        self.save(update_fields=['status', 'last_heartbeat', 'updated_at'])


class DeviceUserMapping(BaseModel):
    """
    设备用户与系统员工映射
    将考勤机中的用户ID映射到系统中的员工
    """
    device = models.ForeignKey(
        AttendanceDevice,
        on_delete=models.CASCADE,
        related_name='user_mappings',
        verbose_name='考勤设备'
    )
    device_user_id = models.CharField(max_length=50, verbose_name='设备用户ID')
    device_user_name = models.CharField(max_length=100, blank=True, verbose_name='设备用户名称')
    
    employee = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='device_mappings',
        verbose_name='关联员工'
    )
    
    # 同步状态
    is_synced = models.BooleanField(default=False, verbose_name='是否已同步到设备')
    last_synced_at = models.DateTimeField(null=True, blank=True, verbose_name='最后同步时间')
    
    # 指纹/卡信息
    fingerprint_count = models.PositiveIntegerField(default=0, verbose_name='指纹数量')
    card_number = models.CharField(max_length=50, blank=True, verbose_name='卡号')
    
    class Meta:
        db_table = 'oa_device_user_mapping'
        verbose_name = '设备用户映射'
        verbose_name_plural = verbose_name
        unique_together = ['device', 'device_user_id']
        ordering = ['device', 'device_user_id']
    
    def __str__(self):
        return f"{self.device.name} - {self.device_user_id} -> {self.employee.get_full_name()}"


class DeviceAttendanceLog(BaseModel):
    """
    设备原始打卡记录
    从考勤机同步的原始打卡数据
    """
    PUNCH_TYPE_CHOICES = [
        ('IN', '签到'),
        ('OUT', '签退'),
        ('BREAK_OUT', '外出'),
        ('BREAK_IN', '返回'),
        ('OT_IN', '加班签到'),
        ('OT_OUT', '加班签退'),
        ('UNKNOWN', '未知'),
    ]
    
    VERIFY_TYPE_CHOICES = [
        ('FINGERPRINT', '指纹'),
        ('FACE', '人脸'),
        ('CARD', '刷卡'),
        ('PASSWORD', '密码'),
        ('WECHAT', '企业微信'),
        ('APP', 'APP打卡'),
        ('OTHER', '其他'),
    ]
    
    # 来源设备
    device = models.ForeignKey(
        AttendanceDevice,
        on_delete=models.CASCADE,
        related_name='attendance_logs',
        verbose_name='考勤设备'
    )
    
    # 设备端数据
    device_user_id = models.CharField(max_length=50, verbose_name='设备用户ID')
    punch_time = models.DateTimeField(verbose_name='打卡时间')
    punch_type = models.CharField(
        max_length=20,
        choices=PUNCH_TYPE_CHOICES,
        default='UNKNOWN',
        verbose_name='打卡类型'
    )
    verify_type = models.CharField(
        max_length=20,
        choices=VERIFY_TYPE_CHOICES,
        default='FINGERPRINT',
        verbose_name='验证方式'
    )
    
    # 关联员工(通过映射)
    employee = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_attendance_logs',
        verbose_name='关联员工'
    )
    
    # 同步标识
    device_log_id = models.CharField(max_length=100, blank=True, verbose_name='设备记录ID')
    sync_batch = models.CharField(max_length=50, blank=True, verbose_name='同步批次')
    
    # 处理状态
    is_processed = models.BooleanField(default=False, verbose_name='是否已处理')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    attendance_record = models.ForeignKey(
        'accounts.AttendanceRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_logs',
        verbose_name='关联考勤记录'
    )
    
    # 原始数据
    raw_data = models.JSONField(default=dict, blank=True, verbose_name='原始数据')
    
    class Meta:
        db_table = 'oa_device_attendance_log'
        verbose_name = '设备打卡记录'
        verbose_name_plural = verbose_name
        ordering = ['-punch_time']
        indexes = [
            models.Index(fields=['device', 'punch_time']),
            models.Index(fields=['employee', 'punch_time']),
            models.Index(fields=['is_processed']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.device_user_id} @ {self.punch_time}"
    
    def get_unique_key(self):
        """生成唯一标识，用于去重"""
        key_str = f"{self.device_id}_{self.device_user_id}_{self.punch_time.isoformat()}"
        return hashlib.md5(key_str.encode()).hexdigest()


class DeviceSyncLog(BaseModel):
    """
    设备同步日志
    记录每次数据同步的详情
    """
    SYNC_TYPE_CHOICES = [
        ('PULL', '拉取'),
        ('PUSH', '推送'),
        ('MANUAL', '手动'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', '进行中'),
        ('SUCCESS', '成功'),
        ('PARTIAL', '部分成功'),
        ('FAILED', '失败'),
    ]
    
    device = models.ForeignKey(
        AttendanceDevice,
        on_delete=models.CASCADE,
        related_name='sync_logs',
        verbose_name='考勤设备'
    )
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPE_CHOICES, verbose_name='同步类型')
    sync_batch = models.CharField(max_length=50, verbose_name='同步批次')
    
    start_time = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    
    # 统计
    total_records = models.PositiveIntegerField(default=0, verbose_name='总记录数')
    new_records = models.PositiveIntegerField(default=0, verbose_name='新增记录数')
    duplicate_records = models.PositiveIntegerField(default=0, verbose_name='重复记录数')
    error_records = models.PositiveIntegerField(default=0, verbose_name='错误记录数')
    
    # 时间范围
    data_from = models.DateTimeField(null=True, blank=True, verbose_name='数据起始时间')
    data_to = models.DateTimeField(null=True, blank=True, verbose_name='数据截止时间')
    
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    details = models.JSONField(default=dict, blank=True, verbose_name='详细信息')
    
    class Meta:
        db_table = 'oa_device_sync_log'
        verbose_name = '设备同步日志'
        verbose_name_plural = verbose_name
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.device.name} - {self.sync_batch} ({self.status})"


# ============================================
# 序列化器
# ============================================

class AttendanceDeviceSerializer(serializers.ModelSerializer):
    """考勤设备序列化器"""
    device_type_display = serializers.CharField(source='get_device_type_display', read_only=True)
    connection_type_display = serializers.CharField(source='get_connection_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    user_count = serializers.SerializerMethodField()
    today_records = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceDevice
        fields = [
            'id', 'name', 'device_sn', 'device_type', 'device_type_display',
            'model', 'connection_type', 'connection_type_display',
            'ip_address', 'port', 'cloud_server', 'cloud_key', 'api_token',
            'location', 'department', 'department_name',
            'status', 'status_display', 'last_heartbeat', 'last_sync_time',
            'sync_enabled', 'sync_interval', 'timezone_offset', 'firmware_version',
            'user_count', 'today_records',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'last_heartbeat', 'last_sync_time', 'created_at', 'updated_at']
        extra_kwargs = {
            'device_password': {'write_only': True},
            'cloud_key': {'write_only': True},
            'api_token': {'write_only': True},
        }
    
    def get_user_count(self, obj):
        return obj.user_mappings.filter(is_deleted=False).count()
    
    def get_today_records(self, obj):
        today = timezone.now().date()
        return obj.attendance_logs.filter(
            punch_time__date=today,
            is_deleted=False
        ).count()


class DeviceUserMappingSerializer(serializers.ModelSerializer):
    """设备用户映射序列化器"""
    device_name = serializers.CharField(source='device.name', read_only=True)
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_id', read_only=True)
    
    class Meta:
        model = DeviceUserMapping
        fields = [
            'id', 'device', 'device_name', 'device_user_id', 'device_user_name',
            'employee', 'employee_name', 'employee_code',
            'is_synced', 'last_synced_at', 'fingerprint_count', 'card_number',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['is_synced', 'last_synced_at', 'created_at', 'updated_at']


class DeviceAttendanceLogSerializer(serializers.ModelSerializer):
    """设备打卡记录序列化器"""
    device_name = serializers.CharField(source='device.name', read_only=True)
    punch_type_display = serializers.CharField(source='get_punch_type_display', read_only=True)
    verify_type_display = serializers.CharField(source='get_verify_type_display', read_only=True)
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    
    class Meta:
        model = DeviceAttendanceLog
        fields = [
            'id', 'device', 'device_name', 'device_user_id',
            'punch_time', 'punch_type', 'punch_type_display',
            'verify_type', 'verify_type_display',
            'employee', 'employee_name',
            'is_processed', 'processed_at', 'attendance_record',
            'created_at'
        ]
        read_only_fields = ['created_at']


class DeviceSyncLogSerializer(serializers.ModelSerializer):
    """设备同步日志序列化器"""
    device_name = serializers.CharField(source='device.name', read_only=True)
    sync_type_display = serializers.CharField(source='get_sync_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = DeviceSyncLog
        fields = [
            'id', 'device', 'device_name', 'sync_type', 'sync_type_display',
            'sync_batch', 'start_time', 'end_time', 'duration',
            'status', 'status_display',
            'total_records', 'new_records', 'duplicate_records', 'error_records',
            'data_from', 'data_to', 'error_message',
            'created_at'
        ]
    
    def get_duration(self, obj):
        if obj.end_time and obj.start_time:
            return (obj.end_time - obj.start_time).total_seconds()
        return None


# ============================================
# 视图集
# ============================================

class AttendanceDeviceViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    考勤设备管理视图集
    """
    queryset = AttendanceDevice.objects.filter(is_deleted=False)
    serializer_class = AttendanceDeviceSerializer
    filterset_fields = ['device_type', 'connection_type', 'status', 'department', 'sync_enabled']
    search_fields = ['name', 'device_sn', 'location']
    ordering_fields = ['name', 'created_at', 'last_sync_time']
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试设备连接"""
        device = self.get_object()
        
        try:
            # 根据连接类型测试
            if device.connection_type == 'TCP_IP':
                success, message = self._test_tcp_connection(device)
            elif device.connection_type in ['CLOUD_PUSH', 'CLOUD_PULL']:
                success, message = self._test_cloud_connection(device)
            else:
                success, message = False, '不支持的连接类型'
            
            if success:
                device.update_status('ONLINE')
                return Response({'success': True, 'message': message})
            else:
                device.update_status('ERROR', heartbeat=False)
                return Response({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"Test connection failed for device {device.device_sn}: {e}")
            device.update_status('ERROR', heartbeat=False)
            return Response({
                'success': False,
                'message': f'连接测试失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _test_tcp_connection(self, device):
        """测试TCP连接 - 尝试连接ZKTECO设备"""
        import socket
        try:
            # 首先检查端口是否可达
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((device.ip_address, device.port))
            sock.close()
            
            if result != 0:
                return False, f'TCP连接失败，端口 {device.ip_address}:{device.port} 未开放'
            
            # 尝试使用pyzk连接获取设备信息
            try:
                from zk import ZK
                zk = ZK(
                    device.ip_address,
                    port=device.port,
                    timeout=10,
                    password=int(device.device_password) if device.device_password else 0,
                    ommit_ping=True  # 跳过ping检查
                )
                conn = zk.connect()
                
                # 获取设备信息
                device_name = conn.get_device_name() or 'Unknown'
                serial = conn.get_serialnumber() or device.device_sn
                users = conn.get_users()
                attendances = conn.get_attendance()
                
                conn.disconnect()
                
                # 更新设备固件版本
                device.firmware_version = conn.get_firmware_version() if hasattr(conn, 'get_firmware_version') else ''
                device.save(update_fields=['firmware_version'])
                
                return True, f'连接成功! 设备: {device_name}, 用户数: {len(users)}, 记录数: {len(attendances)}'
            except ImportError:
                return True, f'TCP端口连接成功 ({device.ip_address}:{device.port})，pyzk库未安装'
            except Exception as e:
                return True, f'TCP端口可达，但设备通讯异常: {str(e)}'
                
        except Exception as e:
            return False, f'TCP连接异常: {str(e)}'
    
    def _test_cloud_connection(self, device):
        """测试云服务连接"""
        import requests
        try:
            if not device.cloud_server:
                return False, '未配置云服务地址'
            
            # 简单的HTTP请求测试
            response = requests.get(
                device.cloud_server,
                timeout=10,
                verify=False
            )
            if response.status_code < 500:
                return True, f'云服务连接成功 (HTTP {response.status_code})'
            else:
                return False, f'云服务异常 (HTTP {response.status_code})'
        except requests.Timeout:
            return False, '云服务连接超时'
        except Exception as e:
            return False, f'云服务连接异常: {str(e)}'
    
    @action(detail=True, methods=['post'])
    def sync_now(self, request, pk=None):
        """立即同步设备数据"""
        device = self.get_object()
        
        try:
            from .attendance_sync_service import AttendanceSyncService
            service = AttendanceSyncService(device)
            result = service.sync()
            
            return Response({
                'success': True,
                'message': f'同步完成，新增 {result["new_records"]} 条记录',
                'details': result
            })
        except Exception as e:
            logger.error(f"Sync failed for device {device.device_sn}: {e}")
            return Response({
                'success': False,
                'message': f'同步失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def sync_history(self, request, pk=None):
        """获取同步历史"""
        device = self.get_object()
        logs = device.sync_logs.order_by('-start_time')[:50]
        serializer = DeviceSyncLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def today_logs(self, request, pk=None):
        """获取今日打卡记录"""
        device = self.get_object()
        today = timezone.now().date()
        logs = device.attendance_logs.filter(
            punch_time__date=today,
            is_deleted=False
        ).order_by('-punch_time')
        serializer = DeviceAttendanceLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """设备概览统计"""
        devices = self.get_queryset()
        today = timezone.now().date()
        
        stats = {
            'total_devices': devices.count(),
            'online_devices': devices.filter(status='ONLINE').count(),
            'offline_devices': devices.filter(status='OFFLINE').count(),
            'error_devices': devices.filter(status='ERROR').count(),
            'today_records': DeviceAttendanceLog.objects.filter(
                punch_time__date=today,
                is_deleted=False
            ).count(),
            'unprocessed_records': DeviceAttendanceLog.objects.filter(
                is_processed=False,
                is_deleted=False
            ).count(),
        }
        
        return Response(stats)


class DeviceUserMappingViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    设备用户映射视图集
    """
    queryset = DeviceUserMapping.objects.filter(is_deleted=False)
    serializer_class = DeviceUserMappingSerializer
    filterset_fields = ['device', 'employee', 'is_synced']
    search_fields = ['device_user_id', 'device_user_name', 'employee__username', 'employee__first_name']
    ordering_fields = ['device', 'device_user_id', 'created_at']
    
    @action(detail=False, methods=['post'])
    def batch_create(self, request):
        """批量创建映射"""
        mappings = request.data.get('mappings', [])
        created = []
        errors = []
        
        for mapping_data in mappings:
            try:
                mapping, is_new = DeviceUserMapping.objects.get_or_create(
                    device_id=mapping_data['device'],
                    device_user_id=mapping_data['device_user_id'],
                    defaults={
                        'employee_id': mapping_data['employee'],
                        'device_user_name': mapping_data.get('device_user_name', ''),
                        'created_by': request.user
                    }
                )
                if is_new:
                    created.append(mapping_data)
            except Exception as e:
                errors.append({
                    'data': mapping_data,
                    'error': str(e)
                })
        
        return Response({
            'created': len(created),
            'errors': errors
        })
    
    @action(detail=False, methods=['get'])
    def unmapped_employees(self, request):
        """获取未映射的员工"""
        device_id = request.query_params.get('device')
        if not device_id:
            return Response({'error': '请指定设备'}, status=400)
        
        mapped_employee_ids = DeviceUserMapping.objects.filter(
            device_id=device_id,
            is_deleted=False
        ).values_list('employee_id', flat=True)
        
        from apps.accounts.models import User
        unmapped = User.objects.filter(
            is_active=True
        ).exclude(id__in=mapped_employee_ids)
        
        return Response([{
            'id': u.id,
            'username': u.username,
            'name': u.get_full_name(),
            'employee_id': getattr(u, 'employee_id', ''),
            'department': u.department.name if u.department else ''
        } for u in unmapped[:100]])


class DeviceAttendanceLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    设备打卡记录视图集（只读）
    """
    queryset = DeviceAttendanceLog.objects.filter(is_deleted=False)
    serializer_class = DeviceAttendanceLogSerializer
    filterset_fields = ['device', 'employee', 'punch_type', 'verify_type', 'is_processed']
    search_fields = ['device_user_id', 'employee__username']
    ordering_fields = ['punch_time', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # 日期范围筛选
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(punch_time__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(punch_time__date__lte=date_to)
        
        return queryset.select_related('device', 'employee')
    
    @action(detail=False, methods=['post'])
    def process_records(self, request):
        """处理打卡记录，转换为考勤记录"""
        record_ids = request.data.get('record_ids', [])
        
        if not record_ids:
            # 处理所有未处理的记录
            logs = self.get_queryset().filter(is_processed=False)
        else:
            logs = self.get_queryset().filter(id__in=record_ids, is_processed=False)
        
        from .attendance_sync_service import AttendanceSyncService
        processed, errors = AttendanceSyncService.process_device_logs(logs)
        
        return Response({
            'processed': processed,
            'errors': errors
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """打卡统计"""
        date = request.query_params.get('date', timezone.now().date().isoformat())
        
        logs = self.get_queryset().filter(punch_time__date=date)
        
        stats = {
            'date': date,
            'total': logs.count(),
            'by_device': {},
            'by_type': {},
            'by_verify': {},
        }
        
        for log in logs:
            # 按设备统计
            device_name = log.device.name
            if device_name not in stats['by_device']:
                stats['by_device'][device_name] = 0
            stats['by_device'][device_name] += 1
            
            # 按打卡类型统计
            punch_type = log.get_punch_type_display()
            if punch_type not in stats['by_type']:
                stats['by_type'][punch_type] = 0
            stats['by_type'][punch_type] += 1
            
            # 按验证方式统计
            verify_type = log.get_verify_type_display()
            if verify_type not in stats['by_verify']:
                stats['by_verify'][verify_type] = 0
            stats['by_verify'][verify_type] += 1
        
        return Response(stats)


class DeviceSyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    设备同步日志视图集（只读）
    """
    queryset = DeviceSyncLog.objects.all()
    serializer_class = DeviceSyncLogSerializer
    filterset_fields = ['device', 'sync_type', 'status']
    ordering_fields = ['start_time', 'end_time']
