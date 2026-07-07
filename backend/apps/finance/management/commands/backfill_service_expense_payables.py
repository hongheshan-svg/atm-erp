"""把存量已批准(APPROVED)的现场服务费报销回填到统一待付款项台账。

收口后新审批通过的 ServiceExpense 经 post_save 信号(apps.projects.signals)自动
登记;本命令用于登记收口前已处于 APPROVED 的存量记录。PENDING/REJECTED 不回填
(前者尚未形成应付事实,后者已被拒绝)。
幂等:register_payable 走 update_or_create,重复运行只更新不重复建项。
"""

from django.core.management.base import BaseCommand

from apps.finance.payable_adapters import register_payable
from apps.projects.field_service import ServiceExpense


class Command(BaseCommand):
    help = '把已批准(APPROVED)的现场服务费报销回填到待付款项台账'

    def handle(self, *args, **options):
        qs = ServiceExpense.objects.filter(status='APPROVED')
        count = 0
        for expense in qs:
            register_payable(expense, 'service_expense')
            count += 1
        self.stdout.write(self.style.SUCCESS(f'回填 {count} 条现场服务费报销到台账'))
