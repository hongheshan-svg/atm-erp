"""组件绑定「一子一父」不变量测试。

追溯树依赖两条不变量：**一个子件在任一时刻只挂在一个父件下**、**绑定关系无环**。
任何一条被打破，向上/向下遍历都会给出错误的追溯结果甚至无限递归。

此前这两条校验只写在 SerialNumberViewSet.bind_component 里，而 ComponentBindingViewSet
是标准 ModelViewSet——直接 POST /component-bindings/ 就能绕开全部校验。本测试覆盖：
  (a) 序列化器层校验（自绑 / 重复绑定 / 环路），确保直连 create 路径同样受控；
  (b) 数据库条件唯一索引，兜住「校验通过后才发生」的并发窗口；
  (c) 解绑后可重新绑定——约束只作用于 is_active=True 的行。
"""

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.masterdata.models import Item
from apps.production.sn_traceability import ComponentBinding, ComponentBindingSerializer, SerialNumber


class ComponentBindingInvariantTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='cb_op', employee_id='CB1')
        self.item = Item.objects.create(sku='SKU-CB', name='绑定测试物料')
        self.sn = {
            key: SerialNumber.objects.create(serial_number=f'SN-CB-{key}', item=self.item) for key in ('a', 'b', 'c')
        }

    def _bind(self, parent, child, **kwargs):
        return ComponentBinding.objects.create(
            parent_sn=parent, child_sn=child, binding_time=timezone.now(), operator=self.user, **kwargs
        )

    def _serializer_errors(self, parent, child):
        serializer = ComponentBindingSerializer(
            data={
                'parent_sn': parent.pk,
                'child_sn': child.pk,
                'binding_time': timezone.now().isoformat(),
                'operator': self.user.pk,
            }
        )
        self.assertFalse(serializer.is_valid(), '该组合本应被序列化器拒绝')
        return serializer.errors

    # ---------- (a) 序列化器层：直连 create 路径 ----------
    def test_serializer_rejects_self_binding(self):
        errors = self._serializer_errors(self.sn['a'], self.sn['a'])
        self.assertIn('自身', str(errors))

    def test_serializer_rejects_second_parent(self):
        self._bind(self.sn['a'], self.sn['b'])
        errors = self._serializer_errors(self.sn['c'], self.sn['b'])
        self.assertIn('已绑定到父组件', str(errors))

    def test_serializer_rejects_cycle(self):
        # a -> b -> c，再把 a 挂到 c 下就成环
        self._bind(self.sn['a'], self.sn['b'])
        self._bind(self.sn['b'], self.sn['c'])
        errors = self._serializer_errors(self.sn['c'], self.sn['a'])
        self.assertIn('环路', str(errors))

    def test_serializer_accepts_valid_binding(self):
        self._bind(self.sn['a'], self.sn['b'])
        serializer = ComponentBindingSerializer(
            data={
                'parent_sn': self.sn['b'].pk,
                'child_sn': self.sn['c'].pk,
                'binding_time': timezone.now().isoformat(),
                'operator': self.user.pk,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    # ---------- (b) 数据库约束：并发窗口兜底 ----------
    def test_db_constraint_blocks_duplicate_active_binding(self):
        self._bind(self.sn['a'], self.sn['b'])
        # 绕过序列化器直接写库，模拟两个并发请求都通过了应用层校验的情形
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._bind(self.sn['c'], self.sn['b'])

    # ---------- (c) 解绑后可重新绑定 ----------
    def test_unbound_row_frees_the_child_sn(self):
        first = self._bind(self.sn['a'], self.sn['b'])
        first.is_active = False
        first.unbinding_time = timezone.now()
        first.save(update_fields=['is_active', 'unbinding_time'])

        second = self._bind(self.sn['c'], self.sn['b'])
        self.assertTrue(second.is_active)
        self.assertEqual(ComponentBinding.objects.filter(child_sn=self.sn['b'], is_active=True).count(), 1)

    # ---------- 祖先遍历自带环路保护 ----------
    def test_active_ancestor_ids_walks_up_the_chain(self):
        self._bind(self.sn['a'], self.sn['b'])
        self._bind(self.sn['b'], self.sn['c'])
        self.assertEqual(
            ComponentBinding.active_ancestor_ids(self.sn['c'].pk),
            {self.sn['b'].pk, self.sn['a'].pk},
        )
        self.assertEqual(ComponentBinding.active_ancestor_ids(self.sn['a'].pk), set())
