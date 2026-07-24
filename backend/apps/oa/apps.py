from django.apps import AppConfig


class OaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.oa'
    verbose_name = 'OA协同办公'

    def ready(self):
        """导入信号处理器"""
        from . import signals  # noqa
