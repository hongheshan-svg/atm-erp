"""
Workflow enforcement mixins for ViewSets.
Ensures configured workflows are respected and provides auto-approve for unconfigured flows.
"""
import logging
from rest_framework.response import Response
from rest_framework import status

from .models import WorkflowInstance
from .services import WorkflowService

logger = logging.getLogger(__name__)


class WorkflowEnforcementMixin:
    """
    Mixin to enforce workflow approval for business objects.
    
    Usage:
        class PurchaseRequestViewSet(WorkflowEnforcementMixin, viewsets.ModelViewSet):
            workflow_business_type = 'PURCHASE_REQUEST'
            workflow_amount_field = 'total_amount'
            workflow_no_field = 'request_no'
    """
    workflow_business_type = None  # 子类必须设置，对应 WorkflowDefinition.business_type
    workflow_amount_field = 'total_amount'  # 金额字段名
    workflow_no_field = None  # 单据编号字段名，如 'request_no', 'order_no'
    
    def has_active_workflow(self, obj):
        """
        检查对象是否有活跃的工作流实例
        
        Returns:
            tuple: (has_workflow: bool, instance: WorkflowInstance or None)
        """
        if not self.workflow_business_type:
            return False, None
        
        instance = WorkflowInstance.objects.filter(
            business_type=self.workflow_business_type,
            business_id=obj.id,
            status='PENDING',
            is_deleted=False
        ).first()
        
        return bool(instance), instance
    
    def check_workflow_allows_direct_action(self, obj, action_name='审批'):
        """
        检查是否允许直接执行操作（如直接审批）
        如果有活跃工作流，返回错误响应
        
        Returns:
            Response or None: 如果不允许返回错误Response，否则返回None
        """
        has_workflow, instance = self.has_active_workflow(obj)
        if has_workflow:
            return Response(
                {'error': f'该单据正在审批流程中，请通过待办任务进行{action_name}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return None
    
    def start_workflow_or_auto_approve(self, obj, submitter, approved_status='APPROVED', submitted_status='SUBMITTED'):
        """
        启动工作流或自动批准
        
        Args:
            obj: 业务对象
            submitter: 提交人
            approved_status: 自动批准时的状态
            submitted_status: 进入工作流时的状态
            
        Returns:
            dict: {
                'workflow_started': bool,
                'auto_approved': bool,
                'new_status': str,
                'instance': WorkflowInstance or None,
                'message': str
            }
        """
        if not self.workflow_business_type:
            return {
                'workflow_started': False,
                'auto_approved': True,
                'new_status': approved_status,
                'instance': None,
                'message': '未配置业务类型，已自动批准'
            }
        
        # 获取金额
        amount = None
        if self.workflow_amount_field:
            amount = getattr(obj, self.workflow_amount_field, None)
        
        # 获取单据编号
        business_no = str(obj.id)
        if self.workflow_no_field:
            business_no = getattr(obj, self.workflow_no_field, business_no)
        
        # 尝试启动工作流
        instance, error = WorkflowService.start_workflow(
            business_type=self.workflow_business_type,
            business_id=obj.id,
            business_no=business_no,
            submitter=submitter,
            amount=amount
        )
        
        if instance:
            logger.info(f'{self.workflow_business_type} {business_no} 已启动工作流审批')
            return {
                'workflow_started': True,
                'auto_approved': False,
                'new_status': submitted_status,
                'instance': instance,
                'message': '已提交审批'
            }
        else:
            # 未配置流程，自动批准
            logger.info(f'{self.workflow_business_type} {business_no} 自动批准（未配置审批流程）')
            return {
                'workflow_started': False,
                'auto_approved': True,
                'new_status': approved_status,
                'instance': None,
                'message': '未配置审批流程，已自动批准'
            }


def check_workflow_status(business_type, business_id):
    """
    独立函数：检查业务对象的工作流状态
    可在非ViewSet场景下使用
    
    Returns:
        tuple: (has_pending_workflow: bool, instance: WorkflowInstance or None)
    """
    instance = WorkflowInstance.objects.filter(
        business_type=business_type,
        business_id=business_id,
        status='PENDING',
        is_deleted=False
    ).first()
    
    return bool(instance), instance


def start_workflow_or_auto_approve(business_type, business_id, business_no, submitter, amount=None):
    """
    独立函数：启动工作流或自动批准
    可在非ViewSet场景下使用
    
    Returns:
        tuple: (new_status: str, workflow_started: bool, instance: WorkflowInstance or None)
    """
    instance, error = WorkflowService.start_workflow(
        business_type=business_type,
        business_id=business_id,
        business_no=business_no,
        submitter=submitter,
        amount=amount
    )
    
    if instance:
        logger.info(f'{business_type} {business_no} 已启动工作流审批')
        return 'SUBMITTED', True, instance
    else:
        logger.info(f'{business_type} {business_no} 自动批准（未配置审批流程）')
        return 'APPROVED', False, None
