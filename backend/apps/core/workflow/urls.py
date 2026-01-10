"""
Workflow URL configuration.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WorkflowDefinitionViewSet,
    WorkflowStepViewSet,
    WorkflowInstanceViewSet,
    WorkflowTaskViewSet
)
from .flow_visualization import (
    WorkflowVisualizationView,
    WorkflowStepStatisticsView,
    WorkflowTimelineView
)

router = DefaultRouter()
router.register(r'definitions', WorkflowDefinitionViewSet, basename='workflow-definition')
router.register(r'steps', WorkflowStepViewSet, basename='workflow-step')
router.register(r'instances', WorkflowInstanceViewSet, basename='workflow-instance')
router.register(r'tasks', WorkflowTaskViewSet, basename='workflow-task')

urlpatterns = [
    path('', include(router.urls)),
    
    # 工作流可视化API
    path('visualization/', WorkflowVisualizationView.as_view(), name='workflow-overview'),
    path('visualization/<int:workflow_id>/', WorkflowVisualizationView.as_view(), name='workflow-visualization'),
    path('visualization/<int:workflow_id>/timeline/', WorkflowTimelineView.as_view(), name='workflow-timeline'),
    path('my-statistics/', WorkflowStepStatisticsView.as_view(), name='workflow-my-statistics'),
]
