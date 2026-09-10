from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.api import Conflict
from apps.core.permissions import MANAGERS, OPERATION_ROLES, has_role

from ..models import BOMLine, Entry, Partner, PurchaseLine
from .bom import incoming, issued
from .common import ZERO, audit, day, fields, identity, integer, lookup, project_action, save, state, text
from .execution import STAGES, assignee, task_action
from .finance import balance


def edit_project(actor, key, project_id, data):
    def execute(user, project):
        fields(
            data,
            {
                'name',
                'customer',
                'manager',
                'members',
                'requirements',
                'due_date',
                'equipment_quantity',
                'warranty_months',
                'reason',
            },
        )
        state(project, {'draft', 'quoted', 'active', 'delivering', 'warranty'})
        reason = text(data, 'reason')
        before = {
            'name': project.name,
            'manager': project.manager_id,
            'members': list(project.members.values_list('pk', flat=True)),
        }
        if any(key in data for key in ('customer', 'equipment_quantity', 'warranty_months')) and (
            project.contract_date or project.deliveries.exists()
        ):
            raise Conflict('签约或交付后不能直接修改客户、设备数量或质保约定。')
        if 'customer' in data:
            project.customer = lookup(
                Partner, data['customer'], 'customer', is_active=True, kind__in=['customer', 'both']
            )
        if 'manager' in data:
            manager = lookup(User, data['manager'], 'manager', is_active=True)
            if not has_role(manager, MANAGERS):
                raise ValidationError({'manager': '负责人必须为启用的管理员或项目经理。'})
            project.manager = manager
        if 'members' in data:
            if not isinstance(data['members'], list) or len(data['members']) > 500:
                raise ValidationError({'members': '成员必须为用户标识数组，最多 500 人。'})
            ids = {identity(value, 'members') for value in data['members']}
            members = list(User.objects.filter(pk__in=ids, is_active=True))
            if len(members) != len(ids):
                raise ValidationError({'members': '包含不存在或已停用的用户。'})
            stranded = (
                project.tasks.filter(status='open')
                .exclude(assignee_id__in=ids | {project.manager_id})
                .select_related('assignee')
            )
            if any(not has_role(task.assignee, OPERATION_ROLES - {'member'}) for task in stranded):
                raise Conflict('移除的成员还有未完成任务，请先重新分配或取消任务。')
            project.members.set(members)
        for field, maximum in [('name', 150), ('requirements', 20000)]:
            if field in data:
                setattr(
                    project, field, text(data, field, maximum=maximum, default='' if field == 'requirements' else None)
                )
        if 'due_date' in data:
            project.due_date = day(data, 'due_date', optional=True)
        if 'equipment_quantity' in data:
            project.equipment_quantity = integer(data, 'equipment_quantity', None, minimum=1)
        if 'warranty_months' in data:
            project.warranty_months = integer(data, 'warranty_months', None, maximum=120)
        save(project, user)
        return audit(user, 'project.edit', project, before=before, fields=sorted(data), reason=reason)

    return project_action(actor, key, 'project.edit', project_id, data, MANAGERS, execute)


def cancel_project(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'reason'})
        state(project, {'draft', 'quoted', 'active'})
        if project.deliveries.exists():
            raise Conflict('已有交付不能取消整个项目，请通过售后处理。')
        if project.purchases.exclude(status__in=['received', 'cancelled']).exists():
            raise Conflict('请先完成采购或取消未收余量。')
        # Group every issued item, including lines removed from the current BOM.
        used = (
            project.stock_moves.filter(kind__in=['issue', 'return'])
            .values('stock__item_id')
            .annotate(total=Sum('quantity'))
        )
        if any(row['total'] != ZERO for row in used):
            raise Conflict('项目仍有未退回领料，请先完成退料。')
        entries = list(project.entries.select_for_update())
        if any(balance(entry) != 0 for entry in entries if entry.kind in {'payable', 'expense'}):
            raise Conflict('请先结清采购、费用及其退款。')
        reason = text(data, 'reason')
        for entry in entries:
            if entry.kind == 'receivable' and entry.task_id is None:
                entry.credit_amount, entry.cancelled = entry.amount, True
                save(entry, user)
        for task in project.tasks.select_for_update().filter(status='open'):
            task.status = 'cancelled'
            save(task, user)
        project.status, project.close_reason = 'cancelled', reason
        save(project, user)
        return audit(user, 'project.cancel', project, reason=reason)

    return project_action(actor, key, 'project.cancel', project_id, data, MANAGERS, execute)


