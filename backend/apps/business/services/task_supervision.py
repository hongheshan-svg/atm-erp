"""Fixed project disciplines; explicit supervisors confirm work without gaining other roles."""

from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core.api import Conflict
from apps.core.permissions import MANAGERS, OPERATION_ROLES, has_role, project_allowed

from ..models import Task, TaskNotice
from .common import audit, fields, identity, integer, project_action, save, state, text


def default_discipline(kind, milestone=''):
    if milestone in {'design_electrical_bom', 'assembly_wiring', 'test_io', 'test_manual', 'test_auto', 'site_test'}:
        return 'electrical'
    if milestone == 'shipping_rectification':
        return 'production'
    return {
        'design': 'mechanical',
        'purchase': 'purchasing',
        'assembly': 'production',
        'test': 'electrical',
        'shipping': 'delivery',
        'site': 'delivery',
        'install': 'production',
        'acceptance': 'delivery',
        'service': 'production',
    }.get(kind, 'mechanical')


def discipline_value(data, kind, milestone=''):
    value = data.get('discipline') or default_discipline(kind, milestone)
    if value not in Task.Discipline.values:
        raise ValidationError({'discipline': '请选择机械、电气、采购、生产或交付与验收专业。'})
    return value


def supervisor_id(task):
    return task.project.task_supervisors.get(task.discipline) or task.project.manager_id


def can_confirm_task(user, task):
    if not user.is_active or not project_allowed(user, task.project):
        return False
    if project_allowed(user, task.project, MANAGERS):
        return True
    # 全局采购读取权不等于该项目主管身份；显式加入成员并指定专业后才可代录。
    return user.pk == supervisor_id(task) and user.pk in member_ids(task.project)


def member_ids(project):
    members = getattr(project, '_prefetched_objects_cache', {}).get('members')
    return (
        {person.pk for person in members} if members is not None else set(project.members.values_list('pk', flat=True))
    )


def require_confirmation(user, task):
    if not can_confirm_task(user, task):
        raise PermissionDenied('任务完成、日期和工时由本项目对应专业主管或项目经理统一登记；执行人员可查看进度。')


def supervised_tasks(user_id, queryset):
    scope = Q(pk__in=[])
    for discipline in Task.Discipline.values:
        scope |= Q(discipline=discipline) & (
            Q(**{f'project__task_supervisors__{discipline}': user_id})
            | (~Q(project__task_supervisors__has_key=discipline) & Q(project__manager_id=user_id))
        )
    return queryset.filter(scope)


def notify_task(actor, task, event):
    recipient = supervisor_id(task)
    # 主管自己派工或调整时已经知情，再给本人发提醒只会淹没别人派来的任务。
    if recipient == getattr(actor, 'pk', None):
        return
    if not User.objects.filter(pk=recipient, is_active=True).exists():
        return
    people = '、'.join(person.display_name or person.username for person in task.assigned_people())
    save(
        TaskNotice(
            task=task,
            recipient_id=recipient,
            message=f'{event}：{task.title}；执行人：{people}；计划完成：{task.due_date or "未设置"}。请跟进并核对实际完成日期和人员工时。'[
                :1000
            ],
        ),
        actor,
    )


def configure(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'supervisors', 'expected_revision', 'reason'})
        state(project, {'active', 'delivering', 'warranty'})
        if integer(data, 'expected_revision', None) != project.supervisor_revision:
            raise Conflict('专业主管设置已变化，请刷新后重新设置。')
        supplied = data.get('supervisors')
        if not isinstance(supplied, dict) or set(supplied) - set(Task.Discipline.values):
            raise ValidationError({'supervisors': '请按固定专业设置主管。'})
        values = {kind: identity(value, 'supervisors') for kind, value in supplied.items() if value not in (None, '')}
        people = User.objects.filter(pk__in=set(values.values()), is_active=True).in_bulk()
        allowed_ids = member_ids(project) | {project.manager_id}
        if (
            set(values.values()) - allowed_ids
            or len(people) != len(set(values.values()))
            or any(not has_role(person, OPERATION_ROLES) for person in people.values())
        ):
            raise ValidationError(
                {'supervisors': '主管必须是本项目启用的负责人或成员，并具备业务岗位；请先在项目成员中添加。'}
            )
        # 设置专业主管是日常安排，说明选填，缺省记为动作名。
        reason = text(data, 'reason', default='') or '设置专业主管'
        previous = project.task_supervisors
        project.task_supervisors = values
        project.supervisor_revision += 1
        save(project, user)
        changed = {kind for kind in Task.Discipline.values if previous.get(kind) != values.get(kind)}
        for task in (
            project.tasks.filter(status='open', discipline__in=changed)
            .select_related('project', 'assignee')
            .prefetch_related('co_assignees')
        ):
            notify_task(user, task, '负责主管已调整')
        return audit(user, 'project.supervisors', project, before=previous, after=values, reason=reason)

    return project_action(actor, key, 'project.supervisors', project_id, data, MANAGERS, execute)
