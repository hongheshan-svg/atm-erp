from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.sales.tasks import build_personal_delivery_reminders


class _User:
    """可 hash 的 user stub（真实 User 实例按 pk 可 hash，SimpleNamespace 不可 hash）。"""

    def __init__(self, active=True, wxid='wx1'):
        self.is_active = active
        self.wechat_work_id = wxid


def _order(no, created_by, ddate, cust='客户A', amt=1000):
    return SimpleNamespace(
        order_no=no,
        created_by=created_by,
        expected_delivery_date=ddate,
        customer=SimpleNamespace(name=cust),
        total_amount=amt,
    )


class BuildPersonalDeliveryTest(SimpleTestCase):
    def test_groups_by_created_by_and_flags_unassigned(self):
        u = _User()
        today = date(2026, 6, 17)
        overdue = [_order('SO-1', u, date(2026, 6, 10))]
        upcoming = [_order('SO-2', None, date(2026, 6, 19))]  # 无 created_by → unassigned
        messages, has_unassigned = build_personal_delivery_reminders(overdue, upcoming, today)
        self.assertEqual(len(messages), 1)
        self.assertIs(messages[0][0], u)
        self.assertIn('SO-1', messages[0][1])
        self.assertTrue(has_unassigned)