def reopen_project(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'reason'})
        state(project, {'closed', 'cancelled'})
        reason = text(data, 'reason')
        before = project.status
        if project.status == 'cancelled':
            project.status = 'active'
            for entry in project.entries.select_for_update().filter(
                kind='receivable', task__isnull=True, cancelled=True
            ):
                entry.credit_amount, entry.cancelled = ZERO, False
                save(entry, user)
        else:
            project.status = 'warranty'
        project.close_reason = ''
        save(project, user)
        return audit(user, 'project.reopen', project, before=before, reason=reason)

    return project_action(actor, key, 'project.reopen', project_id, data, MANAGERS, execute)


def change_task(actor, key, task_id, data, operation):
    def execute(user, project, task):
        fields(data, {'reason', 'assignee'} if operation in {'assign', 'reopen'} else {'reason'})
        reason = text(data, 'reason')
        if operation == 'assign':
            state(task, {'open'})
            task.assignee = assignee(project, data.get('assignee'))
        elif operation == 'cancel':
            state(task, {'open', 'done'})
            if task.kind in {'install', 'acceptance'}:
                raise Conflict('交付关联的安装和验收任务不能取消。')
            if task.kind in STAGES and project.deliveries.exists():
                raise Conflict('已有交付，不能取消原生产阶段任务。')
            task.status = 'cancelled'
            if task.kind == 'service':
                entry = Entry.objects.select_for_update().filter(task=task).first()
                if entry:
                    entry.credit_amount, entry.cancelled = entry.amount, True
                    save(entry, user)
        elif operation == 'reopen':
            state(task, {'done', 'cancelled'})
            task.assignee = assignee(project, data.get('assignee', task.assignee_id))
            if task.kind == 'acceptance' or (task.kind == 'install' and task.delivery.accepted_date):
                raise Conflict('已验收事实不能通过重新打开任务撤销，请登记售后。')
            if task.kind in STAGES:
                if project.deliveries.exists():
                    raise Conflict('已有交付，不能重新打开原生产阶段任务。')
                if project.tasks.filter(kind__in=STAGES[STAGES.index(task.kind) + 1 :], status='done').exists():
                    raise Conflict('请先重新打开后续阶段任务。')
            task.status, task.completed_at = 'open', None
            if task.kind == 'service':
                entry = Entry.objects.select_for_update().filter(task=task, cancelled=True).first()
                if entry:
                    entry.credit_amount, entry.cancelled = ZERO, False
                    save(entry, user)
        else:
            raise ValidationError('不支持的任务操作。')
        save(task, user)
        return audit(user, f'task.{operation}', task, reason=reason)

    return task_action(actor, key, f'task.{operation}', task_id, data, MANAGERS, execute)


def remove_bom(actor, key, line_id, data):
    source = get_object_or_404(BOMLine.all_objects, pk=identity(line_id))

    def execute(user, project):
        fields(data, {'reason'})
        state(project, {'draft', 'quoted', 'active', 'delivering'})
        line = get_object_or_404(BOMLine.all_objects.select_for_update(), pk=source.pk, project=project)
        if line.is_deleted:
            raise Conflict('此 BOM 行已移除。')
        other_quantity = (
            BOMLine.objects.filter(project=project, item_id=line.item_id)
            .exclude(pk=line.pk)
            .aggregate(total=Sum('quantity'))['total']
            or ZERO
        )
        linked_pending = (
            PurchaseLine.objects.filter(bom_line=line)
            .exclude(purchase__status='cancelled')
            .filter(quantity__gt=F('received_quantity') + F('cancelled_quantity'))
            .exists()
        )
        if linked_pending or other_quantity < issued(project, line.item_id) + incoming(project, line.item_id):
            raise Conflict('此物料已有领用或在途采购，请先处理相关单据。')
        reason = text(data, 'reason')
        line.soft_delete(user)
        return audit(user, 'bom.remove', line, reason=reason)

    return project_action(
        actor, key, 'bom.remove', source.project_id, {'line': source.pk, 'data': data}, MANAGERS, execute
    )
