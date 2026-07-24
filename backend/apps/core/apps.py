from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core'

    def ready(self):
        # code_rule_models 定义的 CodeRule 等模型仅被各处惰性 import,不随 models.py 自动加载;
        # 在 app 就绪时显式导入,确保模型稳定注册(编号生成依赖它),不受 admin/url 导入顺序影响。
        from apps.core import code_rule_models  # noqa: F401
