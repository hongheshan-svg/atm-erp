"""
Initialize default workflow definitions for all modules.
"""
from django.core.management.base import BaseCommand
from apps.core.workflow.models import WorkflowDefinition, WorkflowStep
from apps.accounts.models import Role


class Command(BaseCommand):
    help = 'Initialize default workflow definitions for all modules'

    def handle(self, *args, **options):
        self.stdout.write('Creating default workflows for all modules...')
        
        # Get or create roles
        finance_role, _ = Role.objects.get_or_create(
            code='FINANCE',
            defaults={'name': '财务', 'data_scope': 'ALL'}
        )
        manager_role, _ = Role.objects.get_or_create(
            code='MANAGER',
            defaults={'name': '经理', 'data_scope': 'DEPARTMENT'}
        )
        sales_role, _ = Role.objects.get_or_create(
            code='SALES',
            defaults={'name': '销售', 'data_scope': 'SELF'}
        )
        purchase_role, _ = Role.objects.get_or_create(
            code='PURCHASE',
            defaults={'name': '采购', 'data_scope': 'SELF'}
        )
        admin_role, _ = Role.objects.get_or_create(
            code='ADMIN',
            defaults={'name': '管理员', 'data_scope': 'ALL'}
        )
        hr_role, _ = Role.objects.get_or_create(
            code='HR',
            defaults={'name': '人事', 'data_scope': 'ALL'}
        )
        warehouse_role, _ = Role.objects.get_or_create(
            code='WAREHOUSE',
            defaults={'name': '仓库', 'data_scope': 'DEPARTMENT'}
        )
        
        # ============ 采购管理模块 ============
        self._create_purchase_request_workflows(finance_role, admin_role)
        self._create_purchase_order_workflows(finance_role, admin_role)
        
        # ============ 销售管理模块 ============
        self._create_quotation_workflows(sales_role, finance_role, admin_role)
        self._create_sales_order_workflows(finance_role, admin_role)
        self._create_sales_contract_workflows(finance_role, admin_role)
        self._create_delivery_order_workflows(finance_role, admin_role, warehouse_role)
        
        # ============ 财务管理模块 ============
        self._create_expense_workflows(finance_role, admin_role)
        self._create_payment_workflows(finance_role, admin_role)
        
        # ============ 项目管理模块 ============
        self._create_project_workflows(finance_role, admin_role)
        self._create_ecn_workflows(finance_role, admin_role)
        
        # ============ 库存管理模块 ============
        self._create_stock_adjustment_workflows(finance_role, warehouse_role)
        
        # ============ OA办公模块 ============
        self._create_leave_request_workflows(hr_role, admin_role)
        self._create_overtime_request_workflows(hr_role, admin_role)
        self._create_vehicle_request_workflows(admin_role)
        self._create_asset_borrow_workflows(admin_role)
        
        self.stdout.write(self.style.SUCCESS('Workflow initialization complete!'))
    
    # ============ 采购管理 ============
    def _create_purchase_request_workflows(self, finance_role, admin_role):
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='项目经理审批',
                approver_type='PROJECT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='财务审批',
                approver_type='ROLE', approver_role=finance_role, action_type='REVIEW', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=3, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    def _create_purchase_order_workflows(self, finance_role, admin_role):
        """采购订单审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='PO_DEFAULT',
            defaults={
                'name': '采购订单审批',
                'business_type': 'PURCHASE_ORDER',
                'description': '采购订单需经过审批后才能发给供应商',
                'is_active': True,
                'amount_threshold': None,
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='采购经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='财务确认',
                approver_type='ROLE', approver_role=finance_role, action_type='REVIEW', timeout_hours=24,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    def _create_sales_order_workflows(self, finance_role, admin_role):
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='财务审批',
                approver_type='ROLE', approver_role=finance_role, action_type='REVIEW', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=3, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    def _create_sales_contract_workflows(self, finance_role, admin_role):
        """销售合同审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='CONTRACT_DEFAULT',
            defaults={
                'name': '销售合同审批',
                'business_type': 'SALES_CONTRACT',
                'description': '所有销售合同需经过审批流程',
                'is_active': True,
                'amount_threshold': None,
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='销售经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='财务审核',
                approver_type='ROLE', approver_role=finance_role, action_type='REVIEW', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=3, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=48,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='仓库主管确认',
                approver_type='ROLE', approver_role=warehouse_role, action_type='APPROVE', timeout_hours=12,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='仓库主管确认',
                approver_type='ROLE', approver_role=warehouse_role, action_type='APPROVE', timeout_hours=12,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='财务审核',
                approver_type='ROLE', approver_role=finance_role, action_type='REVIEW', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=3, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    # ============ 财务管理 ============
    def _create_expense_workflows(self, finance_role, admin_role):
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='财务审批',
                approver_type='ROLE', approver_role=finance_role, action_type='REVIEW', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=3, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=48,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='财务审批',
                approver_type='ROLE', approver_role=finance_role, action_type='APPROVE', timeout_hours=24,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='财务审批',
                approver_type='ROLE', approver_role=finance_role, action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    # ============ 项目管理 ============
    def _create_project_workflows(self, finance_role, admin_role):
        """项目立项审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='PROJECT_APPROVAL',
            defaults={
                'name': '项目立项审批',
                'business_type': 'PROJECT',
                'description': '所有项目立项需经过审批流程',
                'is_active': True,
                'amount_threshold': None,
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='项目经理确认',
                approver_type='PROJECT_MANAGER', action_type='REVIEW', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='财务预算审核',
                approver_type='ROLE', approver_role=finance_role, action_type='REVIEW', timeout_hours=48,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=3, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=72,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    def _create_ecn_workflows(self, finance_role, admin_role):
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='项目经理审批',
                approver_type='PROJECT_MANAGER', action_type='APPROVE', timeout_hours=24,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='项目经理审批',
                approver_type='PROJECT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='财务审核',
                approver_type='ROLE', approver_role=finance_role, action_type='REVIEW', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=3, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=48,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='仓库主管审批',
                approver_type='ROLE', approver_role=warehouse_role, action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='财务确认',
                approver_type='ROLE', approver_role=finance_role, action_type='REVIEW', timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    # ============ OA办公 ============
    def _create_leave_request_workflows(self, hr_role, admin_role):
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
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
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='HR审核',
                approver_type='ROLE', approver_role=hr_role, action_type='REVIEW', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=3, name='总经理审批',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=48,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    def _create_overtime_request_workflows(self, hr_role, admin_role):
        """加班申请审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='OVERTIME_DEFAULT',
            defaults={
                'name': '加班申请审批',
                'business_type': 'OVERTIME_REQUEST',
                'description': '加班申请需经过审批',
                'is_active': True,
                'amount_threshold': None,
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='HR备案',
                approver_type='ROLE', approver_role=hr_role, action_type='REVIEW', timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    def _create_vehicle_request_workflows(self, admin_role):
        """用车申请审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='VEHICLE_DEFAULT',
            defaults={
                'name': '用车申请审批',
                'business_type': 'VEHICLE_REQUEST',
                'description': '用车申请需经过审批',
                'is_active': True,
                'amount_threshold': None,
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=12,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='行政确认',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=12,
            )
            self.stdout.write(f'  Created: {workflow.name}')
    
    def _create_asset_borrow_workflows(self, admin_role):
        """资产借用审批流程"""
        workflow, created = WorkflowDefinition.objects.get_or_create(
            code='ASSET_BORROW_DEFAULT',
            defaults={
                'name': '资产借用审批',
                'business_type': 'ASSET_BORROW',
                'description': '资产借用申请需经过审批',
                'is_active': True,
                'amount_threshold': None,
            }
        )
        if created:
            WorkflowStep.objects.create(
                workflow=workflow, step_order=1, name='部门经理审批',
                approver_type='DEPARTMENT_MANAGER', action_type='APPROVE', timeout_hours=24,
            )
            WorkflowStep.objects.create(
                workflow=workflow, step_order=2, name='行政确认',
                approver_type='ROLE', approver_role=admin_role, action_type='APPROVE', timeout_hours=24,
            )
            self.stdout.write(f'  Created: {workflow.name}')
