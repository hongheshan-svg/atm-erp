from decimal import ROUND_CEILING, Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Count, DecimalField, Exists, Min, OuterRef, Subquery, Sum, Value, prefetch_related_objects
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core.api import Conflict
from apps.core.models import CodeRule
from apps.core.permissions import (
    ALL_ROLES,
    MANAGERS,
    MONEY_READERS,
    PRODUCTION_MANAGERS,
    project_allowed,
    require_project,
    task_management_roles,
)

from ..models import Delivery, Entry, StockMove, Task, TimeEntry
from ..task_milestones import AUTOMATIC, DEFINITIONS, PHASES
from .bom import issued
from .common import (
    ZERO,
    audit,
    day,
    event_date,
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
from .finance import balance, split_balance
from .task_supervision import can_confirm_task, default_discipline, discipline_value, notify_task, require_confirmation

STAGES = ('design', 'assembly', 'test')
OPEN_PROJECT = {'active', 'delivering', 'warranty'}


def with_task_flags(queryset):
    """Annotate the project facts TaskSerializer needs, so listing N tasks costs no extra query.

    是否已发货和首批发货时间由原交付记录投影；不注解的话序列化每行都要反查一次。
    """
    times = TimeEntry.objects.filter(task=OuterRef('pk')).order_by().values('task')
    return queryset.annotate(
        logged_hours=Coalesce(
            Subquery(times.annotate(total=Sum('hours')).values('total')),
            Value(ZERO),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
        time_entry_count=Coalesce(Subquery(times.annotate(total=Count('pk')).values('total')), Value(0)),
        project_shipped=Exists(Delivery.objects.filter(project=OuterRef('project_id'))),
        project_first_shipped_at=Subquery(
            Delivery.objects.filter(project=OuterRef('project_id')).order_by('created_at').values('created_at')[:1]
        ),
        task_has_time=Exists(TimeEntry.objects.filter(task=OuterRef('pk'))),
        task_has_moves=Exists(StockMove.objects.filter(task=OuterRef('pk'))),
    )


def stage_cancel_block(task):
    """已有交付时阶段任务是否还能取消；返回拒绝原因，None 表示可以取消。

    首批发货前已存在的阶段任务是已发货批次的生产依据，已完成或已登记工时、领料的任务是已发生的事实，
    都必须保留。首批发货后新建且尚未开工的任务（多为误建）取消后不影响任何已发生事实，
    否则它会让下一批发货永远卡在「请先完成所有阶段任务」。列表行由 with_task_flags 预先注解。
    """
    if hasattr(task, 'project_first_shipped_at'):
        first_shipped_at = task.project_first_shipped_at
        has_work = task.task_has_time or task.task_has_moves
    else:
        first_shipped_at = task.project.deliveries.aggregate(first=Min('created_at'))['first']
        has_work = task.time_entries.exists() or StockMove.objects.filter(task=task).exists()
    if first_shipped_at is None:
        return None
    if task.created_at <= first_shipped_at:
        return '已有交付，首批发货前的生产阶段任务是已发货批次的依据，不能取消。'
    if task.status != 'open' or task.started_date or has_work:
        return '此阶段任务已开工、已完成或已登记工时、领料，不能取消；请完成该任务后再安排后续发货。'
    return None


def participant(project, user, key='assignee'):
    """校验被指派人是否属于该项目。

    直接冒泡 require_project 的「无权访问此项目」会让操作者以为是自己权限不足，
    实际被拒的是所选人员；这里按字段报错，说清是谁、该怎么办。
    """
    if not project_allowed(user, project):
        raise ValidationError(
            {key: f'{user.display_name or user.username} 不是该项目的负责人或成员，请先在项目中加入此人再指派。'}
        )
    return user


def assignee(project, value):
    return participant(project, lookup(User, value, 'assignee', is_active=True))


def assigned_people(project, data, task=None):
    if 'assignees' in data:
        if 'assignee' in data:
            raise ValidationError({'assignees': '请只提交多人执行人列表，不要同时提交旧版单执行人字段。'})
        values = data['assignees']
        if not isinstance(values, list) or not 1 <= len(values) <= 500:
            raise ValidationError({'assignees': '请至少选择一名执行人，最多500人。'})
        ids = [identity(value, 'assignees') for value in values]
        if len(set(ids)) != len(ids):
            raise ValidationError({'assignees': '执行人不能重复选择。'})
        people = User.objects.filter(pk__in=ids, is_active=True).in_bulk()
        if len(people) != len(ids):
            raise ValidationError({'assignees': '包含不存在或已停用的执行人，请重新选择。'})
        prefetch_related_objects([project], 'members')
        return [participant(project, people[pk], 'assignees') for pk in ids]
    if 'assignee' in data or task is None:
        return [assignee(project, data.get('assignee'))]
    if not task.co_assignees.exists():
        return [assignee(project, task.assignee_id)]
    return assigned_people(project, {'assignees': [person.pk for person in task.assigned_people()]})


def save_new_task(user, values):
    additional = values.pop('co_assignees', [])
    task = save(Task(**values), user)
    if additional:
        task.co_assignees.set(additional)
    notify_task(user, task, '新任务已分配')
    return task


def check(key, ok, label, detail, *, blocking=True, target=None, message=''):
    """推进检查的一项。blocking 的项不满足时发货或结项会被服务端拒绝；非 blocking 只提示。

    message 是动作被拒时的报错原文，只在服务端内部使用，不随推进检查返回。
    """
    return {
        'key': key,
        'ok': ok,
        'label': label,
        'detail': detail,
        'blocking': blocking,
        'target': target or {},
        'message': message,
    }


def stage_check(project, kind):
    """发货前一个生产阶段是否完成：已取消的不计，必须至少有一项且全部完成。"""
    tasks = project.tasks.filter(kind=kind).exclude(status='cancelled')
    total, done = tasks.count(), tasks.filter(status='done').count()
    label = dict(PHASES)[kind]
    if not total:
        return check(
            f'stage_{kind}',
            False,
            label,
            f'尚未建立{label}任务',
            target={'tab': 'tasks', 'phase': kind},
            message=f'尚未建立{label}任务，请先安排并完成{label}任务再登记发货。',
        )
    return check(
        f'stage_{kind}',
        done == total,
        label,
        f'已完成 {done} / {total}',
        target={'tab': 'tasks', 'phase': kind},
        message=f'请先完成所有{label}任务（还有 {total - done} 项未完成）。',
    )


def follow_up_check(project):
    """采购跟进、客户预验收和整改等发货前跟进任务；由实际业务同步的汇总节点不计。"""
    pending = list(
        project.tasks.filter(kind__in=['purchase', 'shipping'], status='open')
        .exclude(milestone__in=AUTOMATIC)
        .order_by('pk')
        .values_list('kind', 'title')
    )
    names = '、'.join(title for _, title in pending[:4]) + ('等' if len(pending) > 4 else '')
    return check(
        'follow_up',
        not pending,
        '采购跟进、客户预验收与整改',
        f'还有 {len(pending)} 项未完成：{names}' if pending else '没有未完成的跟进任务',
        target={'tab': 'tasks', 'phase': 'shipping' if any(kind == 'shipping' for kind, _ in pending) else 'purchase'},
        message='请先完成已安排的采购跟进、客户预验收和整改任务，再登记发货。',
    )


def shipped_quantity(project):
    return project.deliveries.aggregate(total=Sum('quantity'))['total'] or 0


def bom_totals(project):
    return list(project.bom_lines.values('item_id').annotate(total=Sum('quantity')))


def proportional_plan(project, bom, shipped, qty, previous):
    """同配置项目不填配套清单时，本批按设备数量比例配套（向上取整到 0.001）。"""
    plan = {}
    for line in bom:
        target = (line['total'] * Decimal(shipped + qty) / project.equipment_quantity).quantize(
            Decimal('0.001'), rounding=ROUND_CEILING
        )
        plan[line['item_id']] = max(ZERO, target - previous.get(line['item_id'], ZERO))
    return plan


def material_problem(project, line, previous, planned, final):
    """一条 BOM 物料的累计配套是否成立；返回拒绝原因，None 表示成立。发货与推进检查共用。"""
    required = previous.get(line['item_id'], ZERO) + planned.get(line['item_id'], ZERO)
    if required > line['total']:
        return '累计交付配套数量超过BOM，请先核对清单或完成设计变更。'
    if final and required < line['total']:
        return '最后一批交付必须覆盖剩余BOM配套物料，请补齐清单。'
    if issued(project, line['item_id']) < required:
        return '累计领料不足以支持本批交付，请到库存完成领料。'
    return None


def completed_stage(project, kind):
    item = stage_check(project, kind)
    if not item['ok']:
        raise Conflict(item['message'])


def ship_checks(project):
    """登记发货前与本次填写无关的条件，顺序与发货时的校验一致。

    领料只能按「最少发 1 台」核算：同配置项目按比例、最后一台须覆盖剩余 BOM；多单元项目的本批清单
    在发货时才填写，此时只作提示。发货时服务端仍按实际填写内容逐项复核。
    """
    items = [stage_check(project, stage) for stage in STAGES]
    items.append(follow_up_check(project))
    shipped = shipped_quantity(project)
    remaining = project.equipment_quantity - shipped
    items.append(
        check(
            'quantity',
            remaining >= 1,
            '剩余待发设备',
            f'已发货 {shipped} / {project.equipment_quantity} 台'
            + (f'，还可发 {remaining} 台' if remaining > 0 else ''),
            target={'tab': 'deliveries'},
            message='本次交付数量超过项目设备剩余数量。',
        )
    )
    bom = bom_totals(project)
    items.append(
        check(
            'bom',
            bool(bom),
            '设备 BOM',
            f'已登记 {len(bom)} 种物料' if bom else '尚未登记 BOM',
            target={'tab': 'bom'},
            message='请先登记设备 BOM 并完成领料。',
        )
    )
    if bom and remaining >= 1:
        previous = delivered_materials(project)
        final = remaining == 1
        multi_unit = len({line.assembly_unit for line in project.bom_lines.all() if line.assembly_unit}) > 1
        if multi_unit and not final:
            items.append(
                check(
                    'materials',
                    True,
                    '本批配套领料',
                    '多单元项目在发货时填写本批配套清单，系统按清单核对累计领料',
                    blocking=False,
                    target={'tab': 'bom'},
                )
            )
        else:
            planned = (
                {line['item_id']: line['total'] - previous.get(line['item_id'], ZERO) for line in bom}
                if multi_unit
                else proportional_plan(project, bom, shipped, 1, previous)
            )
            short = [line for line in bom if material_problem(project, line, previous, planned, final)]
            items.append(
                check(
                    'materials',
                    not short,
                    '本批配套领料',
                    (f'按发 1 台核算，还有 {len(short)} 种物料领料不足' if short else '按发 1 台核算，领料已满足')
                    + ('（最后一台须覆盖剩余 BOM）' if final else ''),
                    target={'tab': 'bom'},
                    message='累计领料不足以支持本批交付，请到库存完成领料。',
                )
            )
    return items


def receivable_check(project):
    """发货时提示应收状态：只读取款项余额，不阻断发货。"""
    today = timezone.localdate()
    overdue, outstanding, count, overdue_count, earliest = ZERO, ZERO, 0, 0, None
    for entry in project.entries.filter(kind='receivable').order_by('due_date', 'pk'):
        part = split_balance(entry, today)
        if part.get('receivable'):
            count += 1
            outstanding += part['receivable']
        if part.get('overdue_receivable'):
            overdue_count += 1
            overdue += part['overdue_receivable']
            earliest = earliest or entry
    if not count:
        detail = '应收款项已结清或尚无应收'
    else:
        detail = f'未收 {count} 笔，共 ¥{outstanding:,.2f}'
        if overdue_count:
            detail += f'；其中已逾期 {overdue_count} 笔 ¥{overdue:,.2f}（最早：{earliest.title or "收款节点"}，到期 {earliest.due_date}）'
    return check('receivable', not overdue_count, '应收状态', detail, blocking=False, target={'tab': 'finance'})


def install_ready(delivery):
    """本批安装任务全部完成后才能登记验收。"""
    installs = delivery.tasks.filter(kind='install')
    return installs.exists() and not installs.exclude(status='done').exists()


def acceptance_checks(project):
    """交付中项目的批次进度：安装完成后才能登记验收（与验收动作同一规则）。"""
    pending = list(project.deliveries.filter(accepted_date__isnull=True).order_by('shipped_date', 'pk'))
    installing = [delivery for delivery in pending if not install_ready(delivery)]
    total = project.deliveries.count()
    return [
        check(
            'install',
            not installing,
            '批次安装',
            f'{len(installing)} 批安装任务未完成' if installing else '已发货批次的安装任务均已完成',
            target={'tab': 'tasks', 'phase': 'site'},
        ),
        check(
            'acceptance',
            not pending,
            '客户验收',
            f'已验收 {total - len(pending)} / {total} 批',
            target={'tab': 'deliveries'},
        ),
    ]


def close_checks(project, *, lock=False):
    """结项条件，顺序与结项校验一致；lock 只在实际结项时锁款项行。"""
    open_tasks = project.tasks.filter(status='open').count()
    shipped = shipped_quantity(project)
    unaccepted = project.deliveries.filter(accepted_date__isnull=True).count()
    purchases = project.purchases.exclude(status__in=['received', 'cancelled']).count()
    entries = project.entries.select_for_update() if lock else project.entries.all()
    unsettled = sum(balance(entry) != 0 for entry in entries)
    return [
        check(
            'tasks',
            not open_tasks,
            '任务全部完成或取消',
            f'还有 {open_tasks} 项未完成' if open_tasks else '全部任务已结束',
            target={'tab': 'tasks', 'attention': 'open-tasks'},
            message='项目还有未完成任务。',
        ),
        check(
            'deliveries',
            shipped == project.equipment_quantity and not unaccepted,
            '全部设备交付验收',
            f'已发货 {shipped} / {project.equipment_quantity} 台' + (f'，{unaccepted} 批待验收' if unaccepted else ''),
            target={'tab': 'deliveries'},
            message='项目尚未全部交付验收。',
        ),
        check(
            'purchases',
            not purchases,
            '采购全部收货或取消',
            f'还有 {purchases} 单未处理完成' if purchases else '采购均已收货或取消',
            target={'tab': 'purchases'},
            message='项目还有未处理完成的采购。',
        ),
        check(
            'entries',
            not unsettled,
            '款项全部结清',
            f'还有 {unsettled} 笔未结清或待退款' if unsettled else '款项均已结清',
            target={'tab': 'finance'},
            message='项目还有未结清款项或待退款。',
        ),
    ]


def readiness(user, project):
    """项目推进检查（只读）：发货、验收、结项前还差什么。规则与 ship/accept/close 共用同一组检查函数。"""
    require_project(user, project, MANAGERS)
    result = {'status': project.status, 'ship': [], 'accept': [], 'close': []}
    if project.status in {'active', 'delivering'} and shipped_quantity(project) < project.equipment_quantity:
        result['ship'] = ship_checks(project)
        if project_allowed(user, project, MONEY_READERS):
            result['ship'].append(receivable_check(project))
    if project.status == 'delivering':
        result['accept'] = acceptance_checks(project)
    if project.status == 'warranty':
        result['close'] = close_checks(project)
        from .banking import check_close

        # 对账与银行款项沿用结项时的同一函数；它会短暂锁定相关银行流水，放在只读事务里立即释放。
        try:
            with transaction.atomic():
                check_close(project)
            result['close'].append(
                check(
                    'banking', True, '对账单与银行款项', '没有待确认对账单或未匹配的银行款项', target={'tab': 'finance'}
                )
            )
        except Conflict as error:
            result['close'].append(
                check('banking', False, '对账单与银行款项', str(error.detail), target={'tab': 'finance'})
            )
    for key in ('ship', 'accept', 'close'):
        for item in result[key]:
            item.pop('message', None)
    return result


def task_values(project, data):
    fields(
        data,
        {'project', 'kind', 'milestone', 'title', 'description', 'assignee', 'assignees', 'due_date', 'discipline'},
    )
    kind = text(data, 'kind', maximum=20)
    if kind not in dict(PHASES):
        raise ValidationError(
            {'kind': '请选择设计、采购、组装、调试、发货或客户终验收阶段。批次安装和验收仍随交付创建。'}
        )
    milestone = text(data, 'milestone', default='', maximum=40)
    definition = DEFINITIONS.get(milestone)
    if milestone and (not definition or definition['kind'] != kind):
        raise ValidationError({'milestone': '里程碑节点与阶段不匹配，请重新选择。'})
    title = text(data, 'title', default='', maximum=150) or (definition['title'] if definition else '')
    if not title:
        raise ValidationError({'title': '自定义任务请填写任务名称，或选择里程碑节点。'})
    people = assigned_people(project, data)
    return {
        'project': project,
        'kind': kind,
        'milestone': milestone,
        'discipline': discipline_value(data, kind, milestone),
        'title': title,
        'description': text(
            data, 'description', default=definition['description'] if definition else '', maximum=20000
        ),
        'assignee': people[0],
        'co_assignees': people[1:],
        'due_date': day(data, 'due_date', optional=True),
    }


def create_task(actor, key, data):
    def execute(user, project):
        state(project, {'active', 'delivering'})
        values = task_values(project, data)
        if values['milestone'] and project.tasks.filter(milestone=values['milestone']).exists():
            raise Conflict('该里程碑节点已存在，请调整原任务，不要重复创建。')
        task = save_new_task(user, values)
        result = audit(user, 'task.create', task, assignees=[person.pk for person in task.assigned_people()])
        from .milestones import sync_milestones

        sync_milestones(user, project)
        return result

    return project_action(
        actor, key, 'task.create', data.get('project'), data, task_management_roles(data.get('kind')), execute
    )


def task_action(actor, key, operation, task_id, data, roles, execute, *, authorize_task=None):
    source = lookup(Task, task_id)

    def authorize(user, project):
        if authorize_task:
            task = get_object_or_404(Task.objects.select_for_update(), pk=source.pk, project=project)
            authorize_task(user, task)

    def perform(user, project):
        task = get_object_or_404(Task.objects.select_for_update(), pk=source.pk, project=project)
        state(project, OPEN_PROJECT)
        return execute(user, project, task)

    return project_action(
        actor,
        key,
        operation,
        source.project_id,
        {'task': source.pk, 'data': data},
        roles,
        perform,
        authorize_action=authorize,
    )


def start_task(actor, key, task_id, data, *, amend=False):
    def authorize(user, task):
        require_confirmation(user, task)

    def execute(user, project, task):
        fields(data, {'reason', 'started_date', 'expected_started_date'} if amend else {'reason', 'started_date'})
        state(task, {'open', 'done'} if amend else {'open'})
        if task.kind == 'acceptance' or task.milestone in AUTOMATIC:
            raise Conflict('此节点由实际业务同步，请在具体执行任务记录开始日期。')
        if amend:
            if day(data, 'expected_started_date', optional=True) != task.started_date:
                raise Conflict('实际开始日期已被修改，请刷新后重新核对。')
        elif task.started_date:
            raise Conflict('任务已经开始；日期有误请由有权限的任务管理者更正。')
        # 开始是正向日常登记，说明选填并缺省为动作名；更正开始日期属于纠错，仍须写明原因。
        reason = text(data, 'reason') if amend else text(data, 'reason', default='') or '开始任务'
        previous = task.started_date
        task.started_date = task_start_date(task, data)
        task.started_at = task.started_at or timezone.now()
        save(task, user)
        return audit(
            user,
            'task.start-date' if amend else 'task.start',
            task,
            reason=reason,
            before=previous.isoformat() if previous else None,
            after=task.started_date.isoformat(),
        )

    return task_action(
        actor,
        key,
        'task.start-date' if amend else 'task.start',
        task_id,
        data,
        ALL_ROLES,
        execute,
        authorize_task=authorize,
    )


def task_start_date(task, data):
    value = event_date(data, 'started_date')
    if task.completed_date and value > task.completed_date:
        raise ValidationError({'started_date': '实际开始日期不能晚于实际完成日期。'})
    if task.delivery_id and value < task.delivery.shipped_date:
        raise ValidationError({'started_date': '实际开始日期不能早于本批发货日期。'})
    if task.service_date and value < task.service_date:
        raise ValidationError({'started_date': '实际开始日期不能早于售后发生日期。'})
    return value


def complete_task(actor, key, task_id, data):
    def authorize(user, task):
        require_confirmation(user, task)

    def execute(user, project, task):
        fields(data, {'reason', 'completed_date', 'started_date'})
        state(task, {'open'})
        if task.kind == 'acceptance' or task.milestone in AUTOMATIC:
            raise Conflict('此节点由实际发货、安装或验收记录同步，请从对应业务办理，不能直接完成。')
        # 正常完成不需要「原因」：说明选填，缺省记为动作名，审计里仍有说明。
        reason = text(data, 'reason', default='') or '完成任务'
        if 'started_date' in data:
            if task.started_date:
                raise Conflict('任务已记录开始日期，请刷新；更正日期需由有权限的任务管理者处理。')
            task.started_date = task_start_date(task, data)
            task.started_at = timezone.now()
            audit(user, 'task.start', task, reason=reason, before=None, after=task.started_date.isoformat())
        task.completed_date = task_completion_date(task, data)
        task.status, task.completed_at = 'done', timezone.now()
        save(task, user)
        result = audit(user, 'task.complete', task, reason=reason, completed_date=task.completed_date.isoformat())
        from .milestones import sync_milestones

        sync_milestones(user, project)
        return result

    return task_action(actor, key, 'task.complete', task_id, data, ALL_ROLES, execute, authorize_task=authorize)


def task_completion_date(task, data):
    # 旧客户端省略时以本次确认当天完成；历史记录不据提交时间倒推实际日期。
    value = event_date(data, 'completed_date') if 'completed_date' in data else timezone.localdate()
    if task.started_date and value < task.started_date:
        raise ValidationError({'completed_date': '实际完成日期不能早于实际开始日期。'})
    if task.delivery_id and value < task.delivery.shipped_date:
        raise ValidationError({'completed_date': '实际完成日期不能早于本批发货日期。'})
    if (
        task.kind == 'install'
        and task.delivery_id
        and task.delivery.accepted_date
        and value > task.delivery.accepted_date
    ):
        raise ValidationError({'completed_date': '实际完成日期不能晚于本批验收日期。'})
    if task.service_date and value < task.service_date:
        raise ValidationError({'completed_date': '实际完成日期不能早于售后发生日期。'})
    return value


def amend_task_completion(actor, key, task_id, data):
    def authorize(user, task):
        if not can_confirm_task(user, task):
            raise PermissionDenied('请由有权限的任务管理者补录或更正实际完成日期。')

    def execute(user, project, task):
        fields(data, {'reason', 'completed_date', 'expected_completed_date'})
        state(task, {'done'})
        if task.kind == 'acceptance' or task.milestone in AUTOMATIC:
            raise Conflict('此节点的实际完成日期由业务记录同步，请处理对应的发货、安装或验收记录。')
        expected = day(data, 'expected_completed_date', optional=True)
        if expected != task.completed_date:
            raise Conflict('实际完成日期已被修改，请刷新后重新核对。')
        reason = text(data, 'reason')
        previous = task.completed_date
        task.completed_date = task_completion_date(task, {'completed_date': data.get('completed_date')})
        save(task, user)
        result = audit(
            user,
            'task.completion-date',
            task,
            reason=reason,
            before=previous.isoformat() if previous else None,
            after=task.completed_date.isoformat(),
        )
        from .milestones import sync_milestones

        sync_milestones(user, project)
        return result

    return task_action(actor, key, 'task.completion-date', task_id, data, ALL_ROLES, execute, authorize_task=authorize)


def edit_task(actor, key, task_id, data):
    """只改任务名称和完成要求；执行人、日期和状态仍走各自的动作。权限与重新分配相同。"""
    source = lookup(Task, task_id)

    def execute(user, project, task):
        fields(data, {'title', 'description', 'reason'})
        state(task, {'open', 'done'})
        if task.milestone in AUTOMATIC:
            raise Conflict('此节点按实际发货、安装或验收记录同步，名称和要求不在这里修改。')
        title = text(data, 'title', default=task.title, maximum=150)
        if not title:
            raise ValidationError({'title': '请填写任务名称。'})
        description = text(data, 'description', default=task.description or '', maximum=20000)
        if title == task.title and description == (task.description or ''):
            raise ValidationError({'title': '任务名称和完成要求都没有修改。'})
        # 改动的是执行人据以交付的标准，属于纠错，必须写明原因并保留原文。
        reason = text(data, 'reason')
        before = {'title': task.title, 'description': task.description or ''}
        task.title, task.description = title, description
        save(task, user)
        notify_task(user, task, '任务名称或完成要求已调整')
        return audit(
            user, 'task.edit', task, reason=reason, before=before, after={'title': title, 'description': description}
        )

    return task_action(actor, key, 'task.edit', task_id, data, task_management_roles(source.kind), execute)


def log_time(actor, key, task_id, data):
    def authorize(user, task):
        require_confirmation(user, task)

    def execute(user, project, task):
        fields(data, {'user', 'date', 'hours', 'reason'})
        if task.milestone in AUTOMATIC:
            raise Conflict('此节点是业务汇总，请在具体执行任务登记工时，避免重复计费。')
        state(task, {'open', 'done'})
        person_id = identity(data.get('user', user.pk), 'user')
        # Keep daily totals/rates serialized without blocking actor/audit FK KEY SHARE
        # checks when two people record each other's time in different projects.
        person = get_object_or_404(User.objects.select_for_update(no_key=True), pk=person_id, is_active=True)
        user.refresh_from_db(fields=['role', 'additional_roles', 'is_active', 'is_superuser'])
        require_project(user, project, ALL_ROLES)
        authorize(user, task)
        participant(project, person, 'user')
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
                # 工作内容选填，缺省记为动作名；更正、冲销工时仍须写明原因。
                reason=text(data, 'reason', default='') or '登记工时',
            ),
            user,
        )
        return {
            **audit(user, 'time.create', entry),
            'task': task.pk,
            'hours': str(entry.hours),
            'date': entry.date.isoformat(),
            'user_name': person.display_name or person.username,
        }

    return task_action(actor, key, 'time.create', task_id, data, ALL_ROLES, execute, authorize_task=authorize)


