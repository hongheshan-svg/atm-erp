"""
Workflow API views.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowTask
from .serializers import (
    WorkflowDefinitionSerializer,
    WorkflowStepSerializer,
    WorkflowInstanceSerializer,
    WorkflowTaskSerializer
)
from .services import WorkflowService


class WorkflowDefinitionViewSet(viewsets.ModelViewSet):
    """ViewSet for workflow definitions."""
    queryset = WorkflowDefinition.objects.filter(is_deleted=False)
    serializer_class = WorkflowDefinitionSerializer
    filterset_fields = ['business_type', 'is_active']
    search_fields = ['name', 'code']


class WorkflowStepViewSet(viewsets.ModelViewSet):
    """ViewSet for workflow steps."""
    queryset = WorkflowStep.objects.filter(is_deleted=False)
    serializer_class = WorkflowStepSerializer
    filterset_fields = ['workflow', 'approver_type']


class WorkflowInstanceViewSet(viewsets.ModelViewSet):
    """ViewSet for workflow instances."""
    queryset = WorkflowInstance.objects.filter(is_deleted=False)
    serializer_class = WorkflowInstanceSerializer
    filterset_fields = ['business_type', 'status', 'submitter']
    search_fields = ['business_no']
    
    @action(detail=False, methods=['get'])
    def my_submitted(self, request):
        """Get workflows submitted by current user."""
        workflows = WorkflowService.get_submitted_workflows(request.user)
        serializer = self.get_serializer(workflows, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """Withdraw a workflow instance."""
        instance = self.get_object()
        success, message = WorkflowService.withdraw_workflow(instance, request.user)
        
        if success:
            return Response({'message': message})
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get workflow history for a business object."""
        business_type = request.query_params.get('business_type')
        business_id = request.query_params.get('business_id')
        
        if not business_type or not business_id:
            return Response(
                {'error': '请提供 business_type 和 business_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        workflows = WorkflowService.get_workflow_history(business_type, int(business_id))
        serializer = self.get_serializer(workflows, many=True)
        return Response(serializer.data)


class WorkflowTaskViewSet(viewsets.ModelViewSet):
    """ViewSet for workflow tasks."""
    queryset = WorkflowTask.objects.filter(is_deleted=False)
    serializer_class = WorkflowTaskSerializer
    filterset_fields = ['instance', 'assignee', 'status']
    
    @action(detail=False, methods=['get'])
    def my_pending(self, request):
        """Get pending tasks for current user."""
        tasks = WorkflowService.get_pending_tasks(request.user)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_count(self, request):
        """Get count of pending tasks for current user."""
        count = WorkflowService.get_pending_tasks(request.user).count()
        return Response({'count': count})
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a task."""
        task = self.get_object()
        comment = request.data.get('comment', '')
        
        success, message = WorkflowService.approve_task(task, request.user, comment)
        
        if success:
            return Response({'message': message})
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a task."""
        task = self.get_object()
        comment = request.data.get('comment', '')
        
        if not comment:
            return Response(
                {'error': '拒绝时必须填写原因'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success, message = WorkflowService.reject_task(task, request.user, comment)
        
        if success:
            return Response({'message': message})
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
