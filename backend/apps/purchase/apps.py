from django.apps import AppConfig


class PurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.purchase'
    verbose_name = '采购管理'
    
    def ready(self):
        """导入信号处理器"""
        from . import signals  # noqa

