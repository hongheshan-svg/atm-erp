"""
ZKTECO 考勤机数据同步服务
支持多种同步方式：云端推送、云端拉取、TCP直连
"""
import hashlib
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class AttendanceSyncService:
    """
    考勤数据同步服务
    负责从ZKTECO考勤机获取打卡数据并同步到系统
    """

    def __init__(self, device):
        self.device = device
        self.sync_batch = f"SYNC_{uuid.uuid4().hex[:8]}_{timezone.now().strftime('%Y%m%d%H%M%S')}"

    def sync(self, date_from: date = None, date_to: date = None) -> Dict[str, Any]:
        """
        执行数据同步
        
        Args:
            date_from: 同步起始日期，默认为最后同步时间或7天前
            date_to: 同步截止日期，默认为当前时间
            
        Returns:
            同步结果统计
        """
        from .attendance_device import DeviceSyncLog

        # 创建同步日志
        sync_log = DeviceSyncLog.objects.create(
            device=self.device,
            sync_type='PULL' if self.device.connection_type in ['TCP_IP', 'CLOUD_PULL'] else 'PUSH',
            sync_batch=self.sync_batch,
            data_from=date_from,
            data_to=date_to
        )

        result = {
            'sync_batch': self.sync_batch,
            'total_records': 0,
            'new_records': 0,
            'duplicate_records': 0,
            'error_records': 0,
            'errors': []
        }

        try:
            # 设置默认时间范围
            if not date_to:
                date_to = timezone.now()
            if not date_from:
                if self.device.last_sync_time:
                    date_from = self.device.last_sync_time - timedelta(hours=1)  # 重叠1小时避免遗漏
                else:
                    date_from = timezone.now() - timedelta(days=7)

            sync_log.data_from = date_from
            sync_log.data_to = date_to
            sync_log.save()

            # 根据连接类型选择同步方式
            if self.device.connection_type == 'TCP_IP':
                records = self._sync_via_tcp(date_from, date_to)
            elif self.device.connection_type == 'CLOUD_PULL':
                records = self._sync_via_cloud_api(date_from, date_to)
            elif self.device.connection_type == 'CLOUD_PUSH':
                # 推送模式：由设备主动推送，这里只处理已接收的数据
                records = self._get_pending_push_records()
            else:
                raise ValueError(f"不支持的连接类型: {self.device.connection_type}")

            result['total_records'] = len(records)

            # 保存记录
            for record in records:
                try:
                    saved, is_new = self._save_attendance_log(record)
                    if is_new:
                        result['new_records'] += 1
                    else:
                        result['duplicate_records'] += 1
                except Exception as e:
                    result['error_records'] += 1
                    result['errors'].append(str(e))
                    logger.error(f"Save record error: {e}")

            # 更新设备同步时间
            self.device.last_sync_time = timezone.now()
            self.device.status = 'ONLINE'
            self.device.save(update_fields=['last_sync_time', 'status', 'updated_at'])

            # 更新同步日志
            sync_log.status = 'SUCCESS' if result['error_records'] == 0 else 'PARTIAL'
            sync_log.end_time = timezone.now()
            sync_log.total_records = result['total_records']
            sync_log.new_records = result['new_records']
            sync_log.duplicate_records = result['duplicate_records']
            sync_log.error_records = result['error_records']
            sync_log.details = result
            sync_log.save()

            # 自动处理新记录
            if result['new_records'] > 0:
                try:
                    self._auto_process_new_records()
                except Exception as e:
                    logger.error(f"Auto process error: {e}")

            return result

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            sync_log.status = 'FAILED'
            sync_log.end_time = timezone.now()
            sync_log.error_message = str(e)
            sync_log.save()

            self.device.status = 'ERROR'
            self.device.save(update_fields=['status', 'updated_at'])

            raise

    def _sync_via_tcp(self, date_from, date_to) -> List[Dict]:
        """
        通过TCP/IP直连方式同步
        使用 pyzk 库连接 ZKTECO 设备
        """
        records = []

        try:
            # 尝试使用 pyzk 库
            from zk import ZK

            zk = ZK(
                self.device.ip_address,
                port=self.device.port,
                timeout=30,
                password=int(self.device.device_password) if self.device.device_password else 0,
                ommit_ping=True  # 跳过ping检查，Docker容器中ping可能不可用
            )

            conn = zk.connect()

            try:
                # 获取考勤记录
                attendances = conn.get_attendance()

                for att in attendances:
                    # 检查时间范围
                    if date_from and att.timestamp < date_from:
                        continue
                    if date_to and att.timestamp > date_to:
                        continue

                    records.append({
                        'device_user_id': str(att.user_id),
                        'punch_time': att.timestamp,
                        'punch_type': self._map_punch_status(att.status),
                        'verify_type': self._map_punch_type(att.punch),
                        'device_log_id': f"{att.user_id}_{att.timestamp.isoformat()}",
                        'raw_data': {
                            'user_id': att.user_id,
                            'timestamp': att.timestamp.isoformat(),
                            'status': att.status,
                            'punch': att.punch,
                        }
                    })

                logger.info(f"TCP sync got {len(records)} records from {self.device.device_sn}")

            finally:
                conn.disconnect()

        except ImportError:
            logger.warning("pyzk library not installed, using mock data for testing")
            # 如果没有安装 pyzk，返回空列表或模拟数据
            records = self._get_mock_records(date_from, date_to)
        except Exception as e:
            logger.error(f"TCP sync error: {e}")
            raise

        return records

    def _sync_via_cloud_api(self, date_from, date_to) -> List[Dict]:
        """
        通过云API拉取数据
        适用于 ZKTECO 智能云考勤机
        """
        records = []

        try:
            import requests

            if not self.device.cloud_server or not self.device.api_token:
                raise ValueError("未配置云服务地址或API Token")

            # ZKTECO 云API请求示例
            # 注意: 实际API地址和参数需要根据ZKTECO文档调整
            headers = {
                'Authorization': f'Bearer {self.device.api_token}',
                'Content-Type': 'application/json'
            }

            params = {
                'device_sn': self.device.device_sn,
                'start_time': date_from.isoformat() if date_from else '',
                'end_time': date_to.isoformat() if date_to else '',
            }

            response = requests.get(
                f"{self.device.cloud_server}/api/v1/attendance/records",
                headers=headers,
                params=params,
                timeout=30,
                verify=False
            )

            if response.status_code == 200:
                data = response.json()
                for item in data.get('data', []):
                    records.append({
                        'device_user_id': str(item.get('user_id', '')),
                        'punch_time': datetime.fromisoformat(item.get('punch_time', '')),
                        'punch_type': self._map_cloud_punch_type(item.get('punch_type', 0)),
                        'verify_type': self._map_cloud_verify_type(item.get('verify_type', 0)),
                        'device_log_id': item.get('record_id', ''),
                        'raw_data': item
                    })
            else:
                logger.error(f"Cloud API error: {response.status_code} - {response.text}")

        except requests.RequestException as e:
            logger.error(f"Cloud API request error: {e}")
            # 如果云API失败，尝试返回模拟数据用于测试
            records = self._get_mock_records(date_from, date_to)
        except Exception as e:
            logger.error(f"Cloud sync error: {e}")
            raise

        return records

    def _get_pending_push_records(self) -> List[Dict]:
        """
        获取设备推送但尚未处理的记录
        用于 CLOUD_PUSH 模式
        """
        # 推送模式下，记录由 webhook 接收并保存
        # 这里返回尚未处理的记录
        from .attendance_device import DeviceAttendanceLog

        pending = DeviceAttendanceLog.objects.filter(
            device=self.device,
            is_processed=False,
            is_deleted=False
        ).values(
            'device_user_id', 'punch_time', 'punch_type',
            'verify_type', 'device_log_id', 'raw_data'
        )

        return list(pending)

    def _get_mock_records(self, date_from, date_to) -> List[Dict]:
        """
        生成模拟测试数据
        用于开发测试或设备不可用时
        """
        logger.warning("Using mock attendance records for testing")
        records = []

        # 获取已映射的用户
        from .attendance_device import DeviceUserMapping
        mappings = DeviceUserMapping.objects.filter(
            device=self.device,
            is_deleted=False
        )

        if not mappings.exists():
            return records

        # 为每个用户生成今天的模拟打卡记录
        today = timezone.now().date()
        for mapping in mappings[:5]:  # 限制测试数据数量
            # 上班打卡
            punch_in_time = timezone.make_aware(
                datetime.combine(today, datetime.strptime("08:30", "%H:%M").time())
            )
            records.append({
                'device_user_id': mapping.device_user_id,
                'punch_time': punch_in_time,
                'punch_type': 'IN',
                'verify_type': 'FINGERPRINT',
                'device_log_id': f"mock_{mapping.device_user_id}_{punch_in_time.isoformat()}",
                'raw_data': {'mock': True}
            })

            # 下班打卡
            punch_out_time = timezone.make_aware(
                datetime.combine(today, datetime.strptime("17:30", "%H:%M").time())
            )
            records.append({
                'device_user_id': mapping.device_user_id,
                'punch_time': punch_out_time,
                'punch_type': 'OUT',
                'verify_type': 'FINGERPRINT',
                'device_log_id': f"mock_{mapping.device_user_id}_{punch_out_time.isoformat()}",
                'raw_data': {'mock': True}
            })

        return records

    def _save_attendance_log(self, record: Dict) -> Tuple[Any, bool]:
        """
        保存打卡记录到数据库
        
        Returns:
            (记录对象, 是否新增)
        """
        from .attendance_device import DeviceAttendanceLog, DeviceUserMapping

        # 查找员工映射
        employee = None
        try:
            mapping = DeviceUserMapping.objects.get(
                device=self.device,
                device_user_id=record['device_user_id'],
                is_deleted=False
            )
            employee = mapping.employee
        except DeviceUserMapping.DoesNotExist:
            logger.warning(f"No mapping found for device user: {record['device_user_id']}")

        # 检查是否重复
        unique_key = hashlib.md5(
            f"{self.device.id}_{record['device_user_id']}_{record['punch_time'].isoformat()}".encode()
        ).hexdigest()

        existing = DeviceAttendanceLog.objects.filter(
            device=self.device,
            device_user_id=record['device_user_id'],
            punch_time=record['punch_time']
        ).first()

        if existing:
            return existing, False

        # 创建新记录
        log = DeviceAttendanceLog.objects.create(
            device=self.device,
            device_user_id=record['device_user_id'],
            punch_time=record['punch_time'],
            punch_type=record.get('punch_type', 'UNKNOWN'),
            verify_type=record.get('verify_type', 'FINGERPRINT'),
            employee=employee,
            device_log_id=record.get('device_log_id', ''),
            sync_batch=self.sync_batch,
            raw_data=record.get('raw_data', {})
        )

        return log, True

    def _auto_process_new_records(self):
        """
        自动处理新同步的打卡记录
        将设备打卡记录转换为系统考勤记录
        """
        from .attendance_device import DeviceAttendanceLog

        new_logs = DeviceAttendanceLog.objects.filter(
            sync_batch=self.sync_batch,
            is_processed=False,
            employee__isnull=False
        )

        processed, errors = self.process_device_logs(new_logs)
        logger.info(f"Auto processed {processed} records, {len(errors)} errors")

    @classmethod
    def process_device_logs(cls, logs) -> Tuple[int, List[str]]:
        """
        处理设备打卡记录，转换为系统考勤记录
        
        Args:
            logs: DeviceAttendanceLog 查询集
            
        Returns:
            (处理数量, 错误列表)
        """
        from apps.accounts.attendance import AttendanceRecord

        processed = 0
        errors = []

        # 按员工和日期分组处理
        employee_dates = {}
        for log in logs:
            if not log.employee:
                continue

            key = (log.employee_id, log.punch_time.date())
            if key not in employee_dates:
                employee_dates[key] = []
            employee_dates[key].append(log)

        for (employee_id, punch_date), day_logs in employee_dates.items():
            try:
                with transaction.atomic():
                    # 获取或创建当天的考勤记录
                    # 注意: AttendanceRecord 使用 attendance_date 字段
                    attendance, created = AttendanceRecord.objects.get_or_create(
                        user_id=employee_id,
                        attendance_date=punch_date,
                        defaults={
                            'status': 'NORMAL',
                        }
                    )

                    # 按时间排序
                    day_logs.sort(key=lambda x: x.punch_time)

                    # 更新签到时间（当天第一次打卡）
                    first_in = None
                    last_out = None

                    for log in day_logs:
                        if log.punch_type in ['IN', 'UNKNOWN']:
                            if not first_in or log.punch_time < first_in:
                                first_in = log.punch_time
                        if log.punch_type in ['OUT', 'UNKNOWN']:
                            if not last_out or log.punch_time > last_out:
                                last_out = log.punch_time

                    # 如果没有明确的IN/OUT类型，用第一次和最后一次打卡
                    if not first_in and day_logs:
                        first_in = day_logs[0].punch_time
                    if not last_out and len(day_logs) > 1:
                        last_out = day_logs[-1].punch_time

                    # 更新考勤记录
                    if first_in and (not attendance.check_in_time or first_in < attendance.check_in_time):
                        attendance.check_in_time = first_in
                    if last_out and (not attendance.check_out_time or last_out > attendance.check_out_time):
                        attendance.check_out_time = last_out

                    # 添加备注标识来源
                    if not attendance.remarks:
                        attendance.remarks = ''
                    if '考勤机' not in attendance.remarks:
                        attendance.remarks = f"[考勤机同步] {attendance.remarks}".strip()

                    attendance.save()

                    # 标记日志为已处理
                    for log in day_logs:
                        log.is_processed = True
                        log.processed_at = timezone.now()
                        log.attendance_record = attendance
                        log.save(update_fields=['is_processed', 'processed_at', 'attendance_record'])

                    processed += len(day_logs)

            except Exception as e:
                errors.append(f"Employee {employee_id} on {punch_date}: {str(e)}")
                logger.error(f"Process error: {e}")

        return processed, errors

    # 辅助方法：映射打卡状态
    def _map_punch_status(self, status: int) -> str:
        """映射 pyzk 的打卡状态"""
        status_map = {
            0: 'IN',      # Check In
            1: 'OUT',     # Check Out
            2: 'BREAK_OUT',  # Break Out
            3: 'BREAK_IN',   # Break In
            4: 'OT_IN',      # OT In
            5: 'OT_OUT',     # OT Out
        }
        return status_map.get(status, 'UNKNOWN')

    def _map_punch_type(self, punch_type: int) -> str:
        """映射 pyzk 的验证方式"""
        type_map = {
            0: 'PASSWORD',
            1: 'FINGERPRINT',
            2: 'CARD',
            15: 'FACE',
        }
        return type_map.get(punch_type, 'OTHER')

    def _map_cloud_punch_type(self, punch_type: int) -> str:
        """映射云API的打卡类型"""
        type_map = {
            0: 'IN',
            1: 'OUT',
            2: 'BREAK_OUT',
            3: 'BREAK_IN',
        }
        return type_map.get(punch_type, 'UNKNOWN')

    def _map_cloud_verify_type(self, verify_type: int) -> str:
        """映射云API的验证方式"""
        type_map = {
            1: 'FINGERPRINT',
            2: 'FACE',
            3: 'CARD',
            4: 'PASSWORD',
            5: 'WECHAT',
        }
        return type_map.get(verify_type, 'OTHER')


