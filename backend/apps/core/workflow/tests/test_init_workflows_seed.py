"""init_workflows 种子数据的可解析性约束。

动态审批人（部门经理/项目经理/直属上级）在组织数据不全时会解析不出人，
此时 WorkflowService._get_step_assignee 会回退到步骤的 approver_role。
若种子步骤没配 approver_role，这条兜底链就是断的，提交单据必然抛
「无法确定审批人」——线上采购订单提交 500 即由此而来。
"""

from django.core.management import call_command
from django.test import TestCase

from apps.core.workflow.models import WorkflowStep

# 审批人靠运行时组织数据动态解析的类型，解析不到时必须有角色兜底
DYNAMIC_APPROVER_TYPES = ('DEPARTMENT_MANAGER', 'PROJECT_MANAGER', 'SUPERIOR')


class InitWorkflowsSeedTest(TestCase):
    def test_dynamic_approver_steps_all_have_role_fallback(self):
        call_command('init_workflows')

        unresolvable = [
            f'{step.workflow.code}/{step.name}({step.approver_type})'
            for step in WorkflowStep.objects.filter(approver_type__in=DYNAMIC_APPROVER_TYPES).select_related('workflow')
            if step.approver_role_id is None
        ]

        self.assertEqual(
            unresolvable,
            [],
            f'动态审批人步骤缺少 approver_role 兜底，组织数据不全时会导致提交单据报「无法确定审批人」: {unresolvable}',
        )
