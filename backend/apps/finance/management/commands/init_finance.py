import calendar
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.finance.accounting import FiscalPeriod
from apps.finance.models import Currency
from apps.finance.posting import seed_standard_accounts


class Command(BaseCommand):
    help = '幂等初始化标准科目、基准币和首个会计期间'

    def handle(self, *args, **options):
        account_result = seed_standard_accounts()
        currency, currency_created = Currency.objects.get_or_create(
            code='CNY',
            defaults={
                'name': '人民币',
                'symbol': '¥',
                'exchange_rate': Decimal('1'),
                'is_base_currency': True,
                'is_active': True,
            },
        )
        if not Currency.objects.filter(is_base_currency=True, is_deleted=False).exists():
            currency.is_base_currency = True
            currency.save(update_fields=['is_base_currency', 'updated_at'])

        period_created = False
        if not FiscalPeriod.objects.filter(is_deleted=False).exists():
            today = timezone.localdate()
            end_day = calendar.monthrange(today.year, today.month)[1]
            _, period_created = FiscalPeriod.objects.get_or_create(
                year=today.year,
                period=today.month,
                defaults={
                    'start_date': date(today.year, today.month, 1),
                    'end_date': date(today.year, today.month, end_day),
                    'status': 'OPEN',
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                '财务初始化完成: '
                f'科目类别新增 {account_result["categories"]}, 科目新增 {account_result["accounts"]}, '
                f'基准币新增 {int(currency_created)}, 首个会计期间新增 {int(period_created)}'
            )
        )
