from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core.api import Conflict
from apps.core.permissions import (
    BOM_WRITERS,
    GLOBAL_PROJECT_ROLES,
    MANAGERS,
    has_role,
    project_allowed,
    task_management_roles,
)

from ..models import BOMLine, Entry, Partner, PurchaseLine, SalesOrder, Task
from ..task_milestones import AUTOMATIC, PRE_SHIPMENT
from .bom import incoming, issued, linked_incoming, open_purchases
from .common import (
    ZERO,
    audit,
    day,
    fields,
    identity,
    integer,
    lock_items,
    lookup,
    number,
    project_action,
    save,
    state,
    text,
)
from .execution import assigned_people, stage_cancel_block, task_action
from .finance import balance


def project_snapshot(project):
    """项目编辑前后的完整可编辑字段，审计据此还原每一次修改。"""
    return {
        'name': project.name,
        'customer': project.customer_id,
        'manager': project.manager_id,
        'members': sorted(project.members.values_list('pk', flat=True)),
        'requirements': project.requirements,
        'due_date': project.due_date.isoformat() if project.due_date else None,
        'equipment_quantity': project.equipment_quantity,
        'warranty_months': project.warranty_months,
    }


SHARED_SALE_FIELDS = ('name', 'customer_id', 'requirements', 'due_date', 'equipment_quantity', 'warranty_months')


def sync_sale(user, project):
    """签约时项目从销售单复制了这些字段；此后由项目维护，同步回销售单，避免两处显示不同的名称和交期。"""
    sale = SalesOrder.objects.select_for_update().filter(project=project).first()
    if sale is None:
        return []
    changed = [field for field in SHARED_SALE_FIELDS if getattr(sale, field) != getattr(project, field)]
    for field in changed:
        setattr(sale, field, getattr(project, field))
    if changed:
        if sale.status in {'draft', 'quoted'}:
            before = {'status': sale.status, 'quote_amount': str(sale.quote_amount)}
            sale.status, sale.quote_amount = 'draft', ZERO
            project.status = 'draft'
            save(project, user)
            audit(
                user,
                'sale.invalidate_quote',
                sale,
                before=before,
                project=project.pk,
                reason='历史项目需求变更，需重新报价',
            )
        save(sale, user)
    return [field.removesuffix('_id') for field in changed]


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
        before = project_snapshot(project)
        if any(key in data for key in ('customer', 'equipment_quantity', 'warranty_months')) and (
            project.contract_date or project.deliveries.exists()
        ):
            raise Conflict('签约或交付后不能直接修改客户、设备数量或质保约定。')
        if 'customer' in data:
            project.customer = lookup(
                Partner, data['customer'], 'customer', is_active=True, kind__in=['customer', 'both']
            )
        old_manager_id = project.manager_id
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
            member_ids = ids
            members_to_set = members
        else:
            member_ids = None
            members_to_set = None
        if member_ids is not None or project.manager_id != old_manager_id:
            keep = set(member_ids) if member_ids is not None else set(project.members.values_list('pk', flat=True))
            if set(project.task_supervisors.values()) - (keep | {project.manager_id}):
                raise Conflict('移除的成员仍是项目专业主管，请先调整专业主管设置。')
            stranded = project.tasks.filter(status='open').select_related('assignee').prefetch_related('co_assignees')
            for task in stranded:
                for person in task.assigned_people():
                    if person.pk in keep | {project.manager_id} or has_role(person, GLOBAL_PROJECT_ROLES):
                        continue
                    if person.pk == old_manager_id:
                        raise Conflict(
                            f'原负责人 {person.display_name or person.username} 还有未完成任务，'
                            '请先重新分配，或把其保留为项目成员。'
                        )
                    raise Conflict('移除的成员还有未完成任务，请先重新分配或取消任务。')
        if members_to_set is not None:
            project.members.set(members_to_set)
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
        if project.manager_id != old_manager_id:
            from .task_supervision import notify_task

            for task in (
                project.tasks.filter(status='open')
                .exclude(discipline__in=project.task_supervisors)
                .select_related('project', 'assignee')
                .prefetch_related('co_assignees')
            ):
                notify_task(user, task, '项目负责人已调整')
        synced = sync_sale(user, project)
        after = project_snapshot(project)
        changed = sorted(field for field in before if before[field] != after[field])
        return audit(
            user,
            'project.edit',
            project,
            before={field: before[field] for field in changed},
            after={field: after[field] for field in changed},
            fields=sorted(data),
            sale_synced=synced,
            reason=reason,
        )

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
                entry.cancellation_credit = entry.credit_amount
                entry.credit_amount, entry.cancelled = entry.amount, True
                save(entry, user)
        for task in project.tasks.select_for_update().filter(status='open'):
            task.status = 'cancelled'
            save(task, user)
        before = project.status
        project.status, project.close_reason = 'cancelled', reason
        save(project, user)
        return audit(user, 'project.cancel', project, before=before, reason=reason)

    return project_action(actor, key, 'project.cancel', project_id, data, MANAGERS, execute)


