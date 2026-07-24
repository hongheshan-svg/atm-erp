"""把存量未结清的应付账款回填到统一待付款项台账。

一期只回填应付账款(AP);报销/合同付款的存量按需在各自模块审批点重新登记。
幂等:register_payable 走 update_or_create,重复运行只更新不重复建项。
"""

from django.core.management.base import BaseCommand

from apps.finance.models import AccountPayable
from apps.finance.payable_adapters import register_payable


class Command(BaseCommand):
    help = '把未结清(PENDING/PARTIAL/OVERDUE)的应付账款回填到待付款项台账'

    def handle(self, *args, **options):
        qs = AccountPayable.objects.filter(status__in=['PENDING', 'PARTIAL', 'OVERDUE'])
        count = 0
        for ap in qs:
            item = register_payable(ap, 'ap')
            item.amount_paid = ap.amount_paid
            item.recalc_status()
            item.save(update_fields=['amount_paid', 'status', 'updated_at'])
            count += 1
        self.stdout.write(self.style.SUCCESS(f'回填 {count} 条应付账款到台账'))
