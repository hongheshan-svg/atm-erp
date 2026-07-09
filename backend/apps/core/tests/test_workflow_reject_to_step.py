"""
P1 回归测试：审批流「退回指定步」(reject_to_step)。

审计发现：旧引擎的拒绝 (reject_task) 只能整单拒绝 —— 实例直接进入 REJECTED、
整条流程结束，无法把单据退回到更早的某一步重审。这不符合真实审批场景
（例如三级审批中，第三级发现一级填错，只想退回第一级修改，而非全盘否决）。

本测试覆盖新增的 reject_to_step 语义：
  (a) 处于第 3 步的实例 reject_to_step(target=1) 后：
        - instance.current_step 回退到 1；
        - instance.status 仍为 PENDING（审批中，未整单拒绝）；
        - 第 1 步任务被重新创建为 PENDING；
        - 原第 3 步任务标记为 RETURNED（区别于 REJECTED）。
  (b) 退回后重新审批第 1 步可继续向前推进直至整单通过。
  (c) 守卫：target >= 当前步 或 target < 1 均被拒绝；不存在的步骤被拒绝。
  (d) 退回时当前步的其余待办（会签兄弟任务）被置为 SKIPPED。
  (e) reject_task（整单拒绝）语义保持不变（回归保护）。
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Role
from apps.core.workflow.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowTask,
)
from apps.core.workflow.services import WorkflowService

User = get_user_model()


class WorkflowRejectToStepTest(TestCase):
    def setUp(self):
        # 隔离引擎外的副作用：通知 / 业务对象回填不属于本测试关注点。
        p1 = patch.object(WorkflowService, '_notify_assignee', return_value=None)
        p2 = patch.object(WorkflowService, '_on_workflow_complete', return_value=None)
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)

        self.submitter = User.objects.create_user(
            username='rts_submitter', password='x', employee_id='rts_submitter'
        )
        self.approver1 = User.objects.create_user(
            username='rts_appr1', password='x', employee_id='rts_appr1'
        )
        self.approver2 = User.objects.create_user(
            username='rts_appr2', password='x', employee_id='rts_appr2'
        )
        self.approver3 = User.objects.create_user(
            username='rts_appr3', password='x', employee_id='rts_appr3'
        )

    # ---------- helpers ----------
    def _make_three_step_workflow(self, code):
        wf = WorkflowDefinition.objects.create(
            name='三级审批', code=code, business_type='PURCHASE_REQUEST', is_active=True
        )
        s1 = WorkflowStep.objects.create(
            workflow=wf, step_order=1, name='一级', approver_type='USER',
            approver_user=self.approver1, action_type='APPROVE',
        )
        s2 = WorkflowStep.objects.create(
            workflow=wf, step_order=2, name='二级', approver_type='USER',
            approver_user=self.approver2, action_type='APPROVE',
        )
        s3 = WorkflowStep.objects.create(
            workflow=wf, step_order=3, name='三级', approver_type='USER',
            approver_user=self.approver3, action_type='APPROVE',
        )
        return wf, (s1, s2, s3)

    def _start_and_advance_to_step3(self, code, business_id, business_no):
        """启动三级审批流并逐级通过至第 3 步（第 3 步留一个 PENDING 任务）。"""
        wf, steps = self._make_three_step_workflow(code)
        instance, err = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', business_id, business_no, self.submitter
        )
        self.assertIsNone(err)

        t1 = WorkflowTask.objects.get(instance=instance, step__step_order=1, status='PENDING')
        ok, msg = WorkflowService.approve_task(t1, self.approver1)
        self.assertTrue(ok, msg)
        t2 = WorkflowTask.objects.get(instance=instance, step__step_order=2, status='PENDING')
        ok, msg = WorkflowService.approve_task(t2, self.approver2)
        self.assertTrue(ok, msg)

        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 3)
        self.assertEqual(instance.status, 'PENDING')
        t3 = WorkflowTask.objects.get(instance=instance, step__step_order=3, status='PENDING')
        return instance, steps, t3

    # ---------- (a) 退回到第 1 步：回退步号、不整单拒绝、重建任务、原任务 RETURNED ----------
    def test_reject_to_step_rewinds_and_recreates(self):
        instance, steps, t3 = self._start_and_advance_to_step3('rts_a', 5001, 'PR-RTS-A')

        ok, msg = WorkflowService.reject_to_step(t3, 1, self.approver3, comment='一级填错，退回重填')
        self.assertTrue(ok, msg)

        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 1, '退回后当前步应回退到目标步 1')
        self.assertEqual(instance.status, 'PENDING', '退回不得整单拒绝，实例应保持审批中')

        # 原第 3 步任务被标记为 RETURNED（区别于整单拒绝的 REJECTED）
        t3.refresh_from_db()
        self.assertEqual(t3.status, 'RETURNED')
        self.assertEqual(t3.comment, '一级填错，退回重填')

        # 第 1 步任务被重新创建为 PENDING
        pending_step1 = WorkflowTask.objects.filter(
            instance=instance, step__step_order=1, status='PENDING'
        )
        self.assertEqual(pending_step1.count(), 1, '应为目标步 1 重新创建一个待办任务')
        self.assertEqual(pending_step1.first().assignee, self.approver1)

    # ---------- (b) 退回后重新审批可继续向前推进直至整单通过 ----------
    def test_reapproving_after_return_advances_forward(self):
        instance, steps, t3 = self._start_and_advance_to_step3('rts_b', 5002, 'PR-RTS-B')

        ok, _ = WorkflowService.reject_to_step(t3, 1, self.approver3, comment='退回')
        self.assertTrue(ok)

        # 重新从第 1 步逐级通过 —— 每步都取当前 PENDING 任务
        new_t1 = WorkflowTask.objects.get(
            instance=instance, step__step_order=1, status='PENDING'
        )
        ok, msg = WorkflowService.approve_task(new_t1, self.approver1)
        self.assertTrue(ok, msg)
        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 2)

        new_t2 = WorkflowTask.objects.get(
            instance=instance, step__step_order=2, status='PENDING'
        )
        ok, msg = WorkflowService.approve_task(new_t2, self.approver2)
        self.assertTrue(ok, msg)
        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 3)

        new_t3 = WorkflowTask.objects.get(
            instance=instance, step__step_order=3, status='PENDING'
        )
        ok, msg = WorkflowService.approve_task(new_t3, self.approver3)
        self.assertTrue(ok, msg)
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'APPROVED', '退回并重审后应能正常推进至整单通过')

    # ---------- (c) 守卫：target >= 当前步 / target < 1 / 不存在的步骤 ----------
    def test_guard_rejects_target_not_earlier(self):
        instance, steps, t3 = self._start_and_advance_to_step3('rts_c', 5003, 'PR-RTS-C')

        # target == 当前步(3)
        ok, msg = WorkflowService.reject_to_step(t3, 3, self.approver3, comment='x')
        self.assertFalse(ok)
        # target > 当前步(4)
        ok, msg = WorkflowService.reject_to_step(t3, 4, self.approver3, comment='x')
        self.assertFalse(ok)
        # target < 1
        ok, msg = WorkflowService.reject_to_step(t3, 0, self.approver3, comment='x')
        self.assertFalse(ok)
        # 非法输入
        ok, msg = WorkflowService.reject_to_step(t3, 'abc', self.approver3, comment='x')
        self.assertFalse(ok)

        # 被守卫拦截后：实例与任务状态均不变
        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 3)
        self.assertEqual(instance.status, 'PENDING')
        t3.refresh_from_db()
        self.assertEqual(t3.status, 'PENDING')

    def test_guard_rejects_nonexistent_step(self):
        # 只有 1、2、3 三个步骤；第 3 步退回到不存在但 <current 的步号需借助 gap。
        wf = WorkflowDefinition.objects.create(
            name='跳步审批', code='rts_gap', business_type='PURCHASE_REQUEST', is_active=True
        )
        WorkflowStep.objects.create(
            workflow=wf, step_order=1, name='一级', approver_type='USER',
            approver_user=self.approver1, action_type='APPROVE',
        )
        # 故意不建 step_order=2，直接到 step_order=3
        WorkflowStep.objects.create(
            workflow=wf, step_order=3, name='三级', approver_type='USER',
            approver_user=self.approver3, action_type='APPROVE',
        )
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 5004, 'PR-RTS-GAP', self.submitter
        )
        t1 = WorkflowTask.objects.get(instance=instance, step__step_order=1, status='PENDING')
        WorkflowService.approve_task(t1, self.approver1)
        # 通过第 1 步后引擎为 step_order=3 建了待办任务（step_order=2 不存在被跳过）。
        t3 = WorkflowTask.objects.get(instance=instance, step__step_order=3, status='PENDING')
        instance.refresh_from_db()
        before_step = instance.current_step

        # 退回到 step_order=2（<当前任务步 3，但该步不存在）应被守卫拒绝
        ok, msg = WorkflowService.reject_to_step(t3, 2, self.approver3, comment='x')
        self.assertFalse(ok, '退回到不存在的步骤应被拒绝')
        instance.refresh_from_db()
        self.assertEqual(instance.current_step, before_step, '守卫拦截后步号不变')
        t3.refresh_from_db()
        self.assertEqual(t3.status, 'PENDING', '守卫拦截后任务保持待处理')

    # ---------- (d) 退回时当前步的其余待办（会签兄弟任务）被 SKIPPED ----------
    def test_reject_to_step_skips_sibling_pending_tasks(self):
        role_cs = Role.objects.create(name='退回会签组', code='rts_cs_group')
        members = []
        for i in range(3):
            u = User.objects.create_user(
                username=f'rts_cs_{i}', password='x', employee_id=f'rts_cs_{i}'
            )
            u.roles.add(role_cs)
            members.append(u)

        wf = WorkflowDefinition.objects.create(
            name='会签退回流', code='rts_cs', business_type='PURCHASE_REQUEST', is_active=True
        )
        WorkflowStep.objects.create(
            workflow=wf, step_order=1, name='一级', approver_type='USER',
            approver_user=self.approver1, action_type='APPROVE',
        )
        WorkflowStep.objects.create(
            workflow=wf, step_order=2, name='二级会签', approver_type='ROLE',
            approver_role=role_cs, action_type='COUNTERSIGN',
        )
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 5005, 'PR-RTS-CS', self.submitter
        )
        # 通过第 1 步 -> 进入第 2 步会签（3 个 PENDING 任务）
        t1 = WorkflowTask.objects.get(instance=instance, step__step_order=1, status='PENDING')
        WorkflowService.approve_task(t1, self.approver1)
        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 2)

        cs_tasks = list(
            WorkflowTask.objects.filter(
                instance=instance, step__step_order=2, status='PENDING'
            ).order_by('id')
        )
        self.assertEqual(len(cs_tasks), 3)

        # 一名会签人执行退回到第 1 步 -> 该任务 RETURNED，其余 2 个兄弟任务 SKIPPED
        ok, msg = WorkflowService.reject_to_step(cs_tasks[0], 1, cs_tasks[0].assignee, comment='退回')
        self.assertTrue(ok, msg)

        cs_tasks[0].refresh_from_db()
        self.assertEqual(cs_tasks[0].status, 'RETURNED')
        for t in cs_tasks[1:]:
            t.refresh_from_db()
            self.assertEqual(t.status, 'SKIPPED', '退回时当前会签步的其余待办应被跳过')

        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 1)
        self.assertEqual(instance.status, 'PENDING')
        # 第 1 步重建一个待办
        self.assertEqual(
            WorkflowTask.objects.filter(
                instance=instance, step__step_order=1, status='PENDING'
            ).count(),
            1,
        )

    # ---------- (e) 整单拒绝语义保持不变（回归保护）----------
    def test_full_reject_still_rejects_instance(self):
        instance, steps, t3 = self._start_and_advance_to_step3('rts_e', 5006, 'PR-RTS-E')

        ok, msg = WorkflowService.reject_task(t3, self.approver3, comment='整单否决')
        self.assertTrue(ok, msg)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'REJECTED', 'reject_task 仍应整单拒绝')
        t3.refresh_from_db()
        self.assertEqual(t3.status, 'REJECTED')

    def test_reject_to_step_guards_non_pending_task(self):
        """已处理(非 PENDING)的任务不能退回。"""
        instance, steps, t3 = self._start_and_advance_to_step3('rts_f', 5007, 'PR-RTS-F')
        WorkflowService.approve_task(t3, self.approver3)  # 第 3 步通过 -> 整单完成
        t3.refresh_from_db()
        self.assertEqual(t3.status, 'APPROVED')

        ok, msg = WorkflowService.reject_to_step(t3, 1, self.approver3, comment='x')
        self.assertFalse(ok, '已处理任务不应允许退回')
