"""把存量已归还结算(RETURNED)且行程费合计 > 0 的用车申请回填到统一待付款项台账。

背景:VehicleRequest 归还结算(VehicleRequestViewSet.return_vehicle())在本次改动前
无任何台账适配器,行程费(油费/过路/停车/其他)只落在用车单据自身,从未进入应付/核销
流程。`register_vehicle_request_payable` 信号(apps.oa.signals)覆盖新增数据,本命令
补齐历史存量。

口径:仅回填 status='RETURNED' 且 total_cost(四项费用之和) > 0 的申请——纯公务用车
未产生费用不构成应付事实,不回填,避免污染核销候选(与信号口径一致)。

幂等: register_payable 走 update_or_create,重复运行只更新不重复建项。
"""

from django.core.management.base import BaseCommand

from apps.finance.payable_adapters import register_payable
from apps.oa.vehicle import VehicleRequest


class Command(BaseCommand):
    help = '把存量已归还结算且行程费>0的用车申请回填到待付款项台账'

    def handle(self, *args, **options):
        count = 0
        qs = VehicleRequest.objects.filter(status='RETURNED', is_deleted=False)
        for req in qs:
            if req.total_cost and req.total_cost > 0:
                register_payable(req, 'vehicle_request')
                count += 1

        self.stdout.write(
            self.style.SUCCESS(f'✓ 回填 {count} 条已归还结算(RETURNED、行程费>0)的用车申请到台账')
        )
