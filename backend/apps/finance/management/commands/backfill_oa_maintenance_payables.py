"""把存量应付的资产维护/车辆维护记录回填到统一待付款项台账。

1. AssetMaintenance(资产维修/保养) - 仅回填 status=COMPLETED 且 cost>0 的记录。
   PENDING/IN_PROGRESS 尚未产生确定费用,不回填;CANCELLED 已作废;COMPLETED 但
   cost=0(保养/自行处理无实际支出)不登记空台账项——与信号口径一致(见
   apps.oa.signals.register_asset_maintenance_payable)。

2. VehicleMaintenance(车辆维护记录) - 无状态机,回填全部 cost>0 的记录——与信号
   口径一致(见 apps.oa.signals.register_vehicle_maintenance_payable)。

幂等: register_payable 走 update_or_create,重复运行只更新不重复建项。
"""

from django.core.management.base import BaseCommand

from apps.finance.payable_adapters import register_payable
from apps.oa.asset import AssetMaintenance
from apps.oa.vehicle import VehicleMaintenance


class Command(BaseCommand):
    help = '把存量应付的资产维护(COMPLETED且cost>0)/车辆维护(cost>0)记录回填到待付款项台账'

    def handle(self, *args, **options):
        count = 0

        asset_qs = AssetMaintenance.objects.filter(status='COMPLETED', cost__gt=0)
        for maintenance in asset_qs:
            register_payable(maintenance, 'asset_maintenance')
            count += 1
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ 回填 {asset_qs.count()} 条资产维护(COMPLETED、cost>0)到台账')
        )

        vehicle_qs = VehicleMaintenance.objects.filter(cost__gt=0)
        for maintenance in vehicle_qs:
            register_payable(maintenance, 'vehicle_maintenance')
            count += 1
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ 回填 {vehicle_qs.count()} 条车辆维护(cost>0)到台账')
        )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ 总计回填 {count} 条OA维护单据到台账')
        )
