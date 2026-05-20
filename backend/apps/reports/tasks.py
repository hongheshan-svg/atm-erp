"""
Celery tasks for reports app.
"""

from celery import shared_task

from .services.cost_service import CostCalculationService


@shared_task
def calculate_all_project_costs():
    """
    Calculate and cache costs for all active projects.
    Runs nightly at 2 AM.
    """
    from apps.projects.models import Project

    active_projects = Project.objects.filter(status__in=['ACTIVE', 'COMPLETED'], is_deleted=False).values_list(
        'id', flat=True
    )

    count = 0
    for project_id in active_projects:
        # This will calculate and cache the results
        CostCalculationService.calculate_project_profit(project_id)
        count += 1

    return f'Calculated costs for {count} projects'
