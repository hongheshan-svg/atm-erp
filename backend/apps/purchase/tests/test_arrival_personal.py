from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.purchase.tasks import build_personal_arrival_reminders


class _User:
    def __init__(self, active=True, wxid='wx1'):
        self.is_active = active
        self.wechat_work_id = wxid


def _order(no, created_by, ddate, sup='供应商A', amt=2000):
    return SimpleNamespace(
        order_no=no,
        created_by=created_by,
        delivery_date=ddate,
        supplier=SimpleNamespace(name=sup),
        total_amount=amt,
    )


class BuildPersonalArrivalTest(SimpleTestCase):
    def test_groups_by_created_by(self):
        u = _User()
        today = date(2026, 6, 17)
        messages, has_unassigned = build_personal_arrival_reminders(
            [_order('PO-1', u, date(2026, 6, 10))], [], today
        )
        self.assertEqual(len(messages), 1)
        self.assertIn('PO-1', messages[0][1])
        self.assertFalse(has_unassigned)

    def test_unassigned_flagged(self):
        today = date(2026, 6, 17)
        messages, has_unassigned = build_personal_arrival_reminders(
            [_order('PO-2', None, date(2026, 6, 10))], [], today
        )
        self.assertEqual(messages, [])
        self.assertTrue(has_unassigned)
