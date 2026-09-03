"""初始化编码规则种子数据。

编码规则表为空时 ``CodeRule.generate_code_by_rule`` 会退到「前缀 + 日期 + 6 位随机数」
的兜底分支，生成的单号没有连续序号且带随机后缀，无法用于追溯与对账。本命令为
``CodeRule.RULE_TYPE_CHOICES`` 里的每一类单据写入一条可用规则。

默认只补齐缺失的规则类型，已存在的原样保留（避免重置 ``current_seq`` 造成单号回退）；
``--force`` 才会覆盖已有配置，同样不会动 ``current_seq``。
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.code_rule_models import CodeRule

# (rule_type, rule_name, prefix, date_format, seq_length, reset_mode)
CODE_RULE_SEEDS = [
    ('PROJECT', '项目编号', 'PRJ', 'YYYY', 4, 'YEARLY'),
    ('ITEM', '物料编码', 'M', '', 6, 'NONE'),
    ('PURCHASE_REQUEST', '采购申请单号', 'PR', 'YYYYMM', 4, 'MONTHLY'),
    ('PURCHASE_ORDER', '采购订单号', 'PO', 'YYYYMM', 4, 'MONTHLY'),
    ('PURCHASE_CONTRACT', '采购合同号', 'PC', 'YYYYMM', 3, 'MONTHLY'),
    ('SALES_QUOTE', '销售报价单号', 'QT', 'YYYYMM', 4, 'MONTHLY'),
    ('SALES_ORDER', '销售订单号', 'SO', 'YYYYMM', 4, 'MONTHLY'),
    ('SALES_CONTRACT', '销售合同号', 'SC', 'YYYYMM', 3, 'MONTHLY'),
    ('DELIVERY_ORDER', '发货单号', 'DO', 'YYYYMM', 4, 'MONTHLY'),
    ('GOODS_RECEIPT', '收货单号', 'GR', 'YYYYMM', 4, 'MONTHLY'),
    ('INVOICE', '发票号', 'INV', 'YYYYMM', 4, 'MONTHLY'),
    ('STOCK_MOVE', '库存移动单号', 'SM', 'YYYYMMDD', 4, 'DAILY'),
    ('STOCK_ADJUSTMENT', '库存调整单号', 'SA', 'YYYYMM', 3, 'MONTHLY'),
    ('PRODUCTION_PLAN', '生产计划号', 'PP', 'YYYYMM', 4, 'MONTHLY'),
    ('QUALITY_INSPECTION', '质量检验单号', 'QC', 'YYYYMM', 4, 'MONTHLY'),
    ('DEBUG_RECORD', '调试记录号', 'DBG', 'YYYYMM', 3, 'MONTHLY'),
    ('BUG', 'Bug 编号', 'BUG', 'YYYY', 4, 'YEARLY'),
]


class Command(BaseCommand):
    help = '初始化各类业务单据的编码规则（默认只补齐缺失项，--force 覆盖已有配置）'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='覆盖已存在的规则配置（不重置当前序列号）')

    @transaction.atomic
    def handle(self, *args, **options):
        force = options['force']
        created, updated, skipped = 0, 0, 0

        for rule_type, rule_name, prefix, date_format, seq_length, reset_mode in CODE_RULE_SEEDS:
            defaults = {
                'rule_name': rule_name,
                'prefix': prefix,
                'date_format': date_format,
                'seq_length': seq_length,
                'seq_start': 1,
                'reset_mode': reset_mode,
                'separator': '',
                'is_active': True,
                'description': '由 init_code_rules 初始化',
            }
            rule = CodeRule.all_objects.filter(rule_type=rule_type).first()

            if rule is None:
                rule = CodeRule.objects.create(rule_type=rule_type, **defaults)
                created += 1
                self.stdout.write(f'  + {rule_type:<20} {rule.example}')
            elif force:
                for field, value in defaults.items():
                    setattr(rule, field, value)
                rule.is_deleted = False
                rule.deleted_at = None
                rule.save()
                updated += 1
                self.stdout.write(f'  ~ {rule_type:<20} {rule.example}')
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f'编码规则初始化完成：新增 {created}，更新 {updated}，跳过 {skipped}（已存在）')
        )
