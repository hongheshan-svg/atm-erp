"""
Workflow engine for approval processes.
"""
# Don't import models at module level to avoid AppRegistryNotReady error
# Import models in your code using:
# from apps.core.workflow.models import WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowTask
# from apps.core.workflow.services import WorkflowService

default_app_config = 'apps.core.workflow.apps.WorkflowConfig'
