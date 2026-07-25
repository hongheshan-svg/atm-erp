from datetime import date, datetime
from datetime import timezone as datetime_timezone

from django.test import SimpleTestCase
from django.utils import timezone

from apps.finance.bank_statement_views import BankStatementViewSet


class BankStatementDatetimeParsingTest(SimpleTestCase):
    def setUp(self):
        self.viewset = BankStatementViewSet()

    def test_parsed_string_is_timezone_aware(self):
        parsed = self.viewset._parse_datetime('2024-01-15 10:00:00')

        self.assertTrue(timezone.is_aware(parsed))

    def test_date_value_is_timezone_aware(self):
        parsed = self.viewset._parse_datetime(date(2024, 1, 15))

        self.assertTrue(timezone.is_aware(parsed))
        self.assertEqual(parsed.time(), datetime.min.time())

    def test_aware_datetime_is_preserved(self):
        value = datetime(2024, 1, 15, 10, tzinfo=datetime_timezone.utc)

        self.assertIs(self.viewset._parse_datetime(value), value)
