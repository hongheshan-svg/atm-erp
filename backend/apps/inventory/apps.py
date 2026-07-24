from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventory'
    verbose_name = '库存管理'

    def ready(self):
        # 库存模型分散在多个非 models.py 模块且部分仅被惰性 import;在 app 就绪时显式加载,
        # 确保稳定注册(尤其 cost_accounting.InventoryCostConfig —— StockMove 完成时会查询它,
        # 未注册则该表缺失导致任何库存移动出错),不受各处 import 顺序影响。
        from . import (  # noqa: F401
            batch_models,
            cost_accounting,
            data_accuracy,
            material_models,
            mrp,
            spare_parts,
            spare_parts_prediction,
            stock_alert,
        )
