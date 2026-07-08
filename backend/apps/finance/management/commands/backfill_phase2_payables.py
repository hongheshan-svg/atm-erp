"""把存量已应付(未付)的二期来源单据回填到统一待付款项台账。

来源判断(含 G5 委外修复后的订正):
1. OutsourceOrder (委外加工) - 回填 status in CONFIRMED/PROCESSING/PARTIAL/COMPLETED
   的委外单为 source_type='outsource'。历史上 confirm() 试图内联建 AccountPayable,
   但 AccountPayable 无 notes 字段致每次 500、从未成功建过 AP;现 confirm()/cancel()
   已改为直接登记/作废 outsource 台账项(见 outsource_views.py 与 OutsourcePayableSource),
   故委外应付以 'outsource' 为唯一来源、需在此回填存量已确认单。

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
from apps.purchase.outsource_models import OutsourceOrder


class Command(BaseCommand):
    help = '把存量已应付(未付)的二期来源单据回填到待付款项台账(仅tax/shared_expense/独立payment_request)'

    def handle(self, *args, **options):
        count = 0

        # 0. 委外加工：已确认(且未取消)的委外单,以 source_type='outsource' 回填
        outsource_qs = OutsourceOrder.objects.filter(
            status__in=['CONFIRMED', 'PROCESSING', 'PARTIAL', 'COMPLETED']
        )
        for order in outsource_qs:
            register_payable(order, 'outsource')
            count += 1
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ 回填 {outsource_qs.count()} 条委外加工(已确认)到台账')
        )

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
