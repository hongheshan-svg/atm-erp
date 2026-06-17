from django.test import SimpleTestCase

from apps.projects.tasks import build_personal_task_reminders


class _User:
    def __init__(self, active=True, wxid='wx1'):
        self.is_active = active
        self.wechat_work_id = wxid


class BuildPersonalTaskTest(SimpleTestCase):
    def test_builds_personal_messages_per_assignee(self):
        u = _User()
        data = {u: {'overdue': ['[P-1] 任务A | 逾期2天 | 进度10%'], 'upcoming': [], 'behind': []}}
        msgs, has_unassigned = build_personal_task_reminders(data, unassigned_present=True)
        self.assertEqual(len(msgs), 1)
        self.assertIs(msgs[0][0], u)
        self.assertIn('任务A', msgs[0][1])
        self.assertTrue(has_unassigned)
