"""
Workflow service for managing approval processes.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from .models import WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowTask

logger = logging.getLogger(__name__)


class WorkflowService:
    """
    Service class for workflow operations.
    """
    
    @classmethod
    def get_workflow_for_business(cls, business_type, amount=None):
        """
        Get the appropriate workflow definition for a business type and amount.
        """
        workflows = WorkflowDefinition.objects.filter(
            business_type=business_type,
            is_active=True,
            is_deleted=False
        ).order_by('-amount_threshold')
        
        if amount is not None:
            # Find workflow with matching amount threshold
            for workflow in workflows:
                if workflow.amount_threshold is None or amount >= workflow.amount_threshold:
                    return workflow
        
        # Return first active workflow or None
        return workflows.first()
    
    @classmethod
    def start_workflow(cls, business_type, business_id, business_no, submitter, amount=None):
        """
        Start a new workflow instance for a business object.
        
        Returns:
            tuple: (WorkflowInstance, error_message)
        """
        workflow = cls.get_workflow_for_business(business_type, amount)
        
        if not workflow:
            return None, f"未找到适用于 {business_type} 的审批流程"
        
        with transaction.atomic():
            # Check if there's already an active workflow for this business object
            existing = WorkflowInstance.objects.select_for_update().filter(
                business_type=business_type,
                business_id=business_id,
                status='PENDING',
                is_deleted=False
            ).first()

            if existing:
                return None, "该单据已有进行中的审批流程"

            # Create workflow instance
            instance = WorkflowInstance.objects.create(
                workflow=workflow,
                business_type=business_type,
                business_id=business_id,
                business_no=business_no,
                submitter=submitter,
                amount=amount,
                status='PENDING',
                current_step=1,
                created_by=submitter
            )
            
            # Create first task
            cls._create_next_task(instance)
        
        return instance, None
    
    @classmethod
    def _create_next_task(cls, instance):
        """
        Create the next approval task for the workflow instance.
        """
        steps = instance.workflow.steps.filter(
            is_deleted=False
        ).order_by('step_order')
        
        current_step = None
        for step in steps:
            if step.step_order >= instance.current_step:
                # Check if step should be skipped based on amount
                if step.skip_amount_threshold and instance.amount:
                    if instance.amount < step.skip_amount_threshold:
                        continue
                current_step = step
                break
        
        if not current_step:
            # No more steps, workflow is complete
            instance.status = 'APPROVED'
            instance.completed_at = timezone.now()
            instance.save()
            cls._on_workflow_complete(instance, 'APPROVED')
            return None
        
        # Determine assignee
        assignee = cls._get_step_assignee(current_step, instance)
        
        if not assignee:
            logger.warning(f"No assignee found for step {current_step.id}")
            # Skip this step and try next (with depth guard to avoid infinite recursion)
            instance.current_step = current_step.step_order + 1
            instance.save()
            max_steps = instance.workflow.steps.count()
            if instance.current_step > max_steps:
                instance.status = 'APPROVED'
                instance.completed_at = timezone.now()
                instance.save()
                cls._on_workflow_complete(instance, 'APPROVED')
                return None
            return cls._create_next_task(instance)
        
        # Calculate deadline
        deadline = timezone.now() + timedelta(hours=current_step.timeout_hours)
        
        task = WorkflowTask.objects.create(
            instance=instance,
            step=current_step,
            assignee=assignee,
            status='PENDING',
            deadline=deadline,
            created_by=instance.submitter
        )
        
        # Send notification
        cls._notify_assignee(task)
        
        return task
    
    @classmethod
    def _get_step_assignee(cls, step, instance):
        """
        Determine the assignee for a workflow step.
        Falls back to approver_role if dynamic assignee is not found.
        """
        from apps.accounts.models import User
        
        assignee = None
        
        if step.approver_type == 'USER':
            assignee = step.approver_user
        
        elif step.approver_type == 'ROLE':
            if step.approver_role:
                # Get first active user with this role
                assignee = User.objects.filter(
                    roles=step.approver_role,
                    is_active=True,
                    is_deleted=False
                ).first()
        
        elif step.approver_type == 'DEPARTMENT_MANAGER':
            # Get submitter's department manager
            if instance.submitter.department and instance.submitter.department.manager:
                assignee = instance.submitter.department.manager
        
        elif step.approver_type == 'PROJECT_MANAGER':
            # Get project manager from business object
            assignee = cls._get_project_manager(instance)
        
        elif step.approver_type == 'SUPERIOR':
            # Get submitter's superior (department manager or higher)
            if instance.submitter.department and instance.submitter.department.manager:
                assignee = instance.submitter.department.manager
        
        # Fallback to approver_role if no assignee found
        if not assignee and step.approver_role:
            assignee = User.objects.filter(
                roles=step.approver_role,
                is_active=True,
                is_deleted=False
            ).first()
        
        # Last resort: use first superuser
        if not assignee:
            assignee = User.objects.filter(is_superuser=True, is_active=True).first()
        
        return assignee
    
    @classmethod
    def _get_project_manager(cls, instance):
        """
        Get project manager from the business object.
        Returns None if no project manager is associated.
        """
        try:
            if instance.business_type == 'PURCHASE_REQUEST':
                from apps.purchase.models import PurchaseRequest
                pr = PurchaseRequest.objects.get(id=instance.business_id)
                if pr.project:
                    return pr.project.manager
            
            elif instance.business_type == 'PURCHASE_ORDER':
                from apps.purchase.models import PurchaseOrder
                po = PurchaseOrder.objects.get(id=instance.business_id)
                if hasattr(po, 'project') and po.project:
                    return po.project.manager
            
            elif instance.business_type == 'EXPENSE':
                from apps.finance.models import Expense
                expense = Expense.objects.get(id=instance.business_id)
                if expense.project:
                    return expense.project.manager
            
            elif instance.business_type == 'PAYMENT':
                from apps.finance.models import PaymentRequest
                payment_req = PaymentRequest.objects.get(id=instance.business_id)
                if payment_req.project:
                    return payment_req.project.manager
            
            elif instance.business_type == 'QUOTATION':
                from apps.sales.models import SalesQuotation
                quot = SalesQuotation.objects.get(id=instance.business_id)
                if hasattr(quot, 'project') and quot.project:
                    return quot.project.manager
            
            elif instance.business_type == 'SALES_ORDER':
                from apps.sales.models import SalesOrder
                so = SalesOrder.objects.get(id=instance.business_id)
                if hasattr(so, 'project') and so.project:
                    return so.project.manager
            
            elif instance.business_type == 'SALES_CONTRACT':
                from apps.sales.models import SalesContract
                contract = SalesContract.objects.get(id=instance.business_id)
                if hasattr(contract, 'project') and contract.project:
                    return contract.project.manager
            
            elif instance.business_type == 'DELIVERY_ORDER':
                from apps.sales.models import DeliveryOrder
                delivery = DeliveryOrder.objects.get(id=instance.business_id)
                if delivery.so and hasattr(delivery.so, 'project') and delivery.so.project:
                    return delivery.so.project.manager
            
            elif instance.business_type == 'PROJECT':
                from apps.projects.models import Project
                project = Project.objects.get(id=instance.business_id)
                return project.manager
            
            elif instance.business_type == 'STOCK_ADJUSTMENT':
                # 库存调整没有项目经理，返回None
                return None
            
            elif instance.business_type == 'ECN':
                from apps.projects.models import ECN
                ecn = ECN.objects.get(id=instance.business_id)
                if ecn.project:
                    return ecn.project.manager
            
            elif instance.business_type == 'PURCHASE_CONTRACT':
                from apps.purchase.models import PurchaseContract
                contract = PurchaseContract.objects.get(id=instance.business_id)
                if contract.project:
                    return contract.project.manager

            elif instance.business_type in ['CONTRACT_EXECUTION', 'PAYMENT_RECORD']:
                from apps.purchase.contract_execution import ContractExecution
                if instance.business_type == 'CONTRACT_EXECUTION':
                    execution = ContractExecution.objects.get(id=instance.business_id)
                else:
                    from apps.purchase.contract_execution import PaymentRecord
                    payment = PaymentRecord.objects.get(id=instance.business_id)
                    execution = payment.execution
                if execution.contract and execution.contract.project:
                    return execution.contract.project.manager

            # 外协/售后/OA模块没有项目经理
            elif instance.business_type in [
                'OUTSOURCE_MATERIAL_ISSUE', 'OUTSOURCE_RECEIPT', 'SERVICE_REQUEST',
                'LEAVE_REQUEST', 'OVERTIME_REQUEST', 'VEHICLE_REQUEST', 'ASSET_BORROW'
            ]:
                return None
                
        except Exception as e:
            logger.error(f"Error getting project manager: {e}")
        
        return None
    
    @classmethod
    def approve_task(cls, task, user, comment='', skip_assignee_check=False):
        """
        Approve a workflow task.
        
        Args:
            skip_assignee_check: When True, skip the assignee verification.
                Used by business ViewSets that have their own permission checks.
        """
        if task.status != 'PENDING':
            return False, "该任务已处理"
        
        if not skip_assignee_check and task.assignee != user and not user.is_superuser:
            return False, "您没有权限处理此任务"
        
        with transaction.atomic():
            task.status = 'APPROVED'
            task.action_time = timezone.now()
            task.comment = comment
            task.updated_by = user
            task.save()
            
            # Move to next step
            instance = task.instance
            instance.current_step = task.step.step_order + 1
            instance.save()
            
            # Create next task or complete workflow
            cls._create_next_task(instance)
        
        return True, "审批通过"
    
    @classmethod
    def reject_task(cls, task, user, comment='', skip_assignee_check=False):
        """
        Reject a workflow task.
        
        Args:
            skip_assignee_check: When True, skip the assignee verification.
                Used by business ViewSets that have their own permission checks.
        """
        if task.status != 'PENDING':
            return False, "该任务已处理"
        
        if not skip_assignee_check and task.assignee != user and not user.is_superuser:
            return False, "您没有权限处理此任务"
        
        with transaction.atomic():
            task.status = 'REJECTED'
            task.action_time = timezone.now()
            task.comment = comment
            task.updated_by = user
            task.save()
            
            # Reject the entire workflow
            instance = task.instance
            instance.status = 'REJECTED'
            instance.completed_at = timezone.now()
            instance.save()
            
            cls._on_workflow_complete(instance, 'REJECTED')
        
        return True, "已拒绝"
    
    @classmethod
    def withdraw_workflow(cls, instance, user):
        """
        Withdraw a workflow instance (by submitter).
        """
        if instance.status != 'PENDING':
            return False, "只能撤回进行中的审批"
        
        if instance.submitter != user and not user.is_superuser:
            return False, "只有提交人可以撤回"
        
        with transaction.atomic():
            # Cancel all pending tasks
            instance.tasks.filter(status='PENDING').update(
                status='SKIPPED',
                action_time=timezone.now()
            )
            
            instance.status = 'WITHDRAWN'
            instance.completed_at = timezone.now()
            instance.save()
            
            cls._on_workflow_complete(instance, 'WITHDRAWN')
        
        return True, "已撤回"
    
    @classmethod
    def _on_workflow_complete(cls, instance, result):
        """
        Callback when workflow is completed.
        Updates the business object status.
        """
        try:
            if instance.business_type == 'PURCHASE_REQUEST':
                from apps.purchase.models import PurchaseRequest
                pr = PurchaseRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    pr.status = 'APPROVED'
                    # 更新BOM状态：PR_PENDING -> PR_APPROVED
                    from apps.projects.models import ProjectBOM
                    ProjectBOM.objects.filter(
                        purchase_request=pr,
                        is_deleted=False,
                        order_status='PR_PENDING'
                    ).update(order_status='PR_APPROVED')
                elif result == 'REJECTED':
                    pr.status = 'REJECTED'
                elif result == 'WITHDRAWN':
                    pr.status = 'DRAFT'
                pr.save()
            
            elif instance.business_type == 'EXPENSE':
                from apps.finance.models import Expense
                expense = Expense.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    expense.status = 'APPROVED'
                elif result == 'REJECTED':
                    expense.status = 'REJECTED'
                elif result == 'WITHDRAWN':
                    expense.status = 'DRAFT'
                expense.save()
            
            elif instance.business_type == 'DELIVERY_ORDER':
                from apps.sales.models import DeliveryOrder
                delivery = DeliveryOrder.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    # 审批通过，进入备货环节
                    delivery.status = 'PREPARING'
                    delivery.save()
                    logger.info(f"Delivery order {delivery.delivery_no} approved, entering PREPARING status")
                elif result == 'REJECTED':
                    delivery.status = 'REJECTED'
                    delivery.save()
                elif result == 'WITHDRAWN':
                    delivery.status = 'DRAFT'
                    delivery.save()
            
            elif instance.business_type == 'SALES_ORDER':
                from apps.sales.models import SalesOrder
                so = SalesOrder.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    so.status = 'CONFIRMED'  # 审批通过后确认订单
                    so.save()
                    # 与直接确认路径一致：生成应收账款与付款计划，避免审批确认的订单漏记 AR
                    try:
                        from apps.sales.services import create_sales_order_receivables
                        create_sales_order_receivables(so, getattr(instance, 'submitter', None) or so.created_by)
                    except Exception as e:
                        logger.error(f"销售订单 {so.order_no} 审批通过后创建应收/付款计划失败: {e}")
                    logger.info(f"Sales order {so.order_no} approved, status changed to CONFIRMED")
                elif result == 'REJECTED':
                    so.status = 'REJECTED'
                    so.save()
                elif result == 'WITHDRAWN':
                    so.status = 'DRAFT'
                    so.save()
            
            elif instance.business_type == 'PROJECT':
                from apps.projects.models import Project
                project = Project.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    project.status = 'IN_PROGRESS'  # 审批通过后项目开始
                    project.save()
                    logger.info(f"Project {project.code} approved, status changed to IN_PROGRESS")
                elif result == 'REJECTED':
                    project.status = 'REJECTED'  # 审批拒绝，可重新提交
                    project.save()
                    logger.info(f"Project {project.code} rejected, status changed to REJECTED")
                elif result == 'WITHDRAWN':
                    project.status = 'DRAFT'  # 撤回后回到草稿状态
                    project.save()
            
            elif instance.business_type == 'STOCK_ADJUSTMENT':
                from apps.inventory.models import StockAdjustment
                adjustment = StockAdjustment.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    adjustment.status = 'APPROVED'
                    adjustment.save()
                    # 执行库存调整
                    adjustment.apply_adjustment()
                    logger.info(f"Stock adjustment {adjustment.id} approved and applied")
                elif result == 'REJECTED':
                    adjustment.status = 'REJECTED'
                    adjustment.save()
                elif result == 'WITHDRAWN':
                    adjustment.status = 'DRAFT'
                    adjustment.save()
            
            elif instance.business_type == 'ECN':
                from apps.projects.models import ECN, ECNApproval
                ecn = ECN.objects.get(id=instance.business_id)
                
                # 获取最后一个审批任务的审批人（而非提交人）
                last_task = instance.tasks.filter(
                    status__in=['APPROVED', 'REJECTED']
                ).order_by('-action_time').first()
                approver = last_task.assignee if last_task else instance.submitter
                
                if result == 'APPROVED':
                    ecn.status = 'APPROVED'
                    ecn.approved_date = timezone.now().date()
                    ecn.save()
                    # 记录审批历史
                    ECNApproval.objects.create(
                        ecn=ecn,
                        approver=approver,
                        action='APPROVE',
                        comment='审批流程通过',
                        created_by=approver
                    )
                    logger.info(f"ECN {ecn.ecn_no} approved via workflow")
                elif result == 'REJECTED':
                    ecn.status = 'REJECTED'
                    ecn.save()
                    ECNApproval.objects.create(
                        ecn=ecn,
                        approver=approver,
                        action='REJECT',
                        comment='审批流程拒绝',
                        created_by=approver
                    )
                elif result == 'WITHDRAWN':
                    ecn.status = 'DRAFT'
                    ecn.save()
            
            # ============ 新增业务类型处理 ============
            
            elif instance.business_type == 'PURCHASE_ORDER':
                from apps.purchase.models import PurchaseOrder
                po = PurchaseOrder.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    po.status = 'APPROVED'
                    po.save()
                    logger.info(f"Purchase order {po.order_no} approved, waiting for confirmation")
                elif result == 'REJECTED':
                    po.status = 'REJECTED'
                    po.save()
                elif result == 'WITHDRAWN':
                    po.status = 'DRAFT'
                    po.save()
            
            elif instance.business_type == 'QUOTATION':
                from apps.sales.models import SalesQuotation
                quot = SalesQuotation.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    quot.status = 'APPROVED'
                    quot.save()
                    logger.info(f"Quotation {quot.quote_no} approved")
                elif result == 'REJECTED':
                    quot.status = 'REJECTED'
                    quot.save()
                elif result == 'WITHDRAWN':
                    quot.status = 'DRAFT'
                    quot.save()
            
            elif instance.business_type == 'SALES_CONTRACT':
                from apps.sales.models import SalesContract
                contract = SalesContract.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    contract.status = 'APPROVED'  # 审批通过
                    contract.save()
                    logger.info(f"Sales contract {contract.contract_no} approved")
                elif result == 'REJECTED':
                    contract.status = 'REJECTED'
                    contract.save()
                elif result == 'WITHDRAWN':
                    contract.status = 'DRAFT'
                    contract.save()
            
            elif instance.business_type == 'PAYMENT':
                from apps.finance.models import PaymentRequest
                payment_req = PaymentRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    payment_req.status = 'APPROVED'
                    payment_req.save()
                    logger.info(f"Payment request {payment_req.request_no} approved")
                elif result == 'REJECTED':
                    payment_req.status = 'REJECTED'
                    payment_req.save()
                elif result == 'WITHDRAWN':
                    payment_req.status = 'DRAFT'
                    payment_req.save()
            
            elif instance.business_type == 'LEAVE_REQUEST':
                from apps.accounts.attendance import LeaveRequest
                leave = LeaveRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    leave.status = 'APPROVED'
                    leave.save()
                    logger.info(f"Leave request {leave.id} approved")
                elif result == 'REJECTED':
                    leave.status = 'REJECTED'
                    leave.save()
                elif result == 'WITHDRAWN':
                    leave.status = 'DRAFT'
                    leave.save()
            
            elif instance.business_type == 'OVERTIME_REQUEST':
                from apps.accounts.attendance import OvertimeRequest
                overtime = OvertimeRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    overtime.status = 'APPROVED'
                    overtime.save()
                    logger.info(f"Overtime request {overtime.id} approved")
                elif result == 'REJECTED':
                    overtime.status = 'REJECTED'
                    overtime.save()
                elif result == 'WITHDRAWN':
                    overtime.status = 'DRAFT'
                    overtime.save()
            
            elif instance.business_type == 'VEHICLE_REQUEST':
                from apps.oa.vehicle import VehicleRequest
                vehicle_req = VehicleRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    vehicle_req.status = 'APPROVED'
                    vehicle_req.save()
                    logger.info(f"Vehicle request {vehicle_req.id} approved")
                elif result == 'REJECTED':
                    vehicle_req.status = 'REJECTED'
                    vehicle_req.save()
                elif result == 'WITHDRAWN':
                    vehicle_req.status = 'PENDING'
                    vehicle_req.save()
            
            elif instance.business_type == 'ASSET_BORROW':
                from apps.oa.asset import AssetBorrow
                borrow = AssetBorrow.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    borrow.status = 'APPROVED'
                    borrow.save()
                    logger.info(f"Asset borrow {borrow.id} approved")
                elif result == 'REJECTED':
                    borrow.status = 'REJECTED'
                    borrow.save()
                elif result == 'WITHDRAWN':
                    borrow.status = 'PENDING'
                    borrow.save()

            elif instance.business_type == 'PURCHASE_CONTRACT':
                from apps.purchase.models import PurchaseContract
                contract = PurchaseContract.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    contract.status = 'APPROVED'
                    contract.save()
                    logger.info(f"Purchase contract {contract.contract_no} approved")
                elif result == 'REJECTED':
                    contract.status = 'REJECTED'
                    contract.save()
                elif result == 'WITHDRAWN':
                    contract.status = 'DRAFT'
                    contract.save()

            elif instance.business_type == 'OUTSOURCE_MATERIAL_ISSUE':
                from apps.purchase.outsource_models import OutsourceMaterialIssue
                issue = OutsourceMaterialIssue.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    issue.status = 'CONFIRMED'
                    issue.save()
                    logger.info(f"Outsource material issue {issue.issue_no} approved")
                elif result in ('REJECTED', 'WITHDRAWN'):
                    issue.status = 'DRAFT'
                    issue.save()

            elif instance.business_type == 'OUTSOURCE_RECEIPT':
                from apps.purchase.outsource_models import OutsourceReceipt
                receipt = OutsourceReceipt.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    receipt.status = 'CONFIRMED'
                    receipt.save()
                    logger.info(f"Outsource receipt {receipt.receipt_no} approved")
                elif result in ('REJECTED', 'WITHDRAWN'):
                    receipt.status = 'DRAFT'
                    receipt.save()

            elif instance.business_type == 'CONTRACT_EXECUTION':
                from apps.purchase.contract_execution import ContractExecution
                execution = ContractExecution.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    execution.status = 'IN_PROGRESS'
                    if not execution.actual_start_date:
                        from datetime import date
                        execution.actual_start_date = date.today()
                    execution.save()
                    logger.info(f"Contract execution {execution.id} approved, now IN_PROGRESS")
                elif result in ('REJECTED', 'WITHDRAWN'):
                    execution.status = 'NOT_STARTED'
                    execution.save()

            elif instance.business_type == 'PAYMENT_RECORD':
                from apps.purchase.contract_execution import PaymentRecord
                payment = PaymentRecord.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    payment.status = 'APPROVED'
                    payment.approved_at = timezone.now()
                    payment.save()
                    logger.info(f"Payment record {payment.payment_no} approved")
                elif result == 'REJECTED':
                    payment.status = 'CANCELLED'
                    payment.save()
                elif result == 'WITHDRAWN':
                    payment.status = 'PENDING'
                    payment.save()

            elif instance.business_type == 'SERVICE_REQUEST':
                from apps.sales.after_sales_service import ServiceRequest
                sr = ServiceRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    sr.status = 'ACKNOWLEDGED'
                    sr.acknowledged_at = timezone.now()
                    sr.save()
                    logger.info(f"Service request {sr.request_no} approved/acknowledged")
                elif result in ('REJECTED', 'WITHDRAWN'):
                    sr.status = 'NEW'
                    sr.save()

            # Notify submitter
            cls._notify_submitter(instance, result)
            
        except Exception as e:
            logger.error(f"Error updating business object: {e}")
    
    @classmethod
    def _notify_assignee(cls, task):
        """
        Send notification to task assignee.
        """
        from apps.core.models import SystemNotification
        from apps.core.notification_service import NotificationService
        
        try:
            # Create system notification
            SystemNotification.objects.create(
                user=task.assignee,
                type='INFO',
                title='您有新的审批任务',
                message=f'单据 {task.instance.business_no} 等待您审批。'
            )
            
            # Send external notification (DingTalk/WeChat)
            NotificationService.send_approval_notification(task)
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    @classmethod
    def _notify_submitter(cls, instance, result):
        """
        Notify submitter about workflow result.
        """
        from apps.core.models import SystemNotification
        from apps.core.notification_service import NotificationService
        
        result_text = {
            'APPROVED': '已通过',
            'REJECTED': '已拒绝',
            'WITHDRAWN': '已撤回'
        }.get(result, result)
        
        try:
            SystemNotification.objects.create(
                user=instance.submitter,
                type='SUCCESS' if result == 'APPROVED' else 'WARNING',
                title=f'审批{result_text}',
                message=f'您提交的单据 {instance.business_no} {result_text}。'
            )
            
            # Send external notification
            NotificationService.send_workflow_result_notification(instance, result)
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    @classmethod
    def get_pending_tasks(cls, user):
        """
        Get all pending tasks for a user.
        """
        return WorkflowTask.objects.filter(
            assignee=user,
            status='PENDING',
            is_deleted=False
        ).select_related(
            'instance', 'instance__workflow', 'step'
        ).order_by('-created_at')
    
    @classmethod
    def get_submitted_workflows(cls, user):
        """
        Get all workflows submitted by a user.
        """
        return WorkflowInstance.objects.filter(
            submitter=user,
            is_deleted=False
        ).select_related('workflow').order_by('-submit_time')
    
    @classmethod
    def get_workflow_history(cls, business_type, business_id):
        """
        Get workflow history for a business object.
        """
        return WorkflowInstance.objects.filter(
            business_type=business_type,
            business_id=business_id,
            is_deleted=False
        ).prefetch_related(
            'tasks', 'tasks__assignee', 'tasks__step'
        ).order_by('-submit_time')
