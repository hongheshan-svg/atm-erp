from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.notification_service import NotificationService


def _user(active=True, wxid='wx1'):
    return SimpleNamespace(is_active=active, wechat_work_id=wxid)


class SendTargetedRemindersTest(SimpleTestCase):
    def test_personal_sent_for_users_with_wechat_no_group(self):
        u = _user()
        with patch.object(NotificationService, 'send_to_user') as m_personal, patch.object(
            NotificationService, 'send_custom_notification'
        ) as m_group:
            res = NotificationService.send_targeted_reminders([(u, '明细A')], '标题', 'safe', has_unassigned=False)
        m_personal.assert_called_once_with(u, '标题', '明细A')
        m_group.assert_not_called()
        self.assertEqual(res, {'personal_sent': 1, 'personal_skipped': 0})

    def test_user_without_wechat_falls_back_to_group(self):
        u = _user(wxid='')
        with patch.object(NotificationService, 'send_to_user') as m_personal, patch.object(
            NotificationService, 'send_custom_notification'
        ) as m_group:
            res = NotificationService.send_targeted_reminders([(u, 'x')], 't', 'safe')
        m_personal.assert_not_called()
        m_group.assert_called_once()
        self.assertEqual(res['personal_skipped'], 1)

    def test_has_unassigned_forces_group_even_when_personal_sent(self):
        u = _user()
        with patch.object(NotificationService, 'send_to_user') as m_personal, patch.object(
            NotificationService, 'send_custom_notification'
        ) as m_group:
            NotificationService.send_targeted_reminders([(u, 'x')], 't', 'safe', has_unassigned=True)
        m_personal.assert_called_once()
        m_group.assert_called_once()

    def test_empty_personal_sends_group(self):
        with patch.object(NotificationService, 'send_to_user') as m_personal, patch.object(
            NotificationService, 'send_custom_notification'
        ) as m_group:
            NotificationService.send_targeted_reminders([], 't', 'safe')
        m_personal.assert_not_called()
        m_group.assert_called_once()
