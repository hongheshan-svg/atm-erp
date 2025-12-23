"""
URL configuration for projects app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet,
    ProjectMemberViewSet,
    ProjectTaskViewSet,
    ProjectBOMViewSet,
    TimeLogViewSet,
    ECNViewSet,
    ECNItemViewSet
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'members', ProjectMemberViewSet, basename='member')
router.register(r'tasks', ProjectTaskViewSet, basename='task')
router.register(r'bom', ProjectBOMViewSet, basename='bom')
router.register(r'time-logs', TimeLogViewSet, basename='time-log')
router.register(r'ecn', ECNViewSet, basename='ecn')
router.register(r'ecn-items', ECNItemViewSet, basename='ecn-item')

urlpatterns = [
    path('', include(router.urls)),
]

