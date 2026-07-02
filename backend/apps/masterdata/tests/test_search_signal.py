"""未部署 Elasticsearch 时,创建被 ES Document 索引的主数据不应报错。

新架构(4 服务)不部署 ES,ELASTICSEARCH_HOST 为空。但 Customer/Supplier/Item
等注册了 ES Document,默认的 RealTimeSignalProcessor 会在 post_save 同步索引;
连不上 ES 时抛 TypeError,导致创建/编辑主数据 API 直接 500。

这些用例**不** override ELASTICSEARCH_DSL_AUTOSYNC,依赖 settings 的真实行为:
未配置 ES 时应自动禁用实时索引,使创建不报错。
"""
from django.test import TestCase

from apps.masterdata.models import Customer, Supplier


class CreateWithoutElasticsearchTest(TestCase):
    def test_create_customer_when_es_unavailable(self):
        customer = Customer.objects.create(code='C-NOES-01', name='无ES建档客户')
        self.assertIsNotNone(customer.pk)

    def test_create_supplier_when_es_unavailable(self):
        supplier = Supplier.objects.create(code='S-NOES-01', name='无ES建档供应商')
        self.assertIsNotNone(supplier.pk)
