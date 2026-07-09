"""
或签 (OR_SIGN) 语义测试：任意一人通过即满足步骤。

与会签 (COUNTERSIGN) 互为镜像：
  - 会签：全部通过才推进；任意一人拒绝即整单拒绝。
  - 或签：第一人通过即推进，其余待办被置为 SKIPPED；单人拒绝不整单拒绝
          （其余待办保持 PENDING），仅当全部人都拒绝（最后一个待办被拒）才整单拒绝。

本测试覆盖：
  (a) 3 人或签步骤创建 3 个任务，第一人通过即推进/完成，其余 2 个被置为 SKIPPED；
  (b) 单人拒绝不导致整单拒绝，其余待办保持 PENDING；
  (c) 3 人全部拒绝时整单拒绝；
  (d) 会签仍需全部通过才推进（回归保护，确保 OR_SIGN 未污染 COUNTERSIGN 路径）。
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Role
from apps.core.workflow.models import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowTask,
)
from apps.core.workflow.services import WorkflowService

User = get_user_model()


class WorkflowOrSignTest(TestCase):
    def setUp(self):
        # 隔离引擎外的副作用：通知 / 业务对象回填不属于本测试关注点。
        p1 = patch.object(WorkflowService, '_notify_assignee', return_value=None)
        p2 = patch.object(WorkflowService, '_on_workflow_complete', return_value=None)
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)

        self.submitter = User.objects.create_user(
            username='os_submitter', password='x', employee_id='os_submitter'
        )

        # 或签角色 + 3 名成员
        self.role_os = Role.objects.create(name='或签组', code='orsign_group')
        self.os_users = []
        for i in range(3):
            u = User.objects.create_user(
                username=f'os_member_{i}', password='x', employee_id=f'os_member_{i}'
            )
            u.roles.add(self.role_os)
            self.os_users.append(u)

    # ---------- helpers ----------
    def _make_orsign_workflow(self, code):
        wf = WorkflowDefinition.objects.create(
            name='或签流程', code=code, business_type='PURCHASE_REQUEST', is_active=True
        )
        step = WorkflowStep.objects.create(
            workflow=wf,
            step_order=1,
            name='部门或签',
            approver_type='ROLE',
            approver_role=self.role_os,
            action_type='OR_SIGN',
        )
        return wf, step

    # ---------- (a) 或签：3 任务，第一人通过即推进，其余 SKIPPED ----------
    def test_orsign_creates_task_per_assignee(self):
        wf, step = self._make_orsign_workflow('os_wf_a')
        instance, err = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 4001, 'PR-OS-A', self.submitter
        )
        self.assertIsNone(err)
        self.assertIsNotNone(instance)

        tasks = WorkflowTask.objects.filter(instance=instance, step=step)
        self.assertEqual(tasks.count(), 3, '或签步骤应为每位候选审批人各建 1 个任务')
        self.assertEqual(tasks.filter(status='PENDING').count(), 3)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'PENDING')
        self.assertEqual(instance.current_step, 1)

    def test_orsign_first_approval_advances_and_skips_siblings(self):
        wf, step = self._make_orsign_workflow('os_wf_a2')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 4002, 'PR-OS-A2', self.submitter
        )

        tasks = list(
            WorkflowTask.objects.filter(instance=instance, step=step).order_by('id')
        )
        self.assertEqual(len(tasks), 3)

        # 第一人通过 —— 或签满足，唯一步骤 => 实例完成
        ok, msg = WorkflowService.approve_task(tasks[0], tasks[0].assignee)
        self.assertTrue(ok, msg)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'APPROVED')

        # 通过者标记 APPROVED，其余两个待办被置为 SKIPPED（不再遗留待办）
        tasks[0].refresh_from_db()
        self.assertEqual(tasks[0].status, 'APPROVED')
        for t in tasks[1:]:
            t.refresh_from_db()
            self.assertEqual(t.status, 'SKIPPED')
        self.assertEqual(
            WorkflowTask.objects.filter(instance=instance, status='PENDING').count(), 0
        )

        # 已被 SKIPPED 的兄弟任务再次审批应被拒绝（并发/重复处理护栏）
        ok2, _ = WorkflowService.approve_task(tasks[1], tasks[1].assignee)
        self.assertFalse(ok2, '已跳过的兄弟任务不应能被再次审批推进')

    # ---------- (b) 单人拒绝不整单拒绝，其余待办保持 PENDING ----------
    def test_orsign_single_rejection_does_not_reject_instance(self):
        wf, step = self._make_orsign_workflow('os_wf_b')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 4003, 'PR-OS-B', self.submitter
        )

        tasks = list(
            WorkflowTask.objects.filter(instance=instance, step=step).order_by('id')
        )
        self.assertEqual(len(tasks), 3)

        # 第一人拒绝 —— 或签下不应整单拒绝，其余两人仍可审批
        ok, msg = WorkflowService.reject_task(tasks[0], tasks[0].assignee, comment='不同意')
        self.assertTrue(ok, msg)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'PENDING', '或签单人拒绝不应整单拒绝')
        self.assertEqual(instance.current_step, 1)

        tasks[0].refresh_from_db()
        self.assertEqual(tasks[0].status, 'REJECTED')

        # 其余兄弟任务保持 PENDING（不被 SKIPPED）
        self.assertEqual(
            WorkflowTask.objects.filter(instance=instance, step=step, status='PENDING').count(),
            2,
            '或签单人拒绝后其余候选审批人应仍待处理',
        )

        # 且此时另一人仍可通过并推进整单
        remaining = WorkflowTask.objects.filter(
            instance=instance, step=step, status='PENDING'
        ).order_by('id').first()
        ok2, msg2 = WorkflowService.approve_task(remaining, remaining.assignee)
        self.assertTrue(ok2, msg2)
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'APPROVED', '拒绝后剩余审批人通过应能推进整单')

    # ---------- (c) 全部拒绝 => 整单拒绝 ----------
    def test_orsign_all_rejections_reject_instance(self):
        wf, step = self._make_orsign_workflow('os_wf_c')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 4004, 'PR-OS-C', self.submitter
        )

        tasks = list(
            WorkflowTask.objects.filter(instance=instance, step=step).order_by('id')
        )
        self.assertEqual(len(tasks), 3)

        # 前两人拒绝 —— 仍不整单拒绝（还有人可以通过）
        for t in tasks[:2]:
            ok, msg = WorkflowService.reject_task(t, t.assignee, comment='不同意')
            self.assertTrue(ok, msg)
            instance.refresh_from_db()
            self.assertEqual(instance.status, 'PENDING')
            self.assertEqual(instance.current_step, 1)

        # 第三人（最后一个待办）拒绝 —— 全员拒绝 => 整单拒绝
        ok, msg = WorkflowService.reject_task(tasks[2], tasks[2].assignee, comment='不同意')
        self.assertTrue(ok, msg)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'REJECTED', '全部候选审批人拒绝后应整单拒绝')

        self.assertEqual(
            WorkflowTask.objects.filter(instance=instance, step=step, status='REJECTED').count(),
            3,
        )
        self.assertEqual(
            WorkflowTask.objects.filter(instance=instance, status='PENDING').count(), 0
        )

    # ---------- (d) 会签仍需全部通过才推进（回归保护）----------
    def test_countersign_still_requires_all_approvals(self):
        wf = WorkflowDefinition.objects.create(
            name='会签回归', code='os_cs_regression', business_type='PURCHASE_REQUEST', is_active=True
        )
        # 复用或签组角色作为会签角色
        step = WorkflowStep.objects.create(
            workflow=wf,
            step_order=1,
            name='部门会签',
            approver_type='ROLE',
            approver_role=self.role_os,
            action_type='COUNTERSIGN',
        )
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST', 4005, 'PR-OS-CS', self.submitter
        )

        tasks = list(
            WorkflowTask.objects.filter(instance=instance, step=step).order_by('id')
        )
        self.assertEqual(len(tasks), 3, '会签步骤仍应为每位会签人各建 1 个任务')

        # 前两人通过 —— 会签下仍不得推进 / 完成
        for t in tasks[:2]:
            ok, msg = WorkflowService.approve_task(t, t.assignee)
            self.assertTrue(ok, msg)
            instance.refresh_from_db()
            self.assertEqual(instance.status, 'PENDING', '会签未全部通过前不应推进')
            self.assertEqual(instance.current_step, 1)
            # 会签不得像或签那样把其余待办置为 SKIPPED
            self.assertEqual(
                WorkflowTask.objects.filter(instance=instance, step=step, status='SKIPPED').count(),
                0,
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
