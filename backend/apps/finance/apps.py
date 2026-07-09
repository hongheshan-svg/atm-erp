from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = '财务管理'

    def ready(self):
        """导入信号处理器"""
        from . import signals  # noqa
        # 回款计划模型定义在独立模块且仅被惰性 import,显式加载确保稳定注册
        from . import collection_models  # noqa: F401
