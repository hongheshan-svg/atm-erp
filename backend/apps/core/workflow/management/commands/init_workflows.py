"""
Initialize default workflow definitions.
"""
from django.core.management.base import BaseCommand
from apps.core.workflow.models import WorkflowDefinition, WorkflowStep
from apps.accounts.models import Role


class Command(BaseCommand):
    help = 'Initialize default workflow definitions'

    def handle(self, *args, **options):
        self.stdout.write('Creating default workflows...')
        
        # Get or create roles
        finance_role, _ = Role.objects.get_or_create(
            code='FINANCE',
            defaults={'name': '财务', 'data_scope': 'ALL'}
        )
        manager_role, _ = Role.objects.get_or_create(
            code='MANAGER',
            defaults={'name': '经理', 'data_scope': 'DEPARTMENT'}
        )
        
        # 1. Purchase Request Workflow (Small Amount)
        pr_workflow_small, created = WorkflowDefinition.objects.get_or_create(
            code='PR_SMALL',
            defaults={
                'name': '采购申请审批(小额)',
                'business_type': 'PURCHASE_REQUEST',
                'description': '金额小于10000的采购申请',
                'is_active': True,
                'amount_threshold': None,  # Default for small amounts
            }
        )
        
        if created:
            WorkflowStep.objects.create(
                workflow=pr_workflow_small,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {pr_workflow_small.name}')
        
        # 2. Purchase Request Workflow (Large Amount)
        pr_workflow_large, created = WorkflowDefinition.objects.get_or_create(
            code='PR_LARGE',
            defaults={
                'name': '采购申请审批(大额)',
                'business_type': 'PURCHASE_REQUEST',
                'description': '金额大于等于10000的采购申请',
                'is_active': True,
                'amount_threshold': 10000,
            }
        )
        
        if created:
            WorkflowStep.objects.create(
                workflow=pr_workflow_large,
                step_order=1,
                name='项目经理审批',
                approver_type='PROJECT_MANAGER',
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=pr_workflow_large,
                step_order=2,
                name='财务审批',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {pr_workflow_large.name}')
        
        # 3. Expense Workflow (Small Amount)
        exp_workflow_small, created = WorkflowDefinition.objects.get_or_create(
            code='EXP_SMALL',
            defaults={
                'name': '费用报销审批(小额)',
                'business_type': 'EXPENSE',
                'description': '金额小于5000的费用报销',
                'is_active': True,
                'amount_threshold': None,
            }
        )
        
        if created:
            WorkflowStep.objects.create(
                workflow=exp_workflow_small,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {exp_workflow_small.name}')
        
        # 4. Expense Workflow (Large Amount)
        exp_workflow_large, created = WorkflowDefinition.objects.get_or_create(
            code='EXP_LARGE',
            defaults={
                'name': '费用报销审批(大额)',
                'business_type': 'EXPENSE',
                'description': '金额大于等于5000的费用报销',
                'is_active': True,
                'amount_threshold': 5000,
            }
        )
        
        if created:
            WorkflowStep.objects.create(
                workflow=exp_workflow_large,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=exp_workflow_large,
                step_order=2,
                name='财务审批',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {exp_workflow_large.name}')
        
        self.stdout.write(self.style.SUCCESS('Workflow initialization complete!'))
