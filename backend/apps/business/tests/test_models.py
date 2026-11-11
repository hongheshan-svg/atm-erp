from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.business.models import BOMLine, Entry, Item, Partner, Payment, Project, PurchaseLine, PurchaseOrder, Stock
from apps.core.permissions import projects_for, require_project


class ModelTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username='manager', role='manager')
        self.member = User.objects.create_user(username='member', role='member')
        self.partner = Partner.objects.create(code='PTY1', name='伙伴', kind='both')
        self.project = Project.objects.create(
            code='PRJ1', name='自动化设备', customer=self.partner, manager=self.manager
        )
        self.item = Item.objects.create(code='MAT1', name='电机')

    def test_member_scope_is_enforced(self):
        self.assertFalse(projects_for(self.member, Project.objects.all()).exists())
        with self.assertRaises(PermissionDenied):
            require_project(self.member, self.project)
        self.project.members.add(self.member)
        self.assertEqual(list(projects_for(self.member, Project.objects.all())), [self.project])
        require_project(self.member, self.project)

    def test_soft_delete_hides_record_but_keeps_history(self):
        self.item.soft_delete(self.manager)
        self.assertFalse(Item.objects.filter(pk=self.item.pk).exists())
        self.assertTrue(Item.all_objects.filter(pk=self.item.pk).exists())
        with self.assertRaises(ValidationError):
            self.item.delete()
        with self.assertRaises(ValidationError):
            Item.all_objects.filter(pk=self.item.pk).delete()

    def test_ledger_cannot_be_deleted(self):
        entry = Entry.objects.create(
            project=self.project, kind='receivable', title='合同款', amount=1000, due_date=timezone.localdate()
        )
        payment = Payment.objects.create(entry=entry, amount=100, date=timezone.localdate(), reason='收款')
        for obj in (entry, payment):
            with self.assertRaises(ValidationError):
                obj.soft_delete(self.manager)
            with self.assertRaises(ValidationError):
                obj.delete()

    def test_database_rejects_negative_stock_and_empty_stock_value(self):
        for qty, value in [(-1, 0), (0, 1), (1, -1)]:
            with self.subTest(qty=qty, value=value), self.assertRaises(IntegrityError), transaction.atomic():
                Stock.objects.create(item=self.item, quantity=qty, value=value)

    def test_database_rejects_overreceipt_and_overreturn(self):
        purchase = PurchaseOrder.objects.create(
            code='PO1', project=self.project, supplier=self.partner, due_date=timezone.localdate()
        )
        for received, cancelled, returned in [(11, 0, 0), (6, 5, 0), (2, 0, 3), (-1, 0, 0)]:
            with (
                self.subTest(received=received, cancelled=cancelled, returned=returned),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                PurchaseLine.objects.create(
                    purchase=purchase,
                    item=self.item,
                    quantity=10,
                    received_quantity=received,
                    cancelled_quantity=cancelled,
                    returned_quantity=returned,
                )

    def test_bom_has_one_live_line_per_project_item(self):
        line = BOMLine.objects.create(project=self.project, item=self.item, quantity=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BOMLine.objects.create(project=self.project, item=self.item, quantity=2)
        line.soft_delete(self.manager)
        new = BOMLine.objects.create(project=self.project, item=self.item, quantity=Decimal('2.001'))
        self.assertNotEqual(line.pk, new.pk)
        self.assertEqual(BOMLine.objects.count(), 1)

    def test_credit_cannot_exceed_original_entry(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Entry.objects.create(
                project=self.project,
                kind='payable',
                title='采购款',
                amount=100,
                credit_amount=101,
                due_date=timezone.localdate(),
            )

    def test_posted_payment_cannot_be_overwritten_or_hidden(self):
        entry = Entry.objects.create(
            project=self.project, kind='receivable', title='合同款', amount=1000, due_date=timezone.localdate()
        )
        payment = Payment.objects.create(entry=entry, amount=100, date=timezone.localdate(), reason='收款')
        payment.amount = 200
        with self.assertRaises(ValidationError):
            payment.save()
        with self.assertRaises(ValidationError):
            Payment.objects.filter(pk=payment.pk).update(amount=200)
        with self.assertRaises(ValidationError):
            Payment.all_objects.filter(pk=payment.pk).update(is_deleted=True)
        with self.assertRaises(ValidationError):
            Payment.objects.bulk_update([payment], ['amount'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment(id=payment.pk, entry=entry, amount=200, date=timezone.localdate(), reason='覆盖').save()
        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal('100.00'))


class FullCleanQueryTests(TestCase):
    """common.save → full_clean：查询更少，校验规则、错误内容与顺序与 Django 原逻辑一致。"""

    def setUp(self):
        self.manager = User.objects.create_user(username='manager', role='manager')
        self.partner = Partner.objects.create(code='PTY1', name='伙伴', kind='both')
        self.project = Project.objects.create(
            code='PRJ1', name='自动化设备', customer=self.partner, manager=self.manager
        )
        self.item = Item.objects.create(code='MAT1', name='电机')
        self.purchase = PurchaseOrder.objects.create(
            code='PO1', project=self.project, supplier=self.partner, due_date=timezone.localdate()
        )

    def errors(self, method, *args, **kwargs):
        try:
            method(*args, **kwargs)
        except ValidationError as exc:
            return {key: [(error.code, list(error)[0]) for error in errors] for key, errors in exc.error_dict.items()}
        return {}

    def line(self, **values):
        return PurchaseLine(
            purchase=self.purchase,
            item=self.item,
            created_by=self.manager,
            updated_by=self.manager,
            **{'quantity': 10, **values},
        )

    def test_check_constraints_run_in_one_query_with_identical_errors(self):
        from django.db import connection, models
        from django.test.utils import CaptureQueriesContext

        cases = [
            {},
            {'received_quantity': 11, 'returned_quantity': 12, 'unit_price': -1, 'pending_quantity': -1},
            {'quantity': 0, 'cancelled_quantity': -1},
        ]
        for values in cases:
            for exclude in (None, {'received_quantity'}):
                with self.subTest(values=values, exclude=exclude):
                    line = self.line(**values)
                    with CaptureQueriesContext(connection) as stock_queries:
                        expected = self.errors(models.Model.validate_constraints, line, exclude=exclude)
                    with CaptureQueriesContext(connection) as queries:
                        actual = self.errors(line.validate_constraints, exclude=exclude)
                    self.assertEqual(actual, expected)
                    if exclude is None:
                        checks = [q for q in queries.captured_queries if '_check' in q['sql']]
                        self.assertEqual(len(checks), 1)
                        self.assertEqual(len([q for q in stock_queries if '_check' in q['sql']]), 5)
        # 超收同时违反「待检上限」和「不得超收」两条，按约束声明顺序给出。
        messages = [text for _, text in self.errors(self.line(received_quantity=11).validate_constraints)['__all__']]
        self.assertEqual(len(messages), 2)
        self.assertIn('lean_purchase_pending_limit', messages[0])
        self.assertIn('lean_purchase_no_overreceive', messages[1])

    def test_loaded_relations_skip_existence_queries_only(self):
        from django.db import connection, models
        from django.test.utils import CaptureQueriesContext

        line = self.line()
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.errors(line.clean_fields), {})
        self.assertEqual(len(queries), 0)
        # 只给编号、未加载关联行时照常查存在性；不存在的编号仍是 Django 原错误。
        unloaded = PurchaseLine(purchase_id=self.purchase.pk, item_id=999999, quantity=10)
        with CaptureQueriesContext(connection) as queries:
            actual = self.errors(unloaded.clean_fields)
        self.assertEqual(len(queries), 2)
        self.assertEqual(actual, self.errors(models.Model.clean_fields, unloaded))
        self.assertEqual(list(actual), ['item'])
        # 已加载对象之后又把编号改成别的值，缓存失效，必须重新校验。
        changed = self.line()
        changed.item_id = 999999
        self.assertEqual(self.errors(changed.clean_fields), self.errors(models.Model.clean_fields, changed))
        self.assertIn('item', self.errors(changed.clean_fields))

    def test_business_save_query_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.business.services.common import save

        with CaptureQueriesContext(connection) as queries:
            line = save(self.line(), self.manager)
        # 外键都已加载、5 条 CHECK 合并为一次（含保存点共 3 条语句），加 INSERT；原逻辑为 20 条。
        self.assertEqual(len(queries), 4, [q['sql'] for q in queries.captured_queries])
        fresh = PurchaseLine.objects.get(pk=line.pk)
        with CaptureQueriesContext(connection) as queries:
            save(fresh, self.manager)
        # 更新时创建人沿用原值、经办人已加载；只查未加载的采购单和物料各一次。
        tables = [q['sql'] for q in queries.captured_queries if q['sql'].startswith('SELECT 1 AS "a"')]
        self.assertEqual(len(tables), 2, tables)
        self.assertFalse(any('lean_user' in sql for sql in tables))