def amend_time(actor, key, entry_id, data):
    original = lookup(TimeEntry, entry_id)

    def authorize(user, task):
        require_confirmation(user, task)

    def execute(user, project, task):
        fields(data, {'hours', 'date', 'reason'})
        person = User.objects.select_for_update(no_key=True).get(pk=original.user_id)
        user.refresh_from_db(fields=['role', 'additional_roles', 'is_active', 'is_superuser'])
        require_project(user, project, ALL_ROLES)
        authorize(user, task)
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
        actor,
        key,
        'time.amend',
        original.task_id,
        {'entry': original.pk, 'data': data},
        ALL_ROLES,
        execute,
        authorize_task=authorize,
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
        fields(
            data,
            {
                'quantity',
                'date',
                'installer',
                'acceptor',
                'note',
                'materials',
                'code',
                'install_due_date',
                'acceptance_due_date',
            },
        )
        state(project, {'active', 'delivering'})
        for stage in STAGES:
            completed_stage(project, stage)
        follow_up = follow_up_check(project)
        if not follow_up['ok']:
            raise Conflict(follow_up['message'])
        qty = integer(data, 'quantity', None, minimum=1)
        shipped = shipped_quantity(project)
        if shipped + qty > project.equipment_quantity:
            raise Conflict('本次交付数量超过项目设备剩余数量。')
        bom = bom_totals(project)
        if not bom:
            raise Conflict('请先登记设备 BOM 并完成领料。')
        previous = delivered_materials(project)
        planned = {}
        if data.get('materials'):
            if not isinstance(data['materials'], list) or len(data['materials']) > 1000:
                raise ValidationError({'materials': '本批配套清单必须为最多1000行的列表。'})
            for index, row in enumerate(data['materials']):
                fields(row, {'item', 'quantity'})
                item = identity(row.get('item'), 'item')
                if item in planned or item not in {line['item_id'] for line in bom}:
                    raise ValidationError({'materials': '物料重复或不属于本项目BOM。'})
                try:
                    planned[item] = number(row.get('quantity'), 'quantity', 3, positive=True)
                except ValidationError as exc:
                    raise ValidationError({'materials': {index: exc.detail}}) from exc
        else:
            if len({line.assembly_unit for line in project.bom_lines.all() if line.assembly_unit}) > 1:
                raise Conflict('多单元项目请填写本批配套物料清单，明确本批实际用量。')
            planned = proportional_plan(project, bom, shipped, qty, previous)
        for line in bom:
            problem = material_problem(project, line, previous, planned, shipped + qty == project.equipment_quantity)
            if problem:
                raise Conflict(problem)
        date = event_date(data)
        if project.contract_date and date < project.contract_date:
            raise ValidationError({'date': '交付日期不能早于签约日期。'})
        # 可选的安装、验收期限写入随批次生成的任务，流程进度与工作台据此提示逾期；留空则不设期限。
        deadlines = {}
        for kind, field, label in [
            ('install', 'install_due_date', '安装完成期限'),
            ('acceptance', 'acceptance_due_date', '验收期限'),
        ]:
            deadlines[kind] = day(data, field, optional=True)
            if deadlines[kind] and deadlines[kind] < date:
                raise ValidationError({field: f'{label}不能早于发货日期 {date.isoformat()}，请重新选择或留空。'})
        installer = assignee(project, data.get('installer', project.manager_id))
        acceptor = assignee(project, data.get('acceptor', project.manager_id))
        delivery = save(
            Delivery(
                code=CodeRule.generate_code('delivery', custom=text(data, 'code', default='', maximum=30)),
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
            task = save(
                Task(
                    project=project,
                    delivery=delivery,
                    kind=kind,
                    discipline=default_discipline(kind),
                    title=f'{delivery.code} {Task.Kind(kind).label}',
                    assignee=person,
                    due_date=deadlines[kind],
                ),
                user,
            )
            notify_task(user, task, '交付任务已分配')
        project.status = 'delivering'
        save(project, user)
        result = audit(user, 'delivery.ship', delivery, quantity=qty)
        from .milestones import sync_milestones

        sync_milestones(user, project)
        return result

    return project_action(actor, key, 'delivery.ship', project_id, data, MANAGERS, execute)


def accept(actor, key, delivery_id, data):
    source = lookup(Delivery, delivery_id)

    def execute(user, project):
        fields(data, {'date', 'reason'})
        state(project, {'delivering'})
        delivery = get_object_or_404(Delivery.objects.select_for_update(), pk=source.pk, project=project)
        if delivery.accepted_date:
            raise Conflict('此交付批次已经验收。')
        if not install_ready(delivery):
            raise Conflict('请先完成本批次的安装任务。')
        date = event_date(data)
        if date < delivery.shipped_date:
            raise ValidationError({'date': '验收日期不能早于交付日期。'})
        if delivery.tasks.filter(kind='install', completed_date__gt=date).exists():
            raise ValidationError({'date': '验收日期不能早于本批安装的实际完成日期。'})
        # 正向的日常登记说明选填，缺省记为动作名，审计里仍有说明。
        reason = text(data, 'reason', default='') or '交付验收'
        delivery.accepted_date = date
        delivery.warranty_until = date + relativedelta(months=project.warranty_months)
        save(delivery, user)
        for task in delivery.tasks.select_for_update().filter(kind='acceptance'):
            task.status, task.completed_at = 'done', timezone.now()
            task.completed_date = date
            save(task, user)
        shipped = project.deliveries.aggregate(total=Sum('quantity'))['total'] or 0
        if shipped == project.equipment_quantity and not project.deliveries.filter(accepted_date__isnull=True).exists():
            project.status = 'warranty'
            save(project, user)
        result = audit(user, 'delivery.accept', delivery, date=date.isoformat(), reason=reason)
        from .milestones import sync_milestones

        sync_milestones(user, project)
        return result

    return project_action(
        actor, key, 'delivery.accept', source.project_id, {'delivery': source.pk, 'data': data}, MANAGERS, execute
    )


def service(actor, key, project_id, data):
    def authorize(user, project):
        if not project_allowed(user, project, MANAGERS):
            delivery = lookup(Delivery, data.get('delivery'), 'delivery', project=project)
            date = event_date(data)
            if (delivery.warranty_until and date > delivery.warranty_until) or number(data.get('fee', 0), 'fee'):
                raise PermissionDenied('收费及过保售后由项目经理确认费用后创建；生产经理负责后续派工和处理。')

    def execute(user, project):
        fields(
            data,
            {
                'delivery',
                'date',
                'title',
                'description',
                'assignee',
                'due_date',
                'fee',
                'fee_due_date',
                'free_reason',
                'charge_reason',
            },
        )
        state(project, {'delivering', 'warranty'})
        delivery = lookup(Delivery, data.get('delivery'), 'delivery', project=project)
        if not delivery.accepted_date or not delivery.warranty_until:
            raise Conflict('此交付批次尚未验收，不能登记售后。')
        date = event_date(data)
        if date < delivery.accepted_date:
            raise ValidationError({'date': '售后日期不能早于验收日期。'})
        free = date <= delivery.warranty_until
        fee = number(data.get('fee', 0 if free else None), 'fee')
        # 质保内默认免费；客户误操作、人为损坏等非质保责任可收费，但必须写明原因留审计。
        # 授权已限定只有项目经理/管理员能登记收费售后，生产经理仍只建质保内免费售后。
        charge_reason = text(data, 'charge_reason', default='', maximum=500) if fee else ''
        if free and fee and not charge_reason:
            raise ValidationError(
                {'charge_reason': '质保期内收费请填写非质保责任原因，例如客户误操作、人为损坏；否则请按免费售后登记。'}
            )
        # 过保后的商务赠送、延保等免费服务同样要能派工，但必须写明免费依据；授权已限定由项目经理登记。
        free_reason = text(data, 'free_reason', default='', maximum=500)
        if not free and not fee and not free_reason:
            raise ValidationError({'free_reason': '过保售后免费时请填写免费原因，例如商务赠送或延保约定。'})
        # Older clients can omit this field; the service date is the explicit compatibility default.
        # The repair deadline never determines when a customer payment becomes due.
        fee_due_date = (day(data, 'fee_due_date', optional=True) or date) if fee else None
        task = save(
            Task(
                project=project,
                delivery=delivery,
                kind='service',
                discipline='production',
                service_date=date,
                title=text(data, 'title', maximum=150),
                description=text(data, 'description', default='', maximum=20000),
                assignee=assignee(project, data.get('assignee')),
                due_date=day(data, 'due_date', optional=True),
            ),
            user,
        )
        notify_task(user, task, '售后任务已分配')
        if fee:
            save(
                Entry(
                    project=project,
                    task=task,
                    kind='receivable',
                    title=f'售后 {task.title}'[: Entry._meta.get_field('title').max_length],
                    amount=fee,
                    due_date=fee_due_date,
                ),
                user,
            )
        return audit(
            user,
            'service.create',
            task,
            delivery=delivery.pk,
            date=date.isoformat(),
            fee=str(fee),
            fee_due_date=fee_due_date.isoformat() if fee_due_date else None,
            free_reason=free_reason,
            charge_reason=charge_reason,
        )

    return project_action(
        actor,
        key,
        'service.create',
        project_id,
        data,
        PRODUCTION_MANAGERS,
        execute,
        authorize_action=authorize,
    )


def close(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'reason'})
        state(project, {'warranty'})
        for item in close_checks(project, lock=True):
            if not item['ok']:
                raise Conflict(item['message'])
        from .banking import check_close

        check_close(project)
        reason = text(data, 'reason')
        project.status, project.close_reason = 'closed', reason
        save(project, user)
        return audit(user, 'project.close', project, reason=reason)

    return project_action(actor, key, 'project.close', project_id, data, MANAGERS, execute)
