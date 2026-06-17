from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.projects.tasks import build_personal_project_reminders


class _User:
    def __init__(self, active=True, wxid='wx1'):
        self.is_active = active
        self.wechat_work_id = wxid


def _proj(code, manager, edate, name='项目X'):
    return SimpleNamespace(code=code, name=name, manager=manager, end_date=edate)


class BuildPersonalProjectTest(SimpleTestCase):
    def test_groups_by_manager_and_flags_unassigned(self):
        u = _User()
        today = date(2026, 6, 17)
        msgs, unassigned = build_personal_project_reminders(
            [_proj('P-1', u, date(2026, 6, 10))], [_proj('P-2', None, date(2026, 6, 20))], today
        )
        self.assertEqual(len(msgs), 1)
        self.assertIn('P-1', msgs[0][1])
        self.assertTrue(unassigned)
