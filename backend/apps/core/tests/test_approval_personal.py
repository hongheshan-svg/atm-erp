from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.notification_service import NotificationService


def _task(wxid='wx1'):
    wf = SimpleNamespace(get_business_type_display=lambda: '采购订单')
    inst = SimpleNamespace(workflow=wf, business_no='PO-1')
    assignee = SimpleNamespace(is_active=True, wechat_work_id=wxid)
    return SimpleNamespace(instance=inst, assignee=assignee)


class ApprovalPersonalTest(SimpleTestCase):
    def test_approval_notifies_assignee_personally(self):
        t = _task()
        with patch.object(NotificationService, 'send_to_user') as m_personal, patch.object(
            NotificationService, 'send_custom_notification'
        ) as m_group:
            NotificationService.send_approval_notification(t)
        m_personal.assert_called_once()
        self.assertIs(m_personal.call_args.args[0], t.assignee)
        m_group.assert_not_called()

    def test_approval_without_wechat_falls_back_group(self):
        t = _task(wxid='')
        with patch.object(NotificationService, 'send_to_user') as m_personal, patch.object(
            NotificationService, 'send_custom_notification'
        ) as m_group:
            NotificationService.send_approval_notification(t)
        m_personal.assert_not_called()
        m_group.assert_called_once()

    def test_result_notifies_submitter_personally(self):
        wf = SimpleNamespace(get_business_type_display=lambda: '采购订单')
        submitter = SimpleNamespace(is_active=True, wechat_work_id='wx9')
        inst = SimpleNamespace(workflow=wf, business_no='PO-9', submitter=submitter)
        with patch.object(NotificationService, 'send_to_user') as m_personal:
            NotificationService.send_workflow_result_notification(inst, 'APPROVED')
        m_personal.assert_called_once()
        self.assertIs(m_personal.call_args.args[0], submitter)
