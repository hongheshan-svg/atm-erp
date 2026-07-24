"""
P1 回归测试：会签 (COUNTERSIGN) 必须真正多人会签，而非退化成单人审批。

根因：旧引擎每个步骤只解析 `.first()` 一个审批人、只建 1 个 WorkflowTask，
approve_task 单个通过即推进步骤。因此配置为会签的步骤被静默降级为单人审批，
存在审批/合规风险。

修复要点（本测试覆盖）：
  (a) 3 人会签步骤创建 3 个任务，且必须 3 人全部通过才推进/完成；
  (b) 任意一人拒绝即整单拒绝，其余待办被置为 SKIPPED；
  (c) 普通单人审批步骤仍旧一人通过即推进（回归保护）。

说明：或签 (OR-SIGN) 当前未在 WorkflowStep.ACTION_TYPE_CHOICES 中建模，
本轮不实现，留作后续（见报告 residual_risk）。
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


class WorkflowCountersignTest(TestCase):
    def setUp(self):
        # 隔离引擎外的副作用：通知 / 业务对象回填不属于本测试关注点。
        p1 = patch.object(WorkflowService, '_notify_assignee', return_value=None)
        p2 = patch.object(WorkflowService, '_on_workflow_complete', return_value=None)
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)

        self.submitter = User.objects.create_user(
            username='cs_submitter', password='x', employee_id='cs_submitter'
        )

        # 会签角色 + 3 名成员
        self.role_cs = Role.objects.create(name='会签组', code='countersign_group')
        self.cs_users = []
        for i in range(3):
            u = User.objects.create_user(
                username=f'cs_member_{i}', password='x', employee_id=f'cs_member_{i}'
            )
            u.roles.add(self.role_cs)
            self.cs_users.append(u)

    # ---------- helpers ----------
    def _make_countersign_workflow(self, code):
        wf = WorkflowDefinition.objects.create(
            name='会签流程', code=code, business_type='PURCHASE_REQUEST', is_active=True
        )
        step = WorkflowStep.objects.create(
            workflow=wf,
            step_order=1,
            name='部门会签',
            approver_type='ROLE',
            approver_role=self.role_cs,
            action_type='COUNTERSIGN',
        )
        return wf, step

    # ---------- (a) 会签：3 任务，全部通过才推进 ----------
    def test_countersign_creates_task_per_assignee(self):
        wf, step = self._make_countersign_workflow('cs_wf_a')
        instance, err = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 1001, 'PR-CS-A', self.submitter
        )
        self.assertIsNone(err)
        self.assertIsNotNone(instance)

        tasks = WorkflowTask.objects.filter(instance=instance, step=step)
        self.assertEqual(tasks.count(), 3, '会签步骤应为每位会签人各建 1 个任务')
        self.assertEqual(tasks.filter(status='PENDING').count(), 3)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'PENDING')
        self.assertEqual(instance.current_step, 1)

    def test_countersign_does_not_advance_until_all_approve(self):
        wf, step = self._make_countersign_workflow('cs_wf_b')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 1002, 'PR-CS-B', self.submitter
        )

        tasks = list(
            WorkflowTask.objects.filter(instance=instance, step=step).order_by('id')
        )
        self.assertEqual(len(tasks), 3)

        # 前两人通过 —— 仍不得推进 / 完成
        for t in tasks[:2]:
            ok, msg = WorkflowService.approve_task(t, t.assignee)
            self.assertTrue(ok, msg)
            instance.refresh_from_db()
            self.assertEqual(instance.status, 'PENDING')
            self.assertEqual(instance.current_step, 1)

        self.assertEqual(
            WorkflowTask.objects.filter(instance=instance, step=step, status='PENDING').count(),
            1,
            '应仅剩最后一位会签人未处理',
        )

        # 第三人通过 —— 会签满足，唯一步骤 => 实例完成
        ok, msg = WorkflowService.approve_task(tasks[2], tasks[2].assignee)
        self.assertTrue(ok, msg)
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'APPROVED')
        self.assertEqual(
            WorkflowTask.objects.filter(instance=instance, step=step, status='APPROVED').count(),
            3,
        )

    # ---------- (b) 任意拒绝 => 整单拒绝，其余待办 SKIPPED ----------
    def test_countersign_single_rejection_rejects_instance(self):
        wf, step = self._make_countersign_workflow('cs_wf_c')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 1003, 'PR-CS-C', self.submitter
        )

        tasks = list(
            WorkflowTask.objects.filter(instance=instance, step=step).order_by('id')
        )
        self.assertEqual(len(tasks), 3)

        # 第一人通过，第二人拒绝
        ok, _ = WorkflowService.approve_task(tasks[0], tasks[0].assignee)
        self.assertTrue(ok)
        ok, _ = WorkflowService.reject_task(tasks[1], tasks[1].assignee, comment='不同意')
        self.assertTrue(ok)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'REJECTED')

        tasks[1].refresh_from_db()
        self.assertEqual(tasks[1].status, 'REJECTED')

        # 尚未处理的第三个任务应被取消（SKIPPED），不再遗留待办
        tasks[2].refresh_from_db()
        self.assertEqual(tasks[2].status, 'SKIPPED')
        self.assertEqual(
            WorkflowTask.objects.filter(instance=instance, status='PENDING').count(), 0
        )

    # ---------- (c) 普通单人审批仍一人通过即推进（回归保护）----------
    def test_single_approver_step_advances_on_one_approval(self):
        wf = WorkflowDefinition.objects.create(
            name='两级单人审批', code='single_wf', business_type='PURCHASE_REQUEST', is_active=True
        )
        approver1 = User.objects.create_user(
            username='appr1', password='x', employee_id='appr1'
        )
        approver2 = User.objects.create_user(
            username='appr2', password='x', employee_id='appr2'
        )
        step1 = WorkflowStep.objects.create(
            workflow=wf, step_order=1, name='一级', approver_type='USER',
            approver_user=approver1, action_type='APPROVE',
        )
        WorkflowStep.objects.create(
            workflow=wf, step_order=2, name='二级', approver_type='USER',
            approver_user=approver2, action_type='APPROVE',
        )

        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 2001, 'PR-SINGLE', self.submitter
        )

        # 第一步只建 1 个任务
        step1_tasks = WorkflowTask.objects.filter(instance=instance, step=step1)
        self.assertEqual(step1_tasks.count(), 1)

        # 一人通过 -> 推进到第 2 步，新建第 2 步任务，实例仍在审批中
        t1 = step1_tasks.first()
        ok, msg = WorkflowService.approve_task(t1, approver1)
        self.assertTrue(ok, msg)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'PENDING')
        self.assertEqual(instance.current_step, 2)
        self.assertEqual(
            WorkflowTask.objects.filter(
                instance=instance, step__step_order=2, status='PENDING'
            ).count(),
            1,
        )

        # 第 2 步一人通过 -> 整单完成
        t2 = WorkflowTask.objects.get(instance=instance, step__step_order=2)
        ok, msg = WorkflowService.approve_task(t2, approver2)
        self.assertTrue(ok, msg)
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'APPROVED')

    def test_normal_step_creates_only_one_task_for_role(self):
        """回归：ROLE 审批人 + 非会签 action_type 仍只建 1 个任务（不误伤普通审批）。"""
        wf = WorkflowDefinition.objects.create(
            name='角色单审', code='role_single_wf', business_type='PURCHASE_REQUEST', is_active=True
        )
        step = WorkflowStep.objects.create(
            workflow=wf, step_order=1, name='角色审核', approver_type='ROLE',
            approver_role=self.role_cs, action_type='APPROVE',
        )
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 3001, 'PR-ROLE-SINGLE', self.submitter
        )
        self.assertEqual(
            WorkflowTask.objects.filter(instance=instance, step=step).count(),
            1,
            '角色审批但非会签时应退回单人审批语义（1 个任务）',
        )
