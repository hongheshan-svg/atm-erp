"""把存量已批准(未支付)的员工费用报销回填到统一待付款项台账。

收口 post_save 信号(register_expense_payable)后新审批通过的报销单会自动登记;
本命令用于登记信号接入前已处于 APPROVED 的存量记录,以及信号因异常失败时的
人工兜底(见 apps.finance.signals._safe_sync_payable)。PAID/REJECTED/DRAFT/
SUBMITTED 均跳过——PAID 已结清无需核销,其余状态尚未到达"确认应付"事实。

幂等:register_payable 走 update_or_create,重复运行不会重复建项。
"""

from django.core.management.base import BaseCommand

from apps.finance.models import Expense
from apps.finance.payable_adapters import register_payable


class Command(BaseCommand):
    help = '把已批准未支付的员工费用报销(Expense status=APPROVED)回填到待付款项台账'

    def handle(self, *args, **options):
        qs = Expense.objects.filter(status='APPROVED')
        count = 0
        for expense in qs:
            register_payable(expense, 'expense')
            count += 1
        self.stdout.write(self.style.SUCCESS(f'回填 {count} 条已批准报销单到台账'))
