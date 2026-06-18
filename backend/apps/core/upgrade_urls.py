"""URL patterns for the remote-upgrade admin API.

These are mounted at ``api/v1/`` in ``config/urls.py``, so the full
paths are:
    GET  /api/v1/system/version
    GET  /api/v1/system/check-update
    POST /api/v1/system/upgrade
    GET  /api/v1/system/upgrade/jobs
    GET  /api/v1/system/upgrade/jobs/<int:job_id>
    POST /api/v1/system/rollback
"""
from django.urls import path

from .upgrade_views import (
    CheckUpdateView,
    PerformUpgradeView,
    RollbackView,
    SystemVersionView,
    UpgradeJobDetailView,
    UpgradeJobListView,
)

urlpatterns = [
    path('system/version', SystemVersionView.as_view(), name='system-version'),
    path('system/check-update', CheckUpdateView.as_view(), name='system-check-update'),
    path('system/upgrade', PerformUpgradeView.as_view(), name='system-upgrade'),
    path('system/upgrade/jobs', UpgradeJobListView.as_view(), name='system-upgrade-jobs'),
    path('system/upgrade/jobs/<int:job_id>', UpgradeJobDetailView.as_view(), name='system-upgrade-job-detail'),
    path('system/rollback', RollbackView.as_view(), name='system-rollback'),
]
