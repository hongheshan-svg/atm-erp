from decimal import ROUND_CEILING, Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core.api import Conflict
from apps.core.models import CodeRule
from apps.core.permissions import ALL_ROLES, MANAGERS, has_role, require_project

from ..models import Delivery, Entry, Task, TimeEntry
from .bom import issued
from .common import (
    ZERO,
    audit,
    day,
    fields,
    identity,
    integer,
    lookup,
    number,
    project_action,
    rounded,
    save,
    state,
    text,
)
from .finance import balance

STAGES = ('design', 'assembly', 'test')
OPEN_PROJECT = {'active', 'delivering', 'warranty'}


def event_date(data, field='date'):
    result = day(data, field)
    if result > timezone.localdate():
        raise ValidationError({field: '实际业务日期不能晚于今天。'})
    return result


def assignee(project, value):
    user = lookup(User, value, 'assignee', is_active=True)
    require_project(user, project)
    return user


def completed_stage(project, kind):
    tasks = project.tasks.filter(kind=kind).exclude(status='cancelled')
    if not tasks.exists() or tasks.exclude(status='done').exists():
        raise Conflict(f'请先完成所有{Task.Kind(kind).label}任务。')


def create_task(actor, key, data):
    def execute(user, project):
        fields(data, {'project', 'kind', 'title', 'description', 'assignee', 'due_date'})
        state(project, {'active', 'delivering'})
        kind = text(data, 'kind', maximum=20)
        if kind not in STAGES:
            raise ValidationError(
                {'kind': '这里只能创建设计、装配或调试任务。安装验收随交付创建，售后请从交付批次创建。'}
            )
        task = save(
            Task(
                project=project,
                kind=kind,
                title=text(data, 'title', maximum=150),
                description=text(data, 'description', default='', maximum=20000),
                assignee=assignee(project, data.get('assignee')),
                due_date=day(data, 'due_date', optional=True),
            ),
            user,
        )
        return audit(user, 'task.create', task)

    return project_action(actor, key, 'task.create', data.get('project'), data, MANAGERS, execute)


def task_action(actor, key, operation, task_id, data, roles, execute):
    source = lookup(Task, task_id)

    def perform(user, project):
        task = get_object_or_404(Task.objects.select_for_update(), pk=source.pk, project=project)
        state(project, OPEN_PROJECT)
        return execute(user, project, task)

    return project_action(actor, key, operation, source.project_id, {'task': source.pk, 'data': data}, roles, perform)


def complete_task(actor, key, task_id, data):
    def execute(user, project, task):
        fields(data, {'reason'})
        if not has_role(user, MANAGERS) and task.assignee_id != user.pk:
            raise PermissionDenied('只能完成分配给自己的任务。')
        state(task, {'open'})
        if task.kind == 'acceptance':
            raise Conflict('验收必须从交付批次登记，不能直接完成验收任务。')
        if task.kind in STAGES:
            for prior in STAGES[: STAGES.index(task.kind)]:
                completed_stage(project, prior)
        reason = text(data, 'reason')
        task.status, task.completed_at = 'done', timezone.now()
        save(task, user)
        return audit(user, 'task.complete', task, reason=reason)

    return task_action(actor, key, 'task.complete', task_id, data, ALL_ROLES, execute)


def log_time(actor, key, task_id, data):
    def execute(user, project, task):
        fields(data, {'user', 'date', 'hours', 'reason'})
        state(task, {'open', 'done'})
        person_id = identity(data.get('user', user.pk), 'user')
        if not has_role(user, MANAGERS) and (person_id != user.pk or task.assignee_id != user.pk):
            raise PermissionDenied('只能为自己的任务登记本人工时。')
        # The project lock serializes its tasks; the person lock covers other projects too.
        person = get_object_or_404(User.objects.select_for_update(), pk=person_id, is_active=True)
        require_project(person, project)
        date = event_date(data)
        if project.contract_date and date < project.contract_date:
            raise ValidationError({'date': '工时日期不能早于项目签约日期。'})
        hours = number(data.get('hours'), 'hours', positive=True)
        recorded = TimeEntry.objects.filter(user=person, date=date).aggregate(total=Sum('hours'))['total'] or ZERO
        if recorded + hours > 24:
            raise Conflict('同一人员每天的净工时不能超过 24 小时。')
        entry = save(
            TimeEntry(
                task=task,
                user=person,
                date=date,
                hours=hours,
                hourly_cost=person.hourly_cost,
                cost=rounded(hours * person.hourly_cost),
                reason=text(data, 'reason'),
            ),
            user,
        )
        return audit(user, 'time.create', entry)

    return task_action(actor, key, 'time.create', task_id, data, ALL_ROLES, execute)