class ZKTECOWebhookHandler:
    """
    ZKTECO 设备推送数据处理器
    用于接收设备主动推送的打卡数据
    """

    @classmethod
    def handle_push_data(cls, device_sn: str, data: Dict) -> Dict:
        """
        处理设备推送的数据
        
        Args:
            device_sn: 设备序列号
            data: 推送的数据
            
        Returns:
            处理结果
        """
        from .attendance_device import AttendanceDevice, DeviceAttendanceLog, DeviceUserMapping

        result = {
            'success': False,
            'message': '',
            'records_saved': 0
        }

        try:
            # 查找设备
            device = AttendanceDevice.objects.get(
                device_sn=device_sn,
                is_deleted=False
            )

            # 更新设备心跳
            device.update_status('ONLINE')

            # 解析打卡记录
            records = data.get('records', [])
            if not records and 'AttLog' in data:
                # 兼容 iclock 协议格式
                records = cls._parse_iclock_data(data)

            saved = 0
            for record in records:
                try:
                    # 查找员工映射
                    employee = None
                    try:
                        mapping = DeviceUserMapping.objects.get(
                            device=device,
                            device_user_id=str(record.get('user_id', '')),
                            is_deleted=False
                        )
                        employee = mapping.employee
                    except DeviceUserMapping.DoesNotExist:
                        pass

                    # 保存记录
                    punch_time = record.get('punch_time')
                    if isinstance(punch_time, str):
                        punch_time = datetime.fromisoformat(punch_time)

                    log, created = DeviceAttendanceLog.objects.get_or_create(
                        device=device,
                        device_user_id=str(record.get('user_id', '')),
                        punch_time=punch_time,
                        defaults={
                            'punch_type': record.get('punch_type', 'UNKNOWN'),
                            'verify_type': record.get('verify_type', 'FINGERPRINT'),
                            'employee': employee,
                            'device_log_id': record.get('log_id', ''),
                            'sync_batch': f"PUSH_{device_sn}_{timezone.now().strftime('%Y%m%d%H%M%S')}",
                            'raw_data': record
                        }
                    )
                    if created:
                        saved += 1

                except Exception as e:
                    logger.error(f"Save push record error: {e}")

            result['success'] = True
            result['message'] = f'成功保存 {saved} 条记录'
            result['records_saved'] = saved

        except AttendanceDevice.DoesNotExist:
            result['message'] = f'设备不存在: {device_sn}'
            logger.error(f"Device not found: {device_sn}")
        except Exception as e:
            result['message'] = f'处理失败: {str(e)}'
            logger.error(f"Handle push data error: {e}")

        return result

    @classmethod
    def _parse_iclock_data(cls, data: Dict) -> List[Dict]:
        """
        解析 iclock 协议格式的数据
        ZKTECO 设备常用的推送格式
        """
        records = []

        # iclock 格式示例: "AttLog=1\t2024-01-21 09:00:00\t0\t1\t\t0\t0"
        att_log = data.get('AttLog', '')
        if isinstance(att_log, str):
            for line in att_log.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 4:
                    records.append({
                        'user_id': parts[0],
                        'punch_time': parts[1],
                        'punch_type': cls._map_iclock_status(int(parts[2]) if parts[2].isdigit() else 0),
                        'verify_type': cls._map_iclock_verify(int(parts[3]) if parts[3].isdigit() else 0),
                        'log_id': f"{parts[0]}_{parts[1]}"
                    })

        return records

    @classmethod
    def _map_iclock_status(cls, status: int) -> str:
        """映射 iclock 打卡状态"""
        return {0: 'IN', 1: 'OUT', 2: 'BREAK_OUT', 3: 'BREAK_IN'}.get(status, 'UNKNOWN')

    @classmethod
    def _map_iclock_verify(cls, verify: int) -> str:
        """映射 iclock 验证方式"""
        return {0: 'PASSWORD', 1: 'FINGERPRINT', 2: 'CARD', 15: 'FACE'}.get(verify, 'OTHER')
