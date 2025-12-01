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

router = DefaultRouter()
router.register(r'definitions', WorkflowDefinitionViewSet, basename='workflow-definition')
router.register(r'steps', WorkflowStepViewSet, basename='workflow-step')
router.register(r'instances', WorkflowInstanceViewSet, basename='workflow-instance')
router.register(r'tasks', WorkflowTaskViewSet, basename='workflow-task')

urlpatterns = [
    path('', include(router.urls)),
]
