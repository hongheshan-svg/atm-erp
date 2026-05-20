"""
企业微信考勤数据同步模块
支持从企业微信获取打卡数据并同步到OA系统
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

import requests
from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel

logger = logging.getLogger(__name__)


# ============================================
# 模型定义
# ============================================


class WechatWorkConfig(BaseModel):
    """
    企业微信配置
    存储企业微信API连接信息
    """

    name = models.CharField(max_length=100, default='默认配置', verbose_name='配置名称')
    corp_id = models.CharField(max_length=100, verbose_name='企业ID (CorpID)')
    agent_id = models.CharField(max_length=50, blank=True, verbose_name='应用ID (AgentID)')
    secret = models.CharField(max_length=200, verbose_name='应用密钥 (Secret)')

    # 打卡应用专用secret（如果有单独配置）
    checkin_secret = models.CharField(max_length=200, blank=True, verbose_name='打卡应用密钥')

    # 状态
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    last_sync_time = models.DateTimeField(null=True, blank=True, verbose_name='最后同步时间')

    # 同步配置
    sync_enabled = models.BooleanField(default=True, verbose_name='启用自动同步')
    sync_interval = models.PositiveIntegerField(default=600, verbose_name='同步间隔(秒)')
    sync_days = models.PositiveIntegerField(default=7, verbose_name='同步天数')

    class Meta:
        db_table = 'oa_wechat_work_config'
        verbose_name = '企业微信配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.name} ({self.corp_id})'

    def get_access_token(self, token_type='checkin'):
        """
        获取access_token，自动缓存
        token_type: 'checkin' 打卡, 'contact' 通讯录
        """
        cache_key = f'wechat_work_token_{self.id}_{token_type}'
        token = cache.get(cache_key)

        if token:
            return token

        # 获取新token
        secret = self.checkin_secret if (token_type == 'checkin' and self.checkin_secret) else self.secret

        url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
        params = {'corpid': self.corp_id, 'corpsecret': secret}

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data.get('errcode') == 0:
                token = data.get('access_token')
                expires_in = data.get('expires_in', 7200)
                # 缓存token，提前5分钟过期
                cache.set(cache_key, token, expires_in - 300)
                return token
            else:
                logger.error(f'获取企业微信token失败: {data}')
                return None
        except Exception as e:
            logger.error(f'获取企业微信token异常: {e}')
            return None


class WechatUserMapping(BaseModel):
    """
    企业微信用户与系统员工映射
    """

    config = models.ForeignKey(
        WechatWorkConfig, on_delete=models.CASCADE, related_name='user_mappings', verbose_name='企业微信配置'
    )
    wechat_userid = models.CharField(max_length=100, verbose_name='企业微信UserID')
    wechat_name = models.CharField(max_length=100, blank=True, verbose_name='企业微信姓名')

    employee = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='wechat_mappings', verbose_name='关联员工'
    )

    # 自动匹配标记
    auto_matched = models.BooleanField(default=False, verbose_name='自动匹配')

    class Meta:
        db_table = 'oa_wechat_user_mapping'
        verbose_name = '企业微信用户映射'
        verbose_name_plural = verbose_name
        unique_together = ['config', 'wechat_userid']

    def __str__(self):
        return f'{self.wechat_userid} -> {self.employee.get_full_name()}'


class WechatCheckinRecord(BaseModel):
    """
    企业微信打卡原始记录
    """

    CHECKIN_TYPE_CHOICES = [
        ('上班打卡', '上班打卡'),
        ('下班打卡', '下班打卡'),
        ('外出打卡', '外出打卡'),
        ('外出返回', '外出返回'),
    ]

    EXCEPTION_TYPE_CHOICES = [
        ('', '正常'),
        ('时间异常', '时间异常'),
        ('地点异常', '地点异常'),
        ('未打卡', '未打卡'),
        ('wifi异常', 'WiFi异常'),
        ('非常用设备', '非常用设备'),
    ]

    config = models.ForeignKey(
        WechatWorkConfig, on_delete=models.CASCADE, related_name='checkin_records', verbose_name='企业微信配置'
    )

    # 企业微信原始数据
    wechat_userid = models.CharField(max_length=100, verbose_name='企业微信UserID')
    checkin_time = models.DateTimeField(verbose_name='打卡时间')
    checkin_type = models.CharField(max_length=20, choices=CHECKIN_TYPE_CHOICES, verbose_name='打卡类型')

    # 打卡详情
    location_title = models.CharField(max_length=200, blank=True, verbose_name='打卡地点')
    location_detail = models.CharField(max_length=500, blank=True, verbose_name='详细地址')
    wifi_name = models.CharField(max_length=100, blank=True, verbose_name='WiFi名称')
    device_info = models.CharField(max_length=200, blank=True, verbose_name='设备信息')

    # 异常信息
    exception_type = models.CharField(
        max_length=20, choices=EXCEPTION_TYPE_CHOICES, blank=True, default='', verbose_name='异常类型'
    )
    notes = models.CharField(max_length=500, blank=True, verbose_name='备注')

    # 关联员工
    employee = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wechat_checkin_records',
        verbose_name='关联员工',
    )

    # 处理状态
    is_processed = models.BooleanField(default=False, verbose_name='是否已处理')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    attendance_record = models.ForeignKey(
        'accounts.AttendanceRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wechat_records',
        verbose_name='关联考勤记录',
    )

    # 原始数据
    raw_data = models.JSONField(default=dict, blank=True, verbose_name='原始数据')

    class Meta:
        db_table = 'oa_wechat_checkin_record'
        verbose_name = '企业微信打卡记录'
        verbose_name_plural = verbose_name
        ordering = ['-checkin_time']
        indexes = [
            models.Index(fields=['wechat_userid', 'checkin_time']),
            models.Index(fields=['employee', 'checkin_time']),
            models.Index(fields=['is_processed']),
        ]

    def __str__(self):
        return f'{self.wechat_userid} - {self.checkin_type} @ {self.checkin_time}'


class WechatSyncLog(BaseModel):
    """
    企业微信同步日志
    """

    STATUS_CHOICES = [
        ('PENDING', '进行中'),
        ('SUCCESS', '成功'),
        ('PARTIAL', '部分成功'),
        ('FAILED', '失败'),
    ]

    config = models.ForeignKey(
        WechatWorkConfig, on_delete=models.CASCADE, related_name='sync_logs', verbose_name='企业微信配置'
    )

    sync_date_from = models.DateField(verbose_name='同步起始日期')
    sync_date_to = models.DateField(verbose_name='同步截止日期')

    start_time = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    # 统计
    total_records = models.PositiveIntegerField(default=0, verbose_name='总记录数')
    new_records = models.PositiveIntegerField(default=0, verbose_name='新增记录数')
    processed_records = models.PositiveIntegerField(default=0, verbose_name='处理记录数')
    error_count = models.PositiveIntegerField(default=0, verbose_name='错误数')

    error_message = models.TextField(blank=True, verbose_name='错误信息')

    class Meta:
        db_table = 'oa_wechat_sync_log'
        verbose_name = '企业微信同步日志'
        verbose_name_plural = verbose_name
        ordering = ['-start_time']

    def __str__(self):
        return f'{self.config.name} - {self.sync_date_from} ~ {self.sync_date_to}'


# ============================================
# 企业微信API服务
# ============================================


class WechatWorkService:
    """
    企业微信API服务
    """

    def __init__(self, config: WechatWorkConfig):
        self.config = config
        self.base_url = 'https://qyapi.weixin.qq.com/cgi-bin'

    def _request(self, method: str, endpoint: str, token_type: str = 'checkin', **kwargs) -> Dict:
        """发送API请求"""
        token = self.config.get_access_token(token_type)
        if not token:
            return {'errcode': -1, 'errmsg': '获取access_token失败'}

        url = f'{self.base_url}/{endpoint}?access_token={token}'

        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=kwargs.get('params', {}), timeout=30)
            else:
                response = requests.post(url, json=kwargs.get('json', {}), timeout=30)

            return response.json()
        except Exception as e:
            logger.error(f'企业微信API请求失败: {e}')
            return {'errcode': -1, 'errmsg': str(e)}

    def get_checkin_data(self, userids: List[str], start_time: int, end_time: int) -> Dict:
        """
        获取打卡数据

        Args:
            userids: 用户ID列表
            start_time: 开始时间戳
            end_time: 结束时间戳
        """
        data = {
            'opencheckindatatype': 3,  # 1-上下班打卡 2-外出打卡 3-全部
            'starttime': start_time,
            'endtime': end_time,
            'useridlist': userids,
        }

        return self._request('POST', 'checkin/getcheckindata', json=data)

    def get_checkin_day_data(self, userids: List[str], start_time: int, end_time: int) -> Dict:
        """
        获取打卡日报数据
        """
        data = {'starttime': start_time, 'endtime': end_time, 'useridlist': userids}

        return self._request('POST', 'checkin/getcheckin_daydata', json=data)

    def get_checkin_month_data(self, userids: List[str], start_time: int, end_time: int) -> Dict:
        """
        获取打卡月报数据
        """
        data = {'starttime': start_time, 'endtime': end_time, 'useridlist': userids}

        return self._request('POST', 'checkin/getcheckin_monthdata', json=data)

    def get_department_users(self, department_id: int = 1) -> Dict:
        """
        获取部门成员
        """
        params = {'department_id': department_id, 'fetch_child': 1}
        return self._request('GET', 'user/simplelist', token_type='contact', params=params)

    def sync_checkin_data(self, date_from: date, date_to: date) -> Dict:
        """
        同步指定日期范围的打卡数据

        Returns:
            同步结果
        """
        result = {'total': 0, 'new': 0, 'processed': 0, 'errors': []}

        # 获取所有映射的用户
        mappings = WechatUserMapping.objects.filter(config=self.config, is_deleted=False).select_related('employee')

        if not mappings.exists():
            result['errors'].append('没有配置用户映射，请先配置用户映射')
            return result

        # 按批次获取数据（企业微信限制每次最多100人）
        userids = [m.wechat_userid for m in mappings]
        mapping_dict = {m.wechat_userid: m.employee for m in mappings}

        batch_size = 100
        start_ts = int(datetime.combine(date_from, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(date_to, datetime.max.time()).timestamp())

        for i in range(0, len(userids), batch_size):
            batch_userids = userids[i : i + batch_size]

            try:
                response = self.get_checkin_data(batch_userids, start_ts, end_ts)

                if response.get('errcode') != 0:
                    result['errors'].append(f"API错误: {response.get('errmsg')}")
                    continue

                checkin_data = response.get('checkindata', [])
                result['total'] += len(checkin_data)

                for record in checkin_data:
                    try:
                        saved, is_new = self._save_checkin_record(record, mapping_dict)
                        if is_new:
                            result['new'] += 1
                    except Exception as e:
                        result['errors'].append(f'保存记录失败: {e}')

            except Exception as e:
                result['errors'].append(f'批次同步失败: {e}')

        # 处理新记录
        if result['new'] > 0:
            processed = self._process_checkin_records()
            result['processed'] = processed

        # 更新配置最后同步时间
        self.config.last_sync_time = timezone.now()
        self.config.save(update_fields=['last_sync_time'])

        return result

    def _save_checkin_record(self, data: Dict, mapping_dict: Dict) -> Tuple[Any, bool]:
        """
        保存打卡记录
        """
        wechat_userid = data.get('userid', '')
        checkin_time = datetime.fromtimestamp(data.get('checkin_time', 0))
        checkin_time = timezone.make_aware(checkin_time)

        # 检查是否已存在
        existing = WechatCheckinRecord.objects.filter(
            config=self.config, wechat_userid=wechat_userid, checkin_time=checkin_time
        ).first()

        if existing:
            return existing, False

        # 获取关联员工
        employee = mapping_dict.get(wechat_userid)

        # 解析打卡类型
        checkin_type_map = {
            '上班打卡': '上班打卡',
            '下班打卡': '下班打卡',
            '外出打卡': '外出打卡',
            '外出返回打卡': '外出返回',
        }
        checkin_type = checkin_type_map.get(data.get('checkin_type', ''), '上班打卡')

        # 创建记录
        record = WechatCheckinRecord.objects.create(
            config=self.config,
            wechat_userid=wechat_userid,
            checkin_time=checkin_time,
            checkin_type=checkin_type,
            location_title=data.get('location_title', ''),
            location_detail=data.get('location_detail', ''),
            wifi_name=data.get('wifiname', ''),
            device_info=data.get('deviceinfo', ''),
            exception_type=data.get('exception_type', ''),
            notes=data.get('notes', ''),
            employee=employee,
            raw_data=data,
        )

        return record, True

    def _process_checkin_records(self) -> int:
        """
        处理打卡记录，转换为系统考勤记录
        """
        from apps.accounts.attendance import AttendanceRecord

        # 获取未处理的记录
        records = WechatCheckinRecord.objects.filter(
            config=self.config, is_processed=False, employee__isnull=False
        ).order_by('checkin_time')

        # 按员工和日期分组
        employee_dates = {}
        for record in records:
            key = (record.employee_id, record.checkin_time.date())
            if key not in employee_dates:
                employee_dates[key] = []
            employee_dates[key].append(record)

        processed = 0

        for (employee_id, checkin_date), day_records in employee_dates.items():
            try:
                with transaction.atomic():
                    # 获取或创建当天的考勤记录
                    attendance, created = AttendanceRecord.objects.get_or_create(
                        user_id=employee_id, attendance_date=checkin_date, defaults={'status': 'NORMAL'}
                    )

                    # 按时间排序
                    day_records.sort(key=lambda x: x.checkin_time)

                    # 找出签到和签退时间
                    check_in = None
                    check_out = None

                    for r in day_records:
                        if r.checkin_type == '上班打卡':
                            if not check_in or r.checkin_time < check_in:
                                check_in = r.checkin_time
                        elif r.checkin_type == '下班打卡':
                            if not check_out or r.checkin_time > check_out:
                                check_out = r.checkin_time

                    # 如果没有明确的上下班打卡，用第一次和最后一次
                    if not check_in and day_records:
                        check_in = day_records[0].checkin_time
                    if not check_out and len(day_records) > 1:
                        check_out = day_records[-1].checkin_time

                    # 更新考勤记录
                    if check_in and (not attendance.check_in_time or check_in < attendance.check_in_time):
                        attendance.check_in_time = check_in
                    if check_out and (not attendance.check_out_time or check_out > attendance.check_out_time):
                        attendance.check_out_time = check_out

                    # 添加备注
                    if not attendance.remarks:
                        attendance.remarks = ''
                    if '企业微信' not in attendance.remarks:
                        attendance.remarks = f'[企业微信同步] {attendance.remarks}'.strip()

                    attendance.save()

                    # 标记记录为已处理
                    for r in day_records:
                        r.is_processed = True
                        r.processed_at = timezone.now()
                        r.attendance_record = attendance
                        r.save(update_fields=['is_processed', 'processed_at', 'attendance_record'])

                    processed += len(day_records)

            except Exception as e:
                logger.error(f'处理企业微信打卡记录失败: {e}')

        return processed


# ============================================
# 序列化器
# ============================================


class WechatWorkConfigSerializer(serializers.ModelSerializer):
    """企业微信配置序列化器"""

    user_count = serializers.SerializerMethodField()
    record_count = serializers.SerializerMethodField()

    class Meta:
        model = WechatWorkConfig
        fields = [
            'id',
            'name',
            'corp_id',
            'agent_id',
            'secret',
            'checkin_secret',
            'is_active',
            'last_sync_time',
            'sync_enabled',
            'sync_interval',
            'sync_days',
            'user_count',
            'record_count',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'secret': {'write_only': True},
            'checkin_secret': {'write_only': True},
        }

    def get_user_count(self, obj):
        return obj.user_mappings.filter(is_deleted=False).count()

    def get_record_count(self, obj):
        return obj.checkin_records.filter(is_deleted=False).count()


class WechatUserMappingSerializer(serializers.ModelSerializer):
    """用户映射序列化器"""

    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_id', read_only=True)

    class Meta:
        model = WechatUserMapping
        fields = [
            'id',
            'config',
            'wechat_userid',
            'wechat_name',
            'employee',
            'employee_name',
            'employee_code',
            'auto_matched',
            'created_at',
        ]


class WechatCheckinRecordSerializer(serializers.ModelSerializer):
    """打卡记录序列化器"""

    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)

    class Meta:
        model = WechatCheckinRecord
        fields = [
            'id',
            'wechat_userid',
            'checkin_time',
            'checkin_type',
            'location_title',
            'location_detail',
            'wifi_name',
            'exception_type',
            'notes',
            'employee',
            'employee_name',
            'is_processed',
            'processed_at',
            'created_at',
        ]


class WechatSyncLogSerializer(serializers.ModelSerializer):
    """同步日志序列化器"""

    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = WechatSyncLog
        fields = [
            'id',
            'config',
            'sync_date_from',
            'sync_date_to',
            'start_time',
            'end_time',
            'status',
            'status_display',
            'total_records',
            'new_records',
            'processed_records',
            'error_count',
            'error_message',
            'created_at',
        ]


# ============================================
# 视图集
# ============================================


class WechatWorkConfigViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """企业微信配置管理"""

    queryset = WechatWorkConfig.objects.filter(is_deleted=False)
    serializer_class = WechatWorkConfigSerializer

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试企业微信连接"""
        config = self.get_object()

        token = config.get_access_token()
        if token:
            return Response({'success': True, 'message': '企业微信连接成功!'})
        else:
            return Response({'success': False, 'message': '连接失败，请检查CorpID和Secret是否正确'})

    @action(detail=True, methods=['post'])
    def sync_now(self, request, pk=None):
        """立即同步打卡数据"""
        config = self.get_object()

        days = int(request.data.get('days', config.sync_days))
        date_to = date.today()
        date_from = date_to - timedelta(days=days - 1)

        # 创建同步日志
        sync_log = WechatSyncLog.objects.create(config=config, sync_date_from=date_from, sync_date_to=date_to)

        try:
            service = WechatWorkService(config)
            result = service.sync_checkin_data(date_from, date_to)

            sync_log.total_records = result['total']
            sync_log.new_records = result['new']
            sync_log.processed_records = result['processed']
            sync_log.error_count = len(result['errors'])
            sync_log.error_message = '\n'.join(result['errors'][:10])
            sync_log.status = 'SUCCESS' if not result['errors'] else 'PARTIAL'
            sync_log.end_time = timezone.now()
            sync_log.save()

            return Response(
                {
                    'success': True,
                    'message': f"同步完成! 获取 {result['total']} 条记录，新增 {result['new']} 条，处理 {result['processed']} 条",
                    'details': result,
                }
            )

        except Exception as e:
            sync_log.status = 'FAILED'
            sync_log.error_message = str(e)
            sync_log.end_time = timezone.now()
            sync_log.save()

            return Response({'success': False, 'message': f'同步失败: {str(e)}'}, status=500)

    @action(detail=True, methods=['get'])
    def sync_history(self, request, pk=None):
        """获取同步历史"""
        config = self.get_object()
        logs = config.sync_logs.order_by('-start_time')[:50]
        serializer = WechatSyncLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def auto_match_users(self, request, pk=None):
        """自动匹配用户（根据姓名）"""
        config = self.get_object()

        from apps.accounts.models import User

        # 获取企业微信用户列表
        service = WechatWorkService(config)
        response = service.get_department_users()

        if response.get('errcode') != 0:
            return Response({'success': False, 'message': f"获取企业微信用户失败: {response.get('errmsg')}"})

        matched = 0
        wechat_users = response.get('userlist', [])

        for wu in wechat_users:
            userid = wu.get('userid')
            name = wu.get('name')

            # 检查是否已映射
            if WechatUserMapping.objects.filter(config=config, wechat_userid=userid).exists():
                continue

            # 按姓名匹配
            employee = (
                User.objects.filter(is_active=True)
                .filter(models.Q(first_name=name) | models.Q(last_name=name) | models.Q(username=name))
                .first()
            )

            if employee:
                WechatUserMapping.objects.create(
                    config=config, wechat_userid=userid, wechat_name=name, employee=employee, auto_matched=True
                )
                matched += 1

        return Response(
            {
                'success': True,
                'message': f'自动匹配完成，匹配了 {matched} 个用户',
                'matched': matched,
                'total': len(wechat_users),
            }
        )


class WechatUserMappingViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """企业微信用户映射管理"""

    queryset = WechatUserMapping.objects.filter(is_deleted=False)
    serializer_class = WechatUserMappingSerializer
    filterset_fields = ['config', 'employee']
    search_fields = ['wechat_userid', 'wechat_name', 'employee__first_name']


class WechatCheckinRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """企业微信打卡记录（只读）"""

    queryset = WechatCheckinRecord.objects.filter(is_deleted=False)
    serializer_class = WechatCheckinRecordSerializer
    filterset_fields = ['config', 'employee', 'checkin_type', 'is_processed']
    search_fields = ['wechat_userid', 'location_title']
    ordering_fields = ['checkin_time']

    def get_queryset(self):
        queryset = super().get_queryset()

        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if date_from:
            queryset = queryset.filter(checkin_time__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(checkin_time__date__lte=date_to)

        return queryset.select_related('employee')


class WechatSyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    """企业微信同步日志（只读）"""

    queryset = WechatSyncLog.objects.all()
    serializer_class = WechatSyncLogSerializer
    filterset_fields = ['config', 'status']
    ordering_fields = ['start_time']