def reopen_project(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'reason'})
        state(project, {'closed', 'cancelled'})
        reason = text(data, 'reason')
        before = project.status
        if project.status == 'cancelled':
            sale = SalesOrder.objects.filter(project=project).first()
            project.status = sale.status if sale and sale.status in {'draft', 'quoted'} else 'active'
            for entry in project.entries.select_for_update().filter(
                kind='receivable', task__isnull=True, cancelled=True
            ):
                credit = entry.cancellation_credit
                if credit is None:
                    # Old cancellations did not retain their per-entry credits.
                    # Never invent a zero credit for an amended contract.
                    sale = getattr(project, 'sale', None)
                    if sale and sale.amendments.exists():
                        raise Conflict('历史取消记录缺少原抵减快照，请先核对补充协议并恢复原抵减金额。')
                    credit = ZERO
                entry.credit_amount, entry.cancelled = credit, False
                entry.cancellation_credit = None
                save(entry, user)
        else:
            project.status = 'warranty'
        project.close_reason = ''
        save(project, user)
        return audit(user, 'project.reopen', project, before=before, after=project.status, reason=reason)

    return project_action(actor, key, 'project.reopen', project_id, data, MANAGERS, execute)


def change_task(actor, key, task_id, data, operation):
    source = lookup(Task, task_id)

    def authorize(user, task):
        if (
            operation in {'cancel', 'reopen'}
            and task.kind == 'service'
            and not project_allowed(user, task.project, MANAGERS)
            and Entry.objects.filter(task=task).exists()
        ):
            raise PermissionDenied('收费售后的取消与重开涉及账款，请由项目经理处理。')
        if (
            operation == 'cancel'
            and task.kind in PRE_SHIPMENT
            and task.milestone not in AUTOMATIC
            and task.project.deliveries.exists()
            and stage_cancel_block(task) is None
            and not project_allowed(user, task.project, MANAGERS)
        ):
            # 发货后误建任务的取消会放开后续发货的阶段门槛，由项目经理确认；发货前的生产调整范围不变。
            raise PermissionDenied('首批发货后新建的阶段任务需由项目经理确认后取消。')

    def execute(user, project, task):
        fields(
            data,
            {'reason', 'assignee', 'assignees', 'due_date', 'discipline'}
            if operation == 'assign'
            else {'reason', 'assignee', 'assignees'}
            if operation == 'reopen'
            else {'reason'},
        )
        reason = text(data, 'reason')
        people = None
        previous = [person.pk for person in task.assigned_people()]
        previous_discipline = task.discipline
        if operation == 'assign':
            state(task, {'open'})
            if 'discipline' in data:
                from .task_supervision import discipline_value

                task.discipline = discipline_value(data, task.kind, task.milestone)
            people = assigned_people(project, data)
            task.assignee = people[0]
            if 'due_date' in data:
                task.due_date = day(data, 'due_date', optional=True)
                if (
                    task.delivery_id
                    and task.kind in {'install', 'acceptance'}
                    and task.due_date
                    and task.due_date < task.delivery.shipped_date
                ):
                    raise ValidationError({'due_date': '安装或验收截止日期不能早于本批发货日期。'})
        elif operation == 'cancel':
            state(task, {'open', 'done'})
            if task.kind in {'install', 'acceptance'} or (task.milestone in AUTOMATIC and task.status == 'done'):
                raise Conflict('实际安装、验收任务及已完成的业务汇总节点不能取消。')
            blocked = (
                stage_cancel_block(task) if task.kind in PRE_SHIPMENT and task.milestone not in AUTOMATIC else None
            )
            if blocked:
                raise Conflict(blocked)
            task.status = 'cancelled'
            if task.kind == 'service':
                entry = Entry.objects.select_for_update().filter(task=task).first()
                if entry:
                    entry.credit_amount, entry.cancelled = entry.amount, True
                    save(entry, user)
        elif operation == 'reopen':
            state(task, {'done', 'cancelled'})
            people = assigned_people(project, data, task)
            task.assignee = people[0]
            if (
                task.kind == 'acceptance'
                or (task.kind == 'install' and task.delivery.accepted_date)
                or (task.milestone in AUTOMATIC and task.status == 'done')
            ):
                raise Conflict('实际交付或验收事实不能通过重开汇总节点撤销；已验收后的问题请登记售后。')
            if task.kind in PRE_SHIPMENT and task.milestone not in AUTOMATIC:
                if project.deliveries.exists():
                    raise Conflict('已有交付，不能重新打开原生产阶段任务。')
            task.status, task.completed_at = 'open', None
            task.completed_date = None
            if task.kind == 'service':
                entry = Entry.objects.select_for_update().filter(task=task, cancelled=True).first()
                if entry:
                    entry.credit_amount, entry.cancelled = ZERO, False
                    save(entry, user)
        else:
            raise ValidationError('不支持的任务操作。')
        save(task, user)
        if people is not None:
            task.co_assignees.set(people[1:])
        result = audit(
            user,
            f'task.{operation}',
            task,
            reason=reason,
            previous_assignees=previous,
            previous_discipline=previous_discipline,
            discipline=task.discipline,
            assignees=[person.pk for person in task.assigned_people()],
        )
        if operation != 'assign':
            # 取消、重开会改变节点是否计入汇总；重新分配只改人员、专业和计划日期，自动节点不受影响。
            from .milestones import sync_milestones

            sync_milestones(user, project)
        from .task_supervision import notify_task

        notify_task(user, task, {'assign': '任务分配已调整', 'reopen': '任务已重开', 'cancel': '任务已取消'}[operation])
        return result

    return task_action(
        actor,
        key,
        f'task.{operation}',
        task_id,
        data,
        task_management_roles(source.kind),
        execute,
        authorize_task=authorize,
    )


