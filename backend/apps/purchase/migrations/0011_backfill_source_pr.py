"""尽力回填存量采购订单的 source_pr。

0009 之前 PR->PO 转换不留任何直接关联,历史 PO 无从反查来源申请。
唯一可用的间接线索是 ProjectBOM 上同时挂着 purchase_request 与 purchase_order
两个外键(convert_to_po 会给走 BOM 的行写 purchase_order)。

覆盖范围有限,这是数据本身的缺失而非本迁移的取舍:
  - 手工创建、未经 BOM 的采购申请转出的 PO 无法回填,source_pr 保持 NULL;
  - 一个 PO 若经 BOM 关联到多个不同 PR,判定为有歧义,跳过而不猜测。
前端对 NULL 显示 '-',不会因此报错。
"""

from collections import defaultdict

from django.db import migrations


def backfill(apps, schema_editor):
    ProjectBOM = apps.get_model('projects', 'ProjectBOM')
    PurchaseOrder = apps.get_model('purchase', 'PurchaseOrder')

    # 收集每个 PO 经 BOM 关联到的 PR 集合
    po_to_prs = defaultdict(set)
    rows = ProjectBOM.objects.filter(
        purchase_order__isnull=False,
        purchase_request__isnull=False,
    ).values_list('purchase_order_id', 'purchase_request_id')
    for po_id, pr_id in rows.iterator():
        po_to_prs[po_id].add(pr_id)

    # 只回填唯一对应的,歧义的跳过
    unambiguous = {po_id: prs.pop() for po_id, prs in po_to_prs.items() if len(prs) == 1}
    if not unambiguous:
        return

    to_update = []
    for po in PurchaseOrder.objects.filter(id__in=unambiguous.keys(), source_pr__isnull=True).iterator():
        po.source_pr_id = unambiguous[po.id]
        to_update.append(po)
        if len(to_update) >= 2000:
            PurchaseOrder.objects.bulk_update(to_update, ['source_pr'])
            to_update = []
    if to_update:
        PurchaseOrder.objects.bulk_update(to_update, ['source_pr'])


def noop_reverse(apps, schema_editor):
    """回滚不清空:0009 的 RemoveField 会连同数据一起去掉。"""


class Migration(migrations.Migration):
    dependencies = [
        ('purchase', '0010_backfill_price_with_tax'),
        # ProjectBOM.purchase_order 在 projects.0009,purchase_request 在 0011,取较晚者
        ('projects', '0011_add_pr_tracking_fields'),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
