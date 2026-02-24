"""
Workflow engine for approval processes.
"""
# Don't import models at module level to avoid AppRegistryNotReady error
# Import models in your code using:
# from apps.core.workflow.models import WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowTask
# from apps.core.workflow.services import WorkflowService
# from apps.core.workflow.mixins import WorkflowEnforcementMixin, check_workflow_status, start_workflow_or_auto_approve

default_app_config = 'apps.core.workflow.apps.WorkflowConfig'
