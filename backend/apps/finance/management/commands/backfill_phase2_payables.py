"""把存量已应付(未付)的二期来源单据回填到统一待付款项台账。

R2判断(含两期协调):
1. OutsourceOrder (委外加工) - 不回填。OutsourceOrderViewSet.confirm() 内联创建了
   AccountPayable,外协应付已随 AP 经 backfill_payables 回填,无需重复回填。

2. PaymentRequest (付款申请) - 仅回填 ap__isnull=True 的独立申请(status=APPROVED)。
   大多数 PaymentRequest 关联既存 AP(付款申请→针对某 AP)，该 AP 已被 backfill_payables 覆盖。
   只有独立申请(ap 为空)才需单独回填到统一台账。

3. TaxDeclaration (缴税) - 正常回填。status = DECLARED(已申报、未缴款)。
   TaxDeclaration 独立于 AP 体系，其付款事实由统一台账维护。

4. SharedExpense (公共费用) - 正常回填。status = ALLOCATED(已分摊、待支付)。
   SharedExpense 独立于 AP 体系，其付款事实由统一台账维护。

幂等: register_payable 走 update_or_create,重复运行只更新不重复建项。
"""

from django.core.management.base import BaseCommand

from apps.finance.payable_adapters import register_payable
from apps.finance.models import SharedExpense, PaymentRequest
from apps.finance.tax_management import TaxDeclaration


class Command(BaseCommand):
    help = '把存量已应付(未付)的二期来源单据回填到待付款项台账(仅tax/shared_expense/独立payment_request)'

    def handle(self, *args, **options):
        count = 0

        # 1. 公共费用：已分摊的公共费用(独立于AP，直接回填)
        shared_expense_qs = SharedExpense.objects.filter(status='ALLOCATED')
        for expense in shared_expense_qs:
            register_payable(expense, 'shared_expense')
            count += 1
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ 回填 {shared_expense_qs.count()} 条公共费用(ALLOCATED)到台账')
        )

        # 2. 缴税：已申报未缴款的税务申报(独立于AP，直接回填)
        tax_qs = TaxDeclaration.objects.filter(status='DECLARED')
        for tax in tax_qs:
            register_payable(tax, 'tax')
            count += 1
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ 回填 {tax_qs.count()} 条税务申报(DECLARED)到台账')
        )

        # 3. 付款申请：仅回填独立申请(ap 为空、status=APPROVED)
        # 关联AP的请求已随AP被 backfill_payables 覆盖，无需重复回填
        payment_request_qs = PaymentRequest.objects.filter(status='APPROVED', ap__isnull=True)
        for req in payment_request_qs:
            register_payable(req, 'payment_request')
            count += 1
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ 回填 {payment_request_qs.count()} 条独立付款申请(APPROVED、ap=null)到台账')
        )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ 总计回填 {count} 条二期来源应付单据到台账')
        )
        self.stdout.write(
            self.style.WARNING(
                '⊘ 说明:委外订单(OutsourceOrder)不回填。其应付已随内联创建的AP'
                '通过 backfill_payables 回填。'
            )
        )