BOM_STATES = {'draft', 'quoted', 'active', 'delivering'}


def removal_problems(project, lines):
    """移除这些 BOM 行前的拦截原因：关联本行的未收采购须先处理，各物料其余单元合计仍须覆盖已领与在途。

    提示带上数量和采购单号，工程师拿着它就能去找采购或仓管，不必再翻单据。
    """
    problems = []
    for line in lines:
        pending = linked_incoming(line)
        if pending > ZERO:
            orders = open_purchases(PurchaseLine.objects.filter(bom_line=line))
            problems.append(
                f'{line.item.code} {line.item.name}（{line.assembly_unit or "未分单元"}）关联在途采购 {pending}'
                f'{f"（{orders}）" if orders else ""}，请联系采购员取消未收余量后再移除。'
            )
    removing = {line.pk for line in lines}
    for item_id in sorted({line.item_id for line in lines}):
        other = (
            BOMLine.objects.filter(project=project, item_id=item_id)
            .exclude(pk__in=removing)
            .aggregate(total=Sum('quantity'))['total']
            or ZERO
        )
        used, pending = issued(project, item_id), incoming(project, item_id)
        if other < used + pending:
            item = next(line.item for line in lines if line.item_id == item_id)
            orders = open_purchases(PurchaseLine.objects.filter(purchase__project=project, item_id=item_id))
            problems.append(
                f'移除后 {item.code} {item.name} 其余单元合计 {other}，小于已领用 {used} 与在途采购 {pending}'
                f'{f"（{orders}）" if orders else ""} 之和；请联系采购员取消未收余量或联系仓管退回未用材料，'
                '也可用「修改此行」改为减少数量。'
            )
    return problems


def remove_bom(actor, key, line_id, data):
    source = get_object_or_404(BOMLine.all_objects, pk=identity(line_id))

    def execute(user, project):
        fields(data, {'reason'})
        state(project, BOM_STATES)
        line = get_object_or_404(BOMLine.all_objects.select_for_update(), pk=source.pk, project=project)
        if line.is_deleted:
            raise Conflict('此 BOM 行已移除。')
        problems = removal_problems(project, [line])
        if problems:
            raise Conflict('；'.join(problems))
        reason = text(data, 'reason')
        line.soft_delete(user)
        return audit(
            user, 'bom.remove', line, reason=reason, quantity=str(line.quantity), assembly_unit=line.assembly_unit
        )

    return project_action(
        actor, key, 'bom.remove', source.project_id, {'line': source.pk, 'data': data}, BOM_WRITERS, execute
    )


