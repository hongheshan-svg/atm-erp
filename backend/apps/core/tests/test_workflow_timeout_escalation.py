"""审批超时升级 (timeout_action='ESCALATE') 语义测试。

核心不变量：**实例永远保有一个 PENDING 任务**。approve_task 只处理 PENDING 任务，
所以把任务置为 TIMEOUT 而不同时给出接手人，等同于把单据永久卡死。因此升级要么
「原任务 TIMEOUT + 上级新任务 PENDING」成对发生，要么一点都不改。

本测试覆盖：
  (a) 超时且能找到上级 -> 原任务 TIMEOUT、上级获得新的 PENDING 任务、记录 TIMEOUT 事件；
  (b) 找不到上级 -> 任务保持 PENDING（绝不单方面置 TIMEOUT）；
  (c) 步骤未配置 ESCALATE（默认 NONE）-> 不动，沿用「只提醒」的历史行为；
  (d) 未到 deadline -> 不动；
  (e) 升级后单据仍可被新审批人正常批准（证明没有卡死）；
  (f) 连续升级不超过 MAX_TIMEOUT_ESCALATIONS；
  (g) 上级恰为提交人时不改派（职责分离，否则新任务谁也批不了）。
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Department
from apps.core.tasks import process_workflow_timeouts
from apps.core.workflow.models import WorkflowDefinition, WorkflowEvent, WorkflowStep, WorkflowTask
from apps.core.workflow.services import WorkflowService

User = get_user_model()


class WorkflowTimeoutEscalationTest(TestCase):
    def setUp(self):
        p1 = patch.object(WorkflowService, '_notify_assignee', return_value=None)
        p2 = patch.object(WorkflowService, '_on_workflow_complete', return_value=None)
        p3 = patch.object(WorkflowService, '_notify_timeout_escalation', return_value=None)
        for p in (p1, p2, p3):
            p.start()
            self.addCleanup(p.stop)

        # 部门树：总部 <- 事业部。审批人在事业部，其上级是事业部经理之上的总部经理。
        self.hq = Department.objects.create(name='总部', code='TO_HQ')
        self.div = Department.objects.create(name='事业部', code='TO_DIV', parent=self.hq)

        self.submitter = User.objects.create_user(username='to_submitter', password='x', employee_id='to_submitter')
        self.approver = User.objects.create_user(
            username='to_approver', password='x', employee_id='to_approver', department=self.div
        )
        self.superior = User.objects.create_user(username='to_superior', password='x', employee_id='to_superior')

        # 审批人是事业部经理本人 -> _escalate_to_superior 会上溯到总部经理
        self.div.manager = self.approver
        self.div.save(update_fields=['manager'])
        self.hq.manager = self.superior
        self.hq.save(update_fields=['manager'])

    # ---------- helpers ----------
    def _make_workflow(self, code, timeout_action='ESCALATE', business_type='PURCHASE_REQUEST'):
        # 同一 business_type 只能有一条「无金额阈值」的启用流程(workflow_unique_active_default)，
        # 需要在一个用例里并存两条流程时必须换 business_type。
        wf = WorkflowDefinition.objects.create(
            name='超时升级流程', code=code, business_type=business_type, is_active=True
        )
        step = WorkflowStep.objects.create(
            workflow=wf,
            step_order=1,
            name='部门审批',
            approver_type='USER',
            approver_user=self.approver,
            action_type='APPROVE',
            timeout_hours=24,
            timeout_action=timeout_action,
        )
        return wf, step

    def _start(self, code, business_id, timeout_action='ESCALATE', business_type='PURCHASE_REQUEST'):
        _wf, step = self._make_workflow(code, timeout_action=timeout_action, business_type=business_type)
        instance, err = WorkflowService.start_workflow(business_type, business_id, f'PR-{business_id}', self.submitter)
        self.assertIsNone(err)
        task = WorkflowTask.objects.get(instance=instance, step=step)
        return instance, step, task

    @staticmethod
    def _expire(task):
        """把任务的 deadline 推到过去，模拟超时。"""
        WorkflowTask.objects.filter(pk=task.pk).update(deadline=timezone.now() - timedelta(hours=1))
        task.refresh_from_db()
        return task

    # ---------- (a) 正常升级 ----------
    def test_escalates_to_superior_and_keeps_a_pending_task(self):
        instance, step, task = self._start('to_wf_a', 5001)
        self._expire(task)

        ok, msg = WorkflowService.escalate_timeout_task(task)
        self.assertTrue(ok, msg)

        task.refresh_from_db()
        self.assertEqual(task.status, 'TIMEOUT')
        self.assertIsNotNone(task.action_time)

        pending = WorkflowTask.objects.filter(instance=instance, status='PENDING')
        self.assertEqual(pending.count(), 1, '升级后必须恰好留下一个待办，否则单据无人可批')
        new_task = pending.get()
        self.assertEqual(new_task.assignee, self.superior)
        self.assertEqual(new_task.step, step)
        self.assertGreater(new_task.deadline, timezone.now())

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'PENDING')
        self.assertEqual(instance.current_step, 1, '升级不推进步骤，只换处理人')

        event = WorkflowEvent.objects.get(instance=instance, event_type='TIMEOUT')
        self.assertEqual(event.to_status, 'TIMEOUT')
        self.assertEqual(event.metadata['escalated_to'], self.superior.id)
        self.assertEqual(event.metadata['escalation_round'], 1)

    # ---------- (b) 找不到上级 -> 绝不置 TIMEOUT ----------
    def test_no_superior_leaves_task_pending(self):
        # 摘掉总部经理，审批人再无可上溯的上级
        self.hq.manager = None
        self.hq.save(update_fields=['manager'])

        instance, _step, task = self._start('to_wf_b', 5002)
        self._expire(task)

        ok, reason = WorkflowService.escalate_timeout_task(task)
        self.assertFalse(ok)
        self.assertIn('上级', reason)

        task.refresh_from_db()
        self.assertEqual(task.status, 'PENDING', '找不到接手人时必须保持 PENDING，否则单据永久卡死')
        self.assertEqual(WorkflowTask.objects.filter(instance=instance, status='PENDING').count(), 1)
        self.assertFalse(WorkflowEvent.objects.filter(instance=instance, event_type='TIMEOUT').exists())

    # ---------- (c) 默认 NONE 不改动 ----------
    def test_default_timeout_action_none_does_nothing(self):
        instance, _step, task = self._start('to_wf_c', 5003, timeout_action='NONE')
        self._expire(task)

        ok, reason = WorkflowService.escalate_timeout_task(task)
        self.assertFalse(ok)
        self.assertIn('未配置', reason)

        task.refresh_from_db()
        self.assertEqual(task.status, 'PENDING')
        self.assertEqual(WorkflowTask.objects.filter(instance=instance).count(), 1)

    # ---------- (d) 未超时不动 ----------
    def test_not_yet_overdue_is_untouched(self):
        _instance, _step, task = self._start('to_wf_d', 5004)

        ok, reason = WorkflowService.escalate_timeout_task(task)
        self.assertFalse(ok)
        self.assertIn('未超时', reason)

        task.refresh_from_db()
        self.assertEqual(task.status, 'PENDING')

    # ---------- (e) 升级后仍可正常审批完成 ----------
    def test_escalated_task_can_still_be_approved(self):
        instance, _step, task = self._start('to_wf_e', 5005)
        self._expire(task)
        self.assertTrue(WorkflowService.escalate_timeout_task(task)[0])

        new_task = WorkflowTask.objects.get(instance=instance, status='PENDING')
        ok, msg = WorkflowService.approve_task(new_task, self.superior)
        self.assertTrue(ok, msg)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'APPROVED', '升级后的任务必须能正常推进单据')

    # ---------- (f) 升级次数封顶 ----------
    def test_escalation_is_capped(self):
        # 构造一条足够长的管理链：dept_i 的经理是 u_i 且 u_i 本人也在 dept_i。
        # _escalate_to_superior 会跳过「经理是自己」的那一层继续上溯，于是
        # u_0 -> u_1 -> u_2 -> ... 每一轮都能找到新的上级，升级只可能被封顶挡住。
        depth = WorkflowService.MAX_TIMEOUT_ESCALATIONS + 2
        chain_depts = []
        chain_users = []
        for i in range(depth):
            dept = Department.objects.create(name=f'链层{i}', code=f'TO_CH_{i}')
            user = User.objects.create_user(
                username=f'to_chain_{i}', password='x', employee_id=f'to_chain_{i}', department=dept
            )
            dept.manager = user
            dept.save(update_fields=['manager'])
            chain_depts.append(dept)
            chain_users.append(user)
        for i in range(depth - 1):
            chain_depts[i].parent = chain_depts[i + 1]
            chain_depts[i].save(update_fields=['parent'])

        wf = WorkflowDefinition.objects.create(
            name='封顶流程', code='to_wf_f', business_type='PURCHASE_REQUEST', is_active=True
        )
        WorkflowStep.objects.create(
            workflow=wf,
            step_order=1,
            name='链式审批',
            approver_type='USER',
            approver_user=chain_users[0],
            action_type='APPROVE',
            timeout_hours=24,
            timeout_action='ESCALATE',
        )
        instance, err = WorkflowService.start_workflow('PURCHASE_REQUEST', 5006, 'PR-5006', self.submitter)
        self.assertIsNone(err)

        rounds = 0
        last_reason = ''
        for _ in range(depth):
            current = WorkflowTask.objects.filter(instance=instance, status='PENDING').first()
            self.assertIsNotNone(current, '任何一轮之后都必须仍有待办')
            self._expire(current)
            ok, last_reason = WorkflowService.escalate_timeout_task(current)
            if not ok:
                break
            rounds += 1

        self.assertEqual(rounds, WorkflowService.MAX_TIMEOUT_ESCALATIONS)
        self.assertIn('不再自动改派', last_reason)
        self.assertEqual(
            WorkflowTask.objects.filter(instance=instance, status='PENDING').count(),
            1,
            '封顶之后任务仍须保持 PENDING 等人工处理',
        )

    # ---------- (g) 上级即提交人 -> 不改派 ----------
    def test_superior_equal_to_submitter_is_not_escalated(self):
        self.hq.manager = self.submitter
        self.hq.save(update_fields=['manager'])

        instance, _step, task = self._start('to_wf_g', 5007)
        self._expire(task)

        ok, reason = WorkflowService.escalate_timeout_task(task)
        self.assertFalse(ok)
        self.assertIn('职责分离', reason)

        task.refresh_from_db()
        self.assertEqual(task.status, 'PENDING')
        self.assertEqual(WorkflowTask.objects.filter(instance=instance, status='PENDING').count(), 1)

    # ---------- Celery 任务只挑 ESCALATE 步骤 ----------
    def test_celery_task_only_processes_escalate_steps(self):
        inst_esc, _s1, t1 = self._start('to_wf_h1', 5008, timeout_action='ESCALATE')
        inst_none, _s2, t2 = self._start('to_wf_h2', 5009, timeout_action='NONE', business_type='PURCHASE_ORDER')
        self._expire(t1)
        self._expire(t2)

        result = process_workflow_timeouts()
        self.assertIn('1 escalated', result)

        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertEqual(t1.status, 'TIMEOUT')
        self.assertEqual(t2.status, 'PENDING')
        self.assertEqual(WorkflowTask.objects.filter(instance=inst_esc, status='PENDING').count(), 1)
        self.assertEqual(WorkflowTask.objects.filter(instance=inst_none, status='PENDING').count(), 1)
