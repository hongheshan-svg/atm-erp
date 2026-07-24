"""把存量已审批(未付)的合同付款回填到统一待付款项台账。

收口 pay() 后新审批的合同付款经 post_save 信号自动登记;本命令用于登记
收口前已处于 APPROVED 的存量记录。历史 PAID 记录跳过(已付、无需核销)。
幂等:register_payable 走 update_or_create。
"""

from django.core.management.base import BaseCommand

from apps.finance.payable_adapters import register_payable
from apps.purchase.contract_execution import PaymentRecord


class Command(BaseCommand):
    help = '把已审批未付的合同付款(PaymentRecord status=APPROVED)回填到待付款项台账'

    def handle(self, *args, **options):
        qs = PaymentRecord.objects.filter(status='APPROVED')
        count = 0
        for pr in qs:
            register_payable(pr, 'contract_payment')
            count += 1
        self.stdout.write(self.style.SUCCESS(f'回填 {count} 条合同付款到台账'))
