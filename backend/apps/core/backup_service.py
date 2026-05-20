"""
数据备份恢复服务
Database Backup and Restore Service
"""
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from celery import shared_task
from django.conf import settings
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# 备份文件存储目录
BACKUP_DIR = getattr(settings, 'BACKUP_DIR', '/app/backups')


class BackupService:
    """数据库备份服务"""

    @staticmethod
    def get_db_config():
        """获取数据库配置"""
        db_settings = settings.DATABASES['default']
        return {
            'host': db_settings.get('HOST', 'localhost'),
            'port': db_settings.get('PORT', '5432'),
            'name': db_settings.get('NAME'),
            'user': db_settings.get('USER'),
            'password': db_settings.get('PASSWORD'),
        }

    @classmethod
    def create_backup(cls, backup_name=None):
        """
        创建数据库备份
        :param backup_name: 自定义备份名称，默认使用时间戳
        :return: 备份文件路径
        """
        # 确保备份目录存在
        Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)

        db_config = cls.get_db_config()

        # 生成备份文件名
        if not backup_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"erp_backup_{timestamp}"

        backup_file = os.path.join(BACKUP_DIR, f"{backup_name}.sql")

        # 设置环境变量
        env = os.environ.copy()
        env['PGPASSWORD'] = db_config['password']

        # 执行pg_dump
        cmd = [
            'pg_dump',
            '-h', db_config['host'],
            '-p', str(db_config['port']),
            '-U', db_config['user'],
            '-d', db_config['name'],
            '-f', backup_file,
            '--no-owner',
            '--no-acl',
        ]

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600  # 1小时超时
            )

            if result.returncode != 0:
                logger.error(f"Backup failed: {result.stderr}")
                raise Exception(f"Backup failed: {result.stderr}")

            # 压缩备份文件
            compressed_file = f"{backup_file}.gz"
            subprocess.run(['gzip', '-f', backup_file], check=True)

            # 获取文件大小
            file_size = os.path.getsize(compressed_file)

            logger.info(f"Backup created: {compressed_file}, size: {file_size} bytes")

            return {
                'file': compressed_file,
                'name': f"{backup_name}.sql.gz",
                'size': file_size,
                'created_at': datetime.now().isoformat()
            }

        except subprocess.TimeoutExpired:
            logger.error("Backup timeout")
            raise Exception("Backup timeout")
        except Exception as e:
            logger.error(f"Backup error: {str(e)}")
            raise

    @classmethod
    def restore_backup(cls, backup_file):
        """
        恢复数据库备份
        :param backup_file: 备份文件路径
        """
        if not os.path.exists(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        db_config = cls.get_db_config()

        # 设置环境变量
        env = os.environ.copy()
        env['PGPASSWORD'] = db_config['password']

        # 如果是压缩文件，先解压
        if backup_file.endswith('.gz'):
            subprocess.run(['gunzip', '-k', '-f', backup_file], check=True)
            backup_file = backup_file[:-3]  # 去掉.gz

        # 执行psql恢复
        cmd = [
            'psql',
            '-h', db_config['host'],
            '-p', str(db_config['port']),
            '-U', db_config['user'],
            '-d', db_config['name'],
            '-f', backup_file,
        ]

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600
            )

            if result.returncode != 0:
                logger.error(f"Restore failed: {result.stderr}")
                raise Exception(f"Restore failed: {result.stderr}")

            logger.info(f"Database restored from: {backup_file}")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Restore timeout")
            raise Exception("Restore timeout")
        except Exception as e:
            logger.error(f"Restore error: {str(e)}")
            raise

    @classmethod
    def list_backups(cls):
        """列出所有备份文件"""
        backups = []

        if not os.path.exists(BACKUP_DIR):
            return backups

        for filename in os.listdir(BACKUP_DIR):
            if filename.endswith('.sql.gz') or filename.endswith('.sql'):
                filepath = os.path.join(BACKUP_DIR, filename)
                stat = os.stat(filepath)
                backups.append({
                    'name': filename,
                    'path': filepath,
                    'size': stat.st_size,
                    'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        # 按时间倒序排列
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        return backups

    @classmethod
    def delete_backup(cls, backup_name):
        """删除备份文件"""
        backup_file = os.path.join(BACKUP_DIR, backup_name)

        if not os.path.exists(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_name}")

        os.remove(backup_file)
        logger.info(f"Backup deleted: {backup_name}")
        return True

    @classmethod
    def cleanup_old_backups(cls, keep_days=30):
        """清理过期备份"""
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted = []

        for backup in cls.list_backups():
            created_at = datetime.fromisoformat(backup['created_at'])
            if created_at < cutoff_date:
                cls.delete_backup(backup['name'])
                deleted.append(backup['name'])

        logger.info(f"Cleaned up {len(deleted)} old backups")
        return deleted


# Celery定时任务
@shared_task
def scheduled_backup():
    """定时备份任务（每天凌晨2点执行）"""
    try:
        result = BackupService.create_backup()
        logger.info(f"Scheduled backup completed: {result['file']}")

        # 清理30天前的备份
        BackupService.cleanup_old_backups(keep_days=30)

        return result
    except Exception as e:
        logger.error(f"Scheduled backup failed: {str(e)}")
        raise


# API视图
class BackupListView(APIView):
    """备份列表API"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        """获取备份列表"""
        backups = BackupService.list_backups()
        return Response({
            'backups': backups,
            'backup_dir': BACKUP_DIR
        })


class BackupCreateView(APIView):
    """创建备份API"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        """创建新备份"""
        backup_name = request.data.get('name')

        try:
            result = BackupService.create_backup(backup_name)
            return Response({
                'message': '备份创建成功',
                'backup': result
            })
        except Exception as e:
            return Response({
                'error': f'备份创建失败: {str(e)}'
            }, status=500)


class BackupRestoreView(APIView):
    """恢复备份API"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        """恢复备份"""
        backup_name = request.data.get('name')

        if not backup_name:
            return Response({'error': '请指定备份文件名'}, status=400)

        backup_file = os.path.join(BACKUP_DIR, backup_name)

        try:
            BackupService.restore_backup(backup_file)
            return Response({'message': '数据恢复成功'})
        except FileNotFoundError:
            return Response({'error': '备份文件不存在'}, status=404)
        except Exception as e:
            return Response({'error': f'恢复失败: {str(e)}'}, status=500)


class BackupDeleteView(APIView):
    """删除备份API"""
    permission_classes = [IsAdminUser]

    def delete(self, request, backup_name):
        """删除备份"""
        try:
            BackupService.delete_backup(backup_name)
            return Response({'message': '备份已删除'})
        except FileNotFoundError:
            return Response({'error': '备份文件不存在'}, status=404)
        except Exception as e:
            return Response({'error': f'删除失败: {str(e)}'}, status=500)


class BackupCleanupView(APIView):
    """清理过期备份API"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        """清理过期备份"""
        keep_days = int(request.data.get('keep_days', 30))

        try:
            deleted = BackupService.cleanup_old_backups(keep_days)
            return Response({
                'message': f'已清理 {len(deleted)} 个过期备份',
                'deleted': deleted
            })
        except Exception as e:
            return Response({'error': f'清理失败: {str(e)}'}, status=500)
