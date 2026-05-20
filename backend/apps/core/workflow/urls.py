"""
Workflow URL configuration.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .flow_visualization import WorkflowStepStatisticsView, WorkflowTimelineView, WorkflowVisualizationView
from .views import WorkflowDefinitionViewSet, WorkflowInstanceViewSet, WorkflowStepViewSet, WorkflowTaskViewSet

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
