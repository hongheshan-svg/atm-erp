"""
Initialize default workflow definitions for all modules.
"""

from django.core.management.base import BaseCommand

from apps.accounts.models import Role
from apps.core.permission_models_new import DataScope
from apps.core.workflow.models import WorkflowDefinition, WorkflowStep


def ensure_default_scope(role, scope_type):
    scope_map = {
        'ALL': 'all',
        'DEPARTMENT': 'dept_tree',
        'SELF': 'self',
    }
    DataScope.objects.filter(role=role, module='__default__').delete()
    scope, _ = DataScope.objects.update_or_create(
        role=role, module='', defaults={'scope_type': scope_map.get(scope_type, 'self')}
    )
    scope.custom_departments.clear()


class Command(BaseCommand):
    help = 'Initialize default workflow definitions for all modules'

    def _resolve_role(self, canonical_code, legacy_code, legacy_name, scope_type):
        """优先复用 init_roles 建立的正式角色，没有时才退回本命令的历史角色。

        审批人兜底靠「角色里第一个在职用户」解析。真实用户挂的是 init_roles 的角色
        （purchase_manager / finance_manager ...），若这里仍指向历史大写角色
        （PURCHASE / FINANCE ...），角色里一个人都没有，兜底链等于没接上。
        """
        role = Role.objects.filter(code=canonical_code, is_deleted=False).first()
        if role:
            return role
        role, _ = Role.objects.get_or_create(code=legacy_code, defaults={'name': legacy_name, 'permissions': {}})
        ensure_default_scope(role, scope_type)
        return role

    def handle(self, *args, **options):
        self.stdout.write('Creating default workflows for all modules...')

        # Get or create roles
        finance_role = self._resolve_role('finance_manager', 'FINANCE', '财务', 'ALL')
        manager_role = self._resolve_role('project_manager', 'MANAGER', '经理', 'DEPARTMENT')
        sales_role = self._resolve_role('sales_manager', 'SALES', '销售', 'SELF')
        purchase_role = self._resolve_role('purchase_manager', 'PURCHASE', '采购', 'SELF')
        admin_role = self._resolve_role('general_manager', 'ADMIN', '管理员', 'ALL')
        hr_role = self._resolve_role('hr_admin', 'HR', '人事', 'ALL')
        warehouse_role = self._resolve_role('warehouse_manager', 'WAREHOUSE', '仓库', 'DEPARTMENT')

        # ============ 采购管理模块 ============
        self._create_purchase_request_workflows(finance_role, admin_role, manager_role)
        self._create_purchase_order_workflows(finance_role, admin_role, purchase_role)

        # ============ 销售管理模块 ============
        self._create_quotation_workflows(sales_role, finance_role, admin_role)
        self._create_sales_order_workflows(finance_role, admin_role, sales_role)
        self._create_sales_contract_workflows(finance_role, admin_role, sales_role)
        self._create_delivery_order_workflows(finance_role, admin_role, warehouse_role)

        # ============ 财务管理模块 ============
        self._create_expense_workflows(finance_role, admin_role, manager_role)
        self._create_payment_workflows(finance_role, admin_role)

        # ============ 项目管理模块 ============
        self._create_project_workflows(finance_role, admin_role, manager_role)
        self._create_ecn_workflows(finance_role, admin_role, manager_role)

        # ============ 库存管理模块 ============
        self._create_stock_adjustment_workflows(finance_role, warehouse_role)

        # ============ OA办公模块 ============
        self._create_leave_request_workflows(hr_role, admin_role, manager_role)
        self._create_overtime_request_workflows(hr_role, admin_role, manager_role)
        self._create_vehicle_request_workflows(admin_role, manager_role)
        self._create_asset_borrow_workflows(admin_role, manager_role)

        self._backfill_dynamic_approver_roles(
            {
                '采购': purchase_role,
                '销售': sales_role,
                '项目': manager_role,
                '财务': finance_role,
                '仓库': warehouse_role,
                '部门经理': manager_role,
            },
            default_role=admin_role,
        )

        self.stdout.write(self.style.SUCCESS('Workflow initialization complete!'))

    def _backfill_dynamic_approver_roles(self, keyword_roles, default_role):
        """给已存在的动态审批人步骤补上 approver_role 兜底。

        上面的建流程逻辑都是 ``if created:``，只对空库生效；线上库里那些没配
        approver_role 的历史步骤（以及用户在界面上自建的流程）不会被覆盖，提交单据
        照样报「无法确定审批人」。这里按步骤名关键字补一个兜底角色，找不到关键字就用
        默认的最高权限角色，保证兜底链一定能落到人。
        """
        pending = WorkflowStep.objects.filter(
            approver_type__in=('DEPARTMENT_MANAGER', 'PROJECT_MANAGER', 'SUPERIOR'),
            approver_role__isnull=True,
            is_deleted=False,
        ).select_related('workflow')

        fixed = 0
        for step in pending:
            role = next((r for kw, r in keyword_roles.items() if kw in step.name), default_role)
            step.approver_role = role
            step.save(update_fields=['approver_role', 'updated_at'])
            fixed += 1
            self.stdout.write(f'  Backfilled approver_role: {step.workflow.code}/{step.name} -> {role.name}')

        if fixed:
            self.stdout.write(self.style.SUCCESS(f'  补齐 {fixed} 个动态审批步骤的兜底审批角色'))

    # ============ 采购管理 ============
    def _create_purchase_request_workflows(self, finance_role, admin_role, manager_role):
        """采购申请审批流程"""
        # 小额采购申请
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='PR_SMALL',
            defaults={
                'name': '采购申请审批(小额)',
                'business_type': 'PURCHASE_REQUEST',
                'description': '金额小于10000的采购申请，仅需部门经理审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

        # 大额采购申请
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='PR_LARGE',
            defaults={
                'name': '采购申请审批(大额)',
                'business_type': 'PURCHASE_REQUEST',
                'description': '金额≥10000的采购申请，需项目经理、财务和总经理审批',
                'is_active': True,
                'amount_threshold': 10000,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='项目经理审批',
                approver_type='PROJECT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='财务审批',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=3,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    def _create_purchase_order_workflows(self, finance_role, admin_role, purchase_role):
        """采购订单审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='PO_DEFAULT',
            defaults={
                'name': '采购订单审批',
                'business_type': 'PURCHASE_ORDER',
                'description': '采购订单需经过审批后才能发给供应商',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='采购经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=purchase_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='财务确认',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    # ============ 销售管理 ============
    def _create_quotation_workflows(self, sales_role, finance_role, admin_role):
        """销售报价审批流程"""
        # 小额报价
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='QUOT_SMALL',
            defaults={
                'name': '销售报价审批(小额)',
                'business_type': 'QUOTATION',
                'description': '金额小于50000的报价，仅需销售经理审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=sales_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

        # 大额报价
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='QUOT_LARGE',
            defaults={
                'name': '销售报价审批(大额)',
                'business_type': 'QUOTATION',
                'description': '金额≥50000的报价，需销售经理和总经理审批',
                'is_active': True,
                'amount_threshold': 50000,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=sales_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    def _create_sales_order_workflows(self, finance_role, admin_role, sales_role):
        """销售订单审批流程"""
        # 小额订单
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='SO_SMALL',
            defaults={
                'name': '销售订单审批(小额)',
                'business_type': 'SALES_ORDER',
                'description': '金额小于50000的销售订单，仅需销售经理审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=sales_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

        # 大额订单
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='SO_LARGE',
            defaults={
                'name': '销售订单审批(大额)',
                'business_type': 'SALES_ORDER',
                'description': '金额≥50000的销售订单，需销售经理、财务和总经理审批',
                'is_active': True,
                'amount_threshold': 50000,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=sales_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='财务审批',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=3,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    def _create_sales_contract_workflows(self, finance_role, admin_role, sales_role):
        """销售合同审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='CONTRACT_DEFAULT',
            defaults={
                'name': '销售合同审批',
                'business_type': 'SALES_CONTRACT',
                'description': '所有销售合同需经过审批流程',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=sales_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='财务审核',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=3,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    def _create_delivery_order_workflows(self, finance_role, admin_role, warehouse_role):
        """发货单审批流程"""
        # 小额发货
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='DO_SMALL',
            defaults={
                'name': '发货单审批(小额)',
                'business_type': 'DELIVERY_ORDER',
                'description': '金额小于50000的发货单，仅需仓库主管确认',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='仓库主管确认',
                approver_type='ROLE',
                approver_role=warehouse_role,
                action_type='APPROVE',
                timeout_hours=12,
            )
            self.stdout.write(f'  Created: {workflow.name}')

        # 大额发货
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='DO_LARGE',
            defaults={
                'name': '发货单审批(大额)',
                'business_type': 'DELIVERY_ORDER',
                'description': '金额≥50000的发货单，需仓库主管、财务和总经理审批',
                'is_active': True,
                'amount_threshold': 50000,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='仓库主管确认',
                approver_type='ROLE',
                approver_role=warehouse_role,
                action_type='APPROVE',
                timeout_hours=12,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='财务审核',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=3,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    # ============ 财务管理 ============
    def _create_expense_workflows(self, finance_role, admin_role, manager_role):
        """费用报销审批流程"""
        # 小额报销
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='EXP_SMALL',
            defaults={
                'name': '费用报销审批(小额)',
                'business_type': 'EXPENSE',
                'description': '金额小于5000的费用报销，仅需部门经理审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

        # 大额报销
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='EXP_LARGE',
            defaults={
                'name': '费用报销审批(大额)',
                'business_type': 'EXPENSE',
                'description': '金额≥5000的费用报销，需部门经理、财务和总经理审批',
                'is_active': True,
                'amount_threshold': 5000,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='财务审批',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=3,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    def _create_payment_workflows(self, finance_role, admin_role):
        """付款申请审批流程"""
        # 小额付款
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='PAY_SMALL',
            defaults={
                'name': '付款申请审批(小额)',
                'business_type': 'PAYMENT',
                'description': '金额小于50000的付款申请，仅需财务审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='财务审批',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

        # 大额付款
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='PAY_LARGE',
            defaults={
                'name': '付款申请审批(大额)',
                'business_type': 'PAYMENT',
                'description': '金额≥50000的付款申请，需财务和总经理审批',
                'is_active': True,
                'amount_threshold': 50000,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='财务审批',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    # ============ 项目管理 ============
    def _create_project_workflows(self, finance_role, admin_role, manager_role):
        """项目立项审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='PROJECT_APPROVAL',
            defaults={
                'name': '项目立项审批',
                'business_type': 'PROJECT',
                'description': '所有项目立项需经过审批流程',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='项目经理确认',
                approver_type='PROJECT_MANAGER',
                approver_role=manager_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='财务预算审核',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='REVIEW',
                timeout_hours=48,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=3,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=72,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    def _create_ecn_workflows(self, finance_role, admin_role, manager_role):
        """工程变更审批流程"""
        # 小额变更
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='ECN_SMALL',
            defaults={
                'name': '工程变更审批(小额)',
                'business_type': 'ECN',
                'description': '成本影响小于10000的工程变更，仅需项目经理审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='项目经理审批',
                approver_type='PROJECT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

        # 大额变更
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='ECN_LARGE',
            defaults={
                'name': '工程变更审批(大额)',
                'business_type': 'ECN',
                'description': '成本影响≥10000的工程变更，需项目经理、财务和总经理审批',
                'is_active': True,
                'amount_threshold': 10000,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='项目经理审批',
                approver_type='PROJECT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='财务审核',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=3,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    # ============ 库存管理 ============
    def _create_stock_adjustment_workflows(self, finance_role, warehouse_role):
        """库存调整审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='STOCK_ADJUST',
            defaults={
                'name': '库存调整审批',
                'business_type': 'STOCK_ADJUSTMENT',
                'description': '库存盘点调整需审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='仓库主管审批',
                approver_type='ROLE',
                approver_role=warehouse_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='财务确认',
                approver_type='ROLE',
                approver_role=finance_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    # ============ OA办公 ============
    def _create_leave_request_workflows(self, hr_role, admin_role, manager_role):
        """请假申请审批流程"""
        # 短期请假（3天以内）
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='LEAVE_SHORT',
            defaults={
                'name': '请假申请审批(短期)',
                'business_type': 'LEAVE_REQUEST',
                'description': '3天以内的请假，仅需部门经理审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

        # 长期请假（超过3天）
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='LEAVE_LONG',
            defaults={
                'name': '请假申请审批(长期)',
                'business_type': 'LEAVE_REQUEST',
                'description': '超过3天的请假，需部门经理、HR和总经理审批',
                'is_active': True,
                'amount_threshold': 3,  # 使用amount_threshold存储天数
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='HR审核',
                approver_type='ROLE',
                approver_role=hr_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=3,
                name='总经理审批',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    def _create_overtime_request_workflows(self, hr_role, admin_role, manager_role):
        """加班申请审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='OVERTIME_DEFAULT',
            defaults={
                'name': '加班申请审批',
                'business_type': 'OVERTIME_REQUEST',
                'description': '加班申请需经过审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='HR备案',
                approver_type='ROLE',
                approver_role=hr_role,
                action_type='REVIEW',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    def _create_vehicle_request_workflows(self, admin_role, manager_role):
        """用车申请审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='VEHICLE_DEFAULT',
            defaults={
                'name': '用车申请审批',
                'business_type': 'VEHICLE_REQUEST',
                'description': '用车申请需经过审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=12,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='行政确认',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=12,
            )
            self.stdout.write(f'  Created: {workflow.name}')

    def _create_asset_borrow_workflows(self, admin_role, manager_role):
        """资产借用审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='ASSET_BORROW_DEFAULT',
            defaults={
                'name': '资产借用审批',
                'business_type': 'ASSET_BORROW',
                'description': '资产借用申请需经过审批',
                'is_active': True,
                'amount_threshold': None,
            },
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=1,
                name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER',
                approver_role=manager_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow,
                step_order=2,
                name='行政确认',
                approver_type='ROLE',
                approver_role=admin_role,
                action_type='APPROVE',
                timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')
