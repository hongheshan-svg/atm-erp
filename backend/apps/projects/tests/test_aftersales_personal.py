from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.projects.tasks import build_personal_aftersales_reminders


class _User:
    def __init__(self, active=True, wxid='wx1'):
        self.is_active = active
        self.wechat_work_id = wxid


def _order(no, assigned_to, edate, cust='客户A'):
    return SimpleNamespace(
        order_no=no,
        title='工单',
        assigned_to=assigned_to,
        expected_date=edate,
        customer=SimpleNamespace(name=cust),
        get_priority_display=lambda: '高',
    )


class BuildPersonalAftersalesTest(SimpleTestCase):
    def test_groups_by_assigned_to(self):
        u = _User()
        today = date(2026, 6, 17)
        msgs, unassigned = build_personal_aftersales_reminders(
            [_order('AS-1', u, date(2026, 6, 10))], [_order('AS-2', None, date(2026, 6, 18))], today
        )
        self.assertEqual(len(msgs), 1)
        self.assertIn('AS-1', msgs[0][1])
        self.assertTrue(unassigned)
