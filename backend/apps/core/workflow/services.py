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
        
        # Check if there's already an active workflow for this business object
        existing = WorkflowInstance.objects.filter(
            business_type=business_type,
            business_id=business_id,
            status='PENDING',
            is_deleted=False
        ).first()
        
        if existing:
            return None, "该单据已有进行中的审批流程"
        
        with transaction.atomic():
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
            # Skip this step and try next
            instance.current_step = current_step.step_order + 1
            instance.save()
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
                    role=step.approver_role,
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
                role=step.approver_role,
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
        """
        try:
            if instance.business_type == 'PURCHASE_REQUEST':
                from apps.purchase.models import PurchaseRequest
                pr = PurchaseRequest.objects.get(id=instance.business_id)
                if pr.project:
                    return pr.project.manager
            
            elif instance.business_type == 'EXPENSE':
                from apps.finance.models import Expense
                expense = Expense.objects.get(id=instance.business_id)
                if expense.project:
                    return expense.project.manager
            
            elif instance.business_type == 'SALES_ORDER':
                from apps.sales.models import SalesOrder
                so = SalesOrder.objects.get(id=instance.business_id)
                if so.project:
                    return so.project.manager
            
            elif instance.business_type == 'DELIVERY_ORDER':
                from apps.sales.models import DeliveryOrder
                delivery = DeliveryOrder.objects.get(id=instance.business_id)
                if delivery.so.project:
                    return delivery.so.project.manager
        except Exception as e:
            logger.error(f"Error getting project manager: {e}")
        
        return None
    
    @classmethod
    def approve_task(cls, task, user, comment=''):
        """
        Approve a workflow task.
        """
        if task.status != 'PENDING':
            return False, "该任务已处理"
        
        if task.assignee != user and not user.is_superuser:
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
    def reject_task(cls, task, user, comment=''):
        """
        Reject a workflow task.
        """
        if task.status != 'PENDING':
            return False, "该任务已处理"
        
        if task.assignee != user and not user.is_superuser:
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
                    # 审批通过，进入备货环节（不自动创建出库记录，由仓库确认备货时创建）
                    delivery.status = 'PREPARING'
                    delivery.save()
                    logger.info(f"Delivery order {delivery.delivery_no} approved, entering PREPARING status")
                    
                elif result == 'REJECTED':
                    delivery.status = 'REJECTED'
                    delivery.save()
                elif result == 'WITHDRAWN':
                    delivery.status = 'DRAFT'
                    delivery.save()
            
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
