"""
OA模块 Celery 定时任务
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_attendance_device(self, device_id: int):
    """
    同步单个考勤设备的数据
    
    Args:
        device_id: 设备ID
    """
    from .attendance_device import AttendanceDevice
    from .attendance_sync_service import AttendanceSyncService
    
    try:
        device = AttendanceDevice.objects.get(id=device_id, is_deleted=False)
        
        if not device.sync_enabled:
            logger.info(f"Device {device.device_sn} sync is disabled")
            return {'status': 'skipped', 'reason': 'sync disabled'}
        
        service = AttendanceSyncService(device)
        result = service.sync()
        
        logger.info(f"Device {device.device_sn} synced: {result['new_records']} new records")
        return {
            'status': 'success',
            'device_sn': device.device_sn,
            'new_records': result['new_records']
        }
        
    except AttendanceDevice.DoesNotExist:
        logger.error(f"Device not found: {device_id}")
        return {'status': 'error', 'reason': 'device not found'}
    except Exception as e:
        logger.error(f"Sync device {device_id} failed: {e}")
        # 重试
        raise self.retry(exc=e, countdown=60)


@shared_task
def sync_all_attendance_devices():
    """
    同步所有启用自动同步的考勤设备
    建议每5-10分钟执行一次
    """
    from .attendance_device import AttendanceDevice
    
    devices = AttendanceDevice.objects.filter(
        is_deleted=False,
        sync_enabled=True,
        connection_type__in=['TCP_IP', 'CLOUD_PULL']  # 只同步拉取模式的设备
    )
    
    results = []
    for device in devices:
        # 检查是否需要同步（根据同步间隔）
        if device.last_sync_time:
            next_sync = device.last_sync_time + timedelta(seconds=device.sync_interval)
            if timezone.now() < next_sync:
                continue
        
        # 异步执行同步任务
        task = sync_attendance_device.delay(device.id)
        results.append({
            'device_id': device.id,
            'device_sn': device.device_sn,
            'task_id': task.id
        })
    
    logger.info(f"Scheduled sync for {len(results)} devices")
    return results


@shared_task
def process_unprocessed_attendance_logs():
    """
    处理未处理的设备打卡记录
    将其转换为系统考勤记录
    """
    from .attendance_device import DeviceAttendanceLog
    from .attendance_sync_service import AttendanceSyncService
    
    # 获取未处理且有员工映射的记录
    logs = DeviceAttendanceLog.objects.filter(
        is_processed=False,
        is_deleted=False,
        employee__isnull=False
    ).order_by('punch_time')[:1000]  # 每次最多处理1000条
    
    if not logs.exists():
        return {'status': 'no_pending_logs'}
    
    processed, errors = AttendanceSyncService.process_device_logs(logs)
    
    logger.info(f"Processed {processed} attendance logs, {len(errors)} errors")
    return {
        'status': 'success',
        'processed': processed,
        'errors': errors[:10]  # 只返回前10个错误
    }


@shared_task
def check_device_health():
    """
    检查考勤设备健康状态
    如果设备长时间没有心跳，标记为离线
    """
    from .attendance_device import AttendanceDevice
    
    # 超过30分钟没有心跳的设备标记为离线
    threshold = timezone.now() - timedelta(minutes=30)
    
    offline_count = AttendanceDevice.objects.filter(
        is_deleted=False,
        status='ONLINE',
        last_heartbeat__lt=threshold
    ).update(status='OFFLINE')
    
    # 超过24小时没有心跳的设备标记为异常
    error_threshold = timezone.now() - timedelta(hours=24)
    error_count = AttendanceDevice.objects.filter(
        is_deleted=False,
        status='OFFLINE',
        last_heartbeat__lt=error_threshold
    ).update(status='ERROR')
    
    logger.info(f"Device health check: {offline_count} marked offline, {error_count} marked error")
    return {
        'offline': offline_count,
        'error': error_count
    }


@shared_task
def generate_daily_attendance_report():
    """
    生成每日考勤报表
    """
    from django.db.models import Count, Q
    from apps.accounts.attendance import AttendanceRecord
    from apps.accounts.models import User
    
    yesterday = (timezone.now() - timedelta(days=1)).date()
    
    # 统计昨天的考勤情况
    total_employees = User.objects.filter(is_active=True).count()
    
    records = AttendanceRecord.objects.filter(date=yesterday)
    
    stats = {
        'date': yesterday.isoformat(),
        'total_employees': total_employees,
        'checked_in': records.filter(check_in_time__isnull=False).count(),
        'checked_out': records.filter(check_out_time__isnull=False).count(),
        'late': records.filter(status='LATE').count(),
        'early_leave': records.filter(status='EARLY_LEAVE').count(),
        'absent': records.filter(status='ABSENT').count(),
        'on_leave': records.filter(status='ON_LEAVE').count(),
    }
    
    stats['attendance_rate'] = round(
        stats['checked_in'] / total_employees * 100, 2
    ) if total_employees > 0 else 0
    
    logger.info(f"Daily attendance report for {yesterday}: {stats}")
    
    # TODO: 可以发送邮件通知或保存到报表表
    
    return stats


@shared_task
def cleanup_old_device_logs(days=90):
    """
    清理旧的设备同步日志
    保留最近N天的数据
    """
    from .attendance_device import DeviceSyncLog, DeviceAttendanceLog
    
    threshold = timezone.now() - timedelta(days=days)
    
    # 删除旧的同步日志
    sync_deleted = DeviceSyncLog.objects.filter(
        start_time__lt=threshold
    ).delete()[0]
    
    # 软删除已处理的旧打卡记录（保留原始数据用于审计）
    log_deleted = DeviceAttendanceLog.objects.filter(
        punch_time__lt=threshold,
        is_processed=True
    ).update(is_deleted=True, deleted_at=timezone.now())
    
    logger.info(f"Cleanup: {sync_deleted} sync logs deleted, {log_deleted} attendance logs archived")
    return {
        'sync_logs_deleted': sync_deleted,
        'attendance_logs_archived': log_deleted
    }