def amend_time(actor, key, entry_id, data):
    original = lookup(TimeEntry, entry_id)

    def execute(user, project, task):
        fields(data, {'hours', 'date', 'reason'})
        if not has_role(user, MANAGERS) and original.user_id != user.pk:
            raise PermissionDenied('只能更正本人工时。')
        person = User.objects.select_for_update().get(pk=original.user_id)
        source = get_object_or_404(TimeEntry.objects.select_for_update(), pk=original.pk, task=task)
        if source.reversal_of_id or source.hours <= 0 or TimeEntry.objects.filter(reversal_of=source).exists():
            raise Conflict('此工时已经更正，不能重复更正原记录。')
        hours = number(data.get('hours'), 'hours')
        if hours > 24:
            raise ValidationError({'hours': '工时不能超过 24 小时。'})
        date = event_date(data)
        if project.contract_date and date < project.contract_date:
            raise ValidationError({'date': '工时日期不能早于项目签约日期。'})
        recorded = TimeEntry.objects.filter(user=person, date=date).aggregate(total=Sum('hours'))['total'] or ZERO
        if recorded - (source.hours if source.date == date else ZERO) + hours > 24:
            raise Conflict('更正后同一人员当天净工时超过 24 小时。')
        reason = text(data, 'reason')
        reversal = save(
            TimeEntry(
                task=task,
                user=person,
                date=source.date,
                hours=-source.hours,
                hourly_cost=source.hourly_cost,
                cost=-source.cost,
                reason=reason,
                reversal_of=source,
            ),
            user,
        )
        replacement = None
        if hours:
            replacement = save(
                TimeEntry(
                    task=task,
                    user=person,
                    date=date,
                    hours=hours,
                    hourly_cost=source.hourly_cost,
                    cost=rounded(hours * source.hourly_cost),
                    reason=reason,
                    correction_of=source,
                ),
                user,
            )
        audit(
            user,
            'time.amend',
            source,
            reversal=reversal.pk,
            replacement=replacement.pk if replacement else None,
            reason=reason,
        )
        return {'id': replacement.pk if replacement else reversal.pk}

    return task_action(
        actor, key, 'time.amend', original.task_id, {'entry': original.pk, 'data': data}, ALL_ROLES, execute
    )


def delivered_materials(project):
    result = {}
    legacy_quantity = 0
    for delivery in project.deliveries.all():
        if delivery.material_requirements is None:
            legacy_quantity += delivery.quantity
        else:
            for row in delivery.material_requirements:
                item = int(row['item'])
                result[item] = result.get(item, ZERO) + Decimal(row['quantity'])
    if legacy_quantity:
        for line in project.bom_lines.values('item_id').annotate(total=Sum('quantity')):
            result[line['item_id']] = result.get(line['item_id'], ZERO) + (
                line['total'] * legacy_quantity / project.equipment_quantity
            ).quantize(Decimal('0.001'), rounding=ROUND_CEILING)
    return result


def ship(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'quantity', 'date', 'installer', 'acceptor', 'note', 'materials'})
        state(project, {'active', 'delivering'})
        for stage in STAGES:
            completed_stage(project, stage)
        qty = integer(data, 'quantity', None, minimum=1)
        shipped = project.deliveries.aggregate(total=Sum('quantity'))['total'] or 0
        if shipped + qty > project.equipment_quantity:
            raise Conflict('本次交付数量超过项目设备剩余数量。')
        bom = list(project.bom_lines.values('item_id').annotate(total=Sum('quantity')))
        if not bom:
            raise Conflict('请先登记设备 BOM 并完成领料。')
        previous = delivered_materials(project)
        planned = {}
        if data.get('materials'):
            if not isinstance(data['materials'], list) or len(data['materials']) > 1000:
                raise ValidationError({'materials': '本批配套清单必须为最多1000行的列表。'})
            for row in data['materials']:
                fields(row, {'item', 'quantity'})
                item = identity(row.get('item'), 'item')
                if item in planned or item not in {line['item_id'] for line in bom}:
                    raise ValidationError({'materials': '物料重复或不属于本项目BOM。'})
                planned[item] = number(row.get('quantity'), 'quantity', 3, positive=True)
        else:
            if len({line.assembly_unit for line in project.bom_lines.all() if line.assembly_unit}) > 1:
                raise Conflict('多单元项目请填写本批配套物料清单，明确本批实际用量。')
            for line in bom:
                target = (line['total'] * Decimal(shipped + qty) / project.equipment_quantity).quantize(
                    Decimal('0.001'), rounding=ROUND_CEILING
                )
                planned[line['item_id']] = max(ZERO, target - previous.get(line['item_id'], ZERO))
        for line in bom:
            required = previous.get(line['item_id'], ZERO) + planned.get(line['item_id'], ZERO)
            if required > line['total']:
                raise Conflict('累计交付配套数量超过BOM，请先核对清单或完成设计变更。')
            if shipped + qty == project.equipment_quantity and required < line['total']:
                raise Conflict('最后一批交付必须覆盖剩余BOM配套物料，请补齐清单。')
            if issued(project, line['item_id']) < required:
                raise Conflict('累计领料不足以支持本批交付，请到库存完成领料。')
        date = event_date(data)
        if project.contract_date and date < project.contract_date:
            raise ValidationError({'date': '交付日期不能早于签约日期。'})
        installer = assignee(project, data.get('installer', project.manager_id))
        acceptor = assignee(project, data.get('acceptor', project.manager_id))
        delivery = save(
            Delivery(
                code=CodeRule.generate_code('delivery'),
                project=project,
                quantity=qty,
                shipped_date=date,
                material_requirements=[
                    {'item': item, 'quantity': str(amount)} for item, amount in planned.items() if amount > ZERO
                ],
                note=text(data, 'note', default=''),
            ),
            user,
        )
        for kind, person in [('install', installer), ('acceptance', acceptor)]:
            save(
                Task(
                    project=project,
                    delivery=delivery,
                    kind=kind,
                    title=f'{delivery.code} {Task.Kind(kind).label}',
                    assignee=person,
                ),
                user,
            )
        project.status = 'delivering'
        save(project, user)
        return audit(user, 'delivery.ship', delivery, quantity=qty)

    return project_action(actor, key, 'delivery.ship', project_id, data, MANAGERS, execute)


