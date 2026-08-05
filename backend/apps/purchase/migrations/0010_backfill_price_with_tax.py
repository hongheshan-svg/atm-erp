"""回填存量采购申请/订单明细的含税单价。

0009 新增的 price_with_tax 默认 0,存量单据若不回填,列表与明细页会显示 ¥0.00。
存量数据一律是未税口径(price_input_mode 默认 EXCLUSIVE),因此按各自单头税率
正向算出含税单价即可,不改动任何入账金额。
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations

QUANT = Decimal('0.01')
BATCH_SIZE = 2000


def _inclusive(price, tax_rate):
    price = Decimal(str(price or 0))
    rate = Decimal(str(tax_rate or 0))
    return (price * (Decimal('1') + rate / Decimal('100'))).quantize(QUANT, rounding=ROUND_HALF_UP)


def backfill(apps, schema_editor):
    PurchaseRequestLine = apps.get_model('purchase', 'PurchaseRequestLine')
    PurchaseOrderLine = apps.get_model('purchase', 'PurchaseOrderLine')

    pr_lines = []
    for line in PurchaseRequestLine.objects.select_related('pr').filter(price_with_tax=0).iterator():
        line.price_with_tax = _inclusive(line.estimated_price, line.pr.tax_rate)
        pr_lines.append(line)
        if len(pr_lines) >= BATCH_SIZE:
            PurchaseRequestLine.objects.bulk_update(pr_lines, ['price_with_tax'])
            pr_lines = []
    if pr_lines:
        PurchaseRequestLine.objects.bulk_update(pr_lines, ['price_with_tax'])

    po_lines = []
    for line in PurchaseOrderLine.objects.select_related('po').filter(price_with_tax=0).iterator():
        line.price_with_tax = _inclusive(line.unit_price, line.po.tax_rate)
        po_lines.append(line)
        if len(po_lines) >= BATCH_SIZE:
            PurchaseOrderLine.objects.bulk_update(po_lines, ['price_with_tax'])
            po_lines = []
    if po_lines:
        PurchaseOrderLine.objects.bulk_update(po_lines, ['price_with_tax'])


def noop_reverse(apps, schema_editor):
    """回滚不清零:含税单价是纯展示字段,留着无害,清掉反而丢信息。"""


class Migration(migrations.Migration):
    dependencies = [
        ('purchase', '0009_purchaseorder_price_input_mode_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
