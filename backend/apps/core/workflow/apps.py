"""
Workflow app configuration.
"""
from django.apps import AppConfig


class WorkflowConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core.workflow'
    verbose_name = '审批工作流'
