from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.permissions import ALL_ROLES, MANAGERS, project_allowed, require_project

from ..models import Project, Task
from ..task_milestones import AUTOMATIC, DEFINITIONS, NODES, PHASES
from .common import audit, fields, lookup, project_action, save, state
from .execution import save_new_task, task_values


def sync_milestones(user, project):
    """Rebuild only derived planning nodes from existing delivery/install facts."""
    nodes = list(project.tasks.select_for_update().filter(milestone__in=AUTOMATIC).exclude(status='cancelled'))
    if not nodes:
        return
    deliveries = project.deliveries.all()
    shipped = deliveries.aggregate(total=Sum('quantity'))['total'] or 0
    all_shipped = shipped >= project.equipment_quantity
    installs = Task.objects.filter(delivery__in=deliveries, kind='install')
    completed = {
        'shipping_dispatch': all_shipped,
        'site_install': all_shipped
        and installs.filter(status='done').values('delivery').distinct().count() == deliveries.count()
        and not installs.exclude(status='done').exists(),
        'site_acceptance': all_shipped and not deliveries.filter(accepted_date__isnull=True).exists(),
    }
    for task in nodes:
        target = 'done' if completed[task.milestone] else 'open'
        if task.status == target:
            continue
        task.status = target
        task.completed_at = timezone.now() if target == 'done' else None
        save(task, user)
        audit(user, 'task.milestone-sync', task, reason='按实际交付、安装和验收记录同步', status=target)


def template(actor, project_id=None):
    project = lookup(Project, project_id) if project_id else None
    if project:
        require_project(actor, project, ALL_ROLES)
    existing = list(project.tasks.exclude(milestone='').values_list('milestone', flat=True)) if project else []
    return {
        'stages': [{'value': value, 'label': label} for value, label in PHASES],
        'nodes': [{'milestone': code, **DEFINITIONS[code], 'system_managed': code in AUTOMATIC} for code, *_ in NODES],
        'existing': existing,
        'assignee': project.manager_id if project else None,
        'can_generate': bool(
            project and project.status in {'active', 'delivering'} and project_allowed(actor, project, MANAGERS)
        ),
    }


def apply_template(actor, key, data):
    def execute(user, project):
        fields(data, {'project', 'lines'})
        state(project, {'active', 'delivering'})
        lines = data.get('lines')
        if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
            raise ValidationError({'lines': '请选择1至100个里程碑或自定义任务。'})
        seen, created, skipped = set(), [], []
        for index, row in enumerate(lines):
            if not isinstance(row, dict):
                raise ValidationError({'lines': '每项任务必须包含阶段、负责人和任务内容。'})
            fields(row, {'kind', 'milestone', 'title', 'description', 'assignee', 'assignees', 'due_date'})
            try:
                values = task_values(project, row)
            except ValidationError as error:
                raise ValidationError({'lines': {index: error.detail}}) from error
            code = values['milestone']
            if code and code in seen:
                raise ValidationError({'lines': '同一里程碑节点不能重复，请删除重复行。'})
            if code:
                seen.add(code)
                if project.tasks.filter(milestone=code).exists():
                    skipped.append(code)
                    continue
            task = save_new_task(user, values)
            audit(
                user,
                'task.create',
                task,
                source='milestone-template',
                assignees=[person.pk for person in task.assigned_people()],
            )
            created.append(task.pk)
        sync_milestones(user, project)
        audit(user, 'project.milestones', project, created=created, skipped=skipped)
        return {'count': len(created), 'ids': created, 'skipped': skipped}

    return project_action(actor, key, 'project.milestones', data.get('project'), data, MANAGERS, execute)


def summary(actor, project_id):
    project = lookup(Project, project_id)
    require_project(actor, project, ALL_ROLES)
    tasks = list(
        project.tasks.filter(kind__in=dict(PHASES), delivery__isnull=True).select_related('assignee').order_by('pk')
    )
    today = timezone.localdate()
    stages = []
    for kind, label in PHASES:
        rows = [task for task in tasks if task.kind == kind and task.status != 'cancelled']
        stages.append(
            {
                'key': kind,
                'label': label,
                'total': len(rows),
                'done': sum(task.status == 'done' for task in rows),
                'overdue': sum(
                    task.status == 'open' and task.due_date is not None and task.due_date < today for task in rows
                ),
            }
        )
    return {
        'stages': stages,
        'can_generate': project.status in {'active', 'delivering'} and project_allowed(actor, project, MANAGERS),
    }