def accept(actor, key, delivery_id, data):
    source = lookup(Delivery, delivery_id)

    def execute(user, project):
        fields(data, {'date', 'reason'})
        state(project, {'delivering'})
        delivery = get_object_or_404(Delivery.objects.select_for_update(), pk=source.pk, project=project)
        if delivery.accepted_date:
            raise Conflict('此交付批次已经验收。')
        installs = delivery.tasks.filter(kind='install')
        if not installs.exists() or installs.exclude(status='done').exists():
            raise Conflict('请先完成本批次的安装任务。')
        date = event_date(data)
        if date < delivery.shipped_date:
            raise ValidationError({'date': '验收日期不能早于交付日期。'})
        reason = text(data, 'reason')
        delivery.accepted_date = date
        delivery.warranty_until = date + relativedelta(months=project.warranty_months)
        save(delivery, user)
        for task in delivery.tasks.select_for_update().filter(kind='acceptance'):
            task.status, task.completed_at = 'done', timezone.now()
            save(task, user)
        shipped = project.deliveries.aggregate(total=Sum('quantity'))['total'] or 0
        if shipped == project.equipment_quantity and not project.deliveries.filter(accepted_date__isnull=True).exists():
            project.status = 'warranty'
            save(project, user)
        return audit(user, 'delivery.accept', delivery, date=date.isoformat(), reason=reason)

    return project_action(
        actor, key, 'delivery.accept', source.project_id, {'delivery': source.pk, 'data': data}, MANAGERS, execute
    )


def service(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'delivery', 'date', 'title', 'description', 'assignee', 'due_date', 'fee'})
        state(project, {'delivering', 'warranty'})
        delivery = lookup(Delivery, data.get('delivery'), 'delivery', project=project)
        if not delivery.accepted_date or not delivery.warranty_until:
            raise Conflict('此交付批次尚未验收，不能登记售后。')
        date = event_date(data)
        if date < delivery.accepted_date:
            raise ValidationError({'date': '售后日期不能早于验收日期。'})
        free = date <= delivery.warranty_until
        fee = number(data.get('fee', 0 if free else None), 'fee', positive=not free)
        if free and fee:
            raise ValidationError({'fee': '质保内售后免费，不能生成收费应收。'})
        task = save(
            Task(
                project=project,
                delivery=delivery,
                kind='service',
                service_date=date,
                title=text(data, 'title', maximum=150),
                description=text(data, 'description', default='', maximum=20000),
                assignee=assignee(project, data.get('assignee')),
                due_date=day(data, 'due_date', optional=True),
            ),
            user,
        )
        if fee:
            save(
                Entry(
                    project=project,
                    task=task,
                    kind='receivable',
                    title=f'售后 {task.title}',
                    amount=fee,
                    due_date=task.due_date or date,
                ),
                user,
            )
        return audit(user, 'service.create', task, delivery=delivery.pk, date=date.isoformat(), fee=str(fee))

    return project_action(actor, key, 'service.create', project_id, data, MANAGERS, execute)


def close(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'reason'})
        state(project, {'warranty'})
        if project.tasks.filter(status='open').exists():
            raise Conflict('项目还有未完成任务。')
        if (
            project.deliveries.aggregate(total=Sum('quantity'))['total'] != project.equipment_quantity
            or project.deliveries.filter(accepted_date__isnull=True).exists()
        ):
            raise Conflict('项目尚未全部交付验收。')
        if project.purchases.exclude(status__in=['received', 'cancelled']).exists():
            raise Conflict('项目还有未处理完成的采购。')
        if any(balance(entry) != 0 for entry in project.entries.select_for_update()):
            raise Conflict('项目还有未结清款项或待退款。')
        from .banking import check_close

        check_close(project)
        reason = text(data, 'reason')
        project.status, project.close_reason = 'closed', reason
        save(project, user)
        return audit(user, 'project.close', project, reason=reason)

    return project_action(actor, key, 'project.close', project_id, data, MANAGERS, execute)