def remove_bom_lines(actor, key, data):
    """一次事务移除多行 BOM：任一行被拦截则整批不动，说明逐行列出。"""
    project_id = data.get('project') if isinstance(data, dict) else None

    def execute(user, project):
        fields(data, {'project', 'ids', 'reason'})
        state(project, BOM_STATES)
        ids = data.get('ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 500:
            raise ValidationError({'ids': '请选择 1 至 500 行 BOM 明细。'})
        ids = [identity(value, 'ids') for value in ids]
        if len(set(ids)) != len(ids):
            raise ValidationError({'ids': '所选 BOM 明细不能重复，请刷新后重新选择。'})
        reason = text(data, 'reason')
        lines = list(
            BOMLine.objects.select_for_update(of=('self',))
            .select_related('item')
            .filter(project=project, pk__in=ids)
            .order_by('pk')
        )
        if len(lines) != len(ids):
            raise Conflict('所选 BOM 明细已变化或已移除，请刷新后重新选择。')
        problems = removal_problems(project, lines)
        if problems:
            raise Conflict('；'.join(problems))
        for line in lines:
            line.soft_delete(user)
            audit(
                user, 'bom.remove', line, reason=reason, quantity=str(line.quantity), assembly_unit=line.assembly_unit
            )
        return {'id': project.pk, 'removed': len(lines)}

    return project_action(actor, key, 'bom.remove_batch', project_id, data, BOM_WRITERS, execute)


def replace_bom(actor, key, line_id, data):
    """替换物料（升版或换型）：同一事务里在原单元新增新物料行并移除原行，不出现新旧两行同时算缺料的中间状态。"""
    source = get_object_or_404(BOMLine.all_objects, pk=identity(line_id))

    def execute(user, project):
        fields(data, {'item', 'quantity', 'change_note', 'required_date', 'application_date', 'applicant'})
        state(project, BOM_STATES)
        line = get_object_or_404(
            BOMLine.all_objects.select_for_update(of=('self',)).select_related('item'), pk=source.pk, project=project
        )
        if line.is_deleted:
            raise Conflict('此 BOM 行已移除。')
        item_id = identity(data.get('item'), 'item')
        if item_id == line.item_id:
            raise ValidationError({'item': '请选择与原物料不同的新物料；只改数量请用「修改此行」。'})
        item = lock_items({item_id, line.item_id})[item_id]
        if not item.is_active:
            raise ValidationError({'item': 'BOM 不能添加或修改为已停用物料。'})
        qty = number(data.get('quantity'), 'quantity', 3, positive=True)
        note = text(data, 'change_note')
        if BOMLine.objects.filter(project=project, item=item, assembly_unit=line.assembly_unit).exists():
            raise Conflict(
                f'单元「{line.assembly_unit or "未分单元"}」已有物料 {item.code}，请用「修改此行」调整该行数量后移除原行。'
            )
        problems = removal_problems(project, [line])
        if problems:
            raise Conflict('；'.join(problems))
        replacement = BOMLine(
            project=project,
            item=item,
            quantity=qty,
            assembly_unit=line.assembly_unit,
            change_note=note,
            required_date=line.required_date,
            application_date=line.application_date,
            applicant=line.applicant,
        )
        for field in ('required_date', 'application_date'):
            if field in data:
                setattr(replacement, field, day(data, field, optional=True))
        if 'applicant' in data:
            replacement.applicant = text(data, 'applicant', default='', maximum=80)
        line.soft_delete(user)
        save(replacement, user)
        detail = {'replaced_line': line.pk, 'replaced_item': line.item.code, 'replacement_item': item.code}
        audit(
            user,
            'bom.remove',
            line,
            reason=note,
            quantity=str(line.quantity),
            assembly_unit=line.assembly_unit,
            replacement=replacement.pk,
            **detail,
        )
        audit(
            user,
            'bom.revise',
            replacement,
            before=None,
            after=str(qty),
            reason=note,
            before_unit='',
            after_unit=replacement.assembly_unit,
            **detail,
        )
        return {'id': replacement.pk, 'removed': line.pk}

    return project_action(
        actor, key, 'bom.replace', source.project_id, {'line': source.pk, 'data': data}, BOM_WRITERS, execute
    )
