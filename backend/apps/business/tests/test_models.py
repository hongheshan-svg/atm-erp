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
