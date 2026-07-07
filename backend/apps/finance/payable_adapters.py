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
    # 不变量:此处 defaults 绝不能含核销进度字段(status / amount_paid)。register_payable
    # 是可重入的——合同付款经 post_save 信号在每次 save(APPROVED) 时重登记,反核销
    # (unsettle→write_back 把源单据从 PAID 退回 APPROVED→save)也会再次触发它。因
    # to_payable() 只返回单据静态属性(收款方/应付额/日期等)、从不返回 status/amount_paid,
    # update_or_create 的重复调用只刷新静态字段、不会覆盖已由核销/反核销正确维护的核销进度。
    # 若将来往任何 to_payable() 里加 status/amount_paid,会在反核销场景悄悄复位台账,务必避免。
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
        elif obj.status == 'PAID':
            # 反核销:台账退回未结清,报销单从 PAID 退回 APPROVED、清报销日期。
            obj.status = 'APPROVED'
            obj.reimbursement_date = None
            obj.save(update_fields=['status', 'reimbursement_date', 'updated_at'])


@register_source
class ContractPaymentSource(PayableSource):
    source_type = 'contract_payment'
    category = '合同付款'

    def to_payable(self, obj) -> dict:
        contract = obj.execution.contract
        supplier = getattr(contract, 'supplier', None)
        return {
            'source_no': obj.payment_no,
            'payee_name': supplier.name if supplier else '',
            'supplier_id': supplier.id if supplier else None,
            'amount_due': obj.amount,
            'currency_id': None,
            'due_date': obj.planned_date,
            'project_id': None,
        }

    def write_back(self, obj, item) -> None:
        from decimal import Decimal
        from django.db.models import Sum
        from django.utils import timezone
        if item.status == item.STATUS_PAID and obj.status != 'PAID':
            obj.status = 'PAID'
            if not obj.actual_date:
                obj.actual_date = timezone.now().date()
            obj.save(update_fields=['status', 'actual_date', 'updated_at'])
        elif item.status != item.STATUS_PAID and obj.status == 'PAID':
            # 反核销:合同付款记录从 PAID 退回 APPROVED、清实际付款日期。
            obj.status = 'APPROVED'
            obj.actual_date = None
            obj.save(update_fields=['status', 'actual_date', 'updated_at'])
        # execution.paid_amount 按该合同所有 PAID 付款记录重算(幂等,settle/unsettle
        # 双向正确;避免 F() 增量在反核销时无法扣减导致的 paid_amount 永久漂移)。
        execution = obj.execution
        paid = execution.payments.filter(status='PAID').aggregate(s=Sum('amount'))['s'] or Decimal('0')
        type(execution).objects.filter(pk=execution.pk).update(paid_amount=paid)
