from apps.finance.payable_models import PayableItem

PAYABLE_SOURCES = {}


class PayableSource:
    """来源适配器基类。子类设 source_type / category,并实现 to_payable / write_back。"""
    source_type = ''
    category = ''

    def to_payable(self, obj) -> dict:
        """返回 dict:source_no, payee_name, supplier_id, amount_due, currency_id, due_date, project_id"""
        raise NotImplementedError

    def write_back(self, obj, item: PayableItem) -> None:
        """据台账项 item(amount_paid/status)回写源单据。"""
        raise NotImplementedError


def register_source(adapter_cls):
    PAYABLE_SOURCES[adapter_cls.source_type] = adapter_cls()
    return adapter_cls


def register_payable(obj, source_type: str) -> PayableItem:
    adapter = PAYABLE_SOURCES[source_type]
    data = adapter.to_payable(obj)
    defaults = {'category': adapter.category, **data}
    item, _ = PayableItem.objects.update_or_create(
        source_type=source_type, source_id=obj.pk, defaults=defaults,
    )
    return item


def cancel_payable(obj, source_type: str) -> None:
    item = PayableItem.objects.filter(source_type=source_type, source_id=obj.pk).first()
    if item and item.amount_paid == 0:
        item.status = PayableItem.STATUS_CANCELLED
        item.save(update_fields=['status', 'updated_at'])


@register_source
class APPayableSource(PayableSource):
    source_type = 'ap'
    category = '采购'

    def to_payable(self, obj) -> dict:
        return {
            'source_no': obj.ap_no,
            'payee_name': obj.supplier.name if obj.supplier_id else '',
            'supplier_id': obj.supplier_id,
            'amount_due': obj.amount_due,
            'currency_id': obj.currency_id,
            'due_date': obj.due_date,
            'project_id': obj.project_id,
        }

    def write_back(self, obj, item) -> None:
        obj.amount_paid = item.amount_paid
        obj.save()  # AccountPayable.save() 自动算 status


@register_source
class ExpensePayableSource(PayableSource):
    source_type = 'expense'
    category = '报销'

    def to_payable(self, obj) -> dict:
        # Expense 无供应商;payee_name 用申请人姓名。
        # apps.accounts.models.User 无 real_name 字段,真实姓名由 get_full_name()
        # 提供(拼接 last_name+first_name),该方法自身在姓名为空时已回退到 username。
        payee_name = obj.user.get_full_name() if obj.user_id else ''
        return {
            'source_no': obj.expense_no,
            'payee_name': payee_name,
            'supplier_id': None,
            'amount_due': obj.amount,
            'currency_id': obj.currency_id,
            'due_date': obj.expense_date,
            'project_id': obj.project_id,
        }

    def write_back(self, obj, item) -> None:
        from django.utils import timezone
        if item.status == item.STATUS_PAID:
            obj.status = 'PAID'
            if not obj.reimbursement_date:
                obj.reimbursement_date = timezone.now().date()
            obj.save(update_fields=['status', 'reimbursement_date', 'updated_at'])
