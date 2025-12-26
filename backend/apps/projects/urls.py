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
    ECNItemViewSet,
    AfterSalesOrderViewSet,
    ServiceRecordViewSet,
    SparePartUsageViewSet
)
from .bug_views import BugViewSet, BugCommentViewSet, BugAttachmentViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'members', ProjectMemberViewSet, basename='member')
router.register(r'tasks', ProjectTaskViewSet, basename='task')
router.register(r'bom', ProjectBOMViewSet, basename='bom')
router.register(r'time-logs', TimeLogViewSet, basename='time-log')
router.register(r'ecn', ECNViewSet, basename='ecn')
router.register(r'ecn-items', ECNItemViewSet, basename='ecn-item')

# 售后管理
router.register(r'aftersales', AfterSalesOrderViewSet, basename='aftersales')
router.register(r'service-records', ServiceRecordViewSet, basename='service-record')
router.register(r'spare-parts', SparePartUsageViewSet, basename='spare-part')

# Bug跟踪
router.register(r'bugs', BugViewSet, basename='bug')
router.register(r'bug-comments', BugCommentViewSet, basename='bug-comment')
router.register(r'bug-attachments', BugAttachmentViewSet, basename='bug-attachment')

urlpatterns = [
    path('', include(router.urls)),
]

