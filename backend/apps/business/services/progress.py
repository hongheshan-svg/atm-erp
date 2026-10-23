"""Read-only collaboration projection; never exposes commercial payloads or grants actions."""

from django.core.paginator import Paginator
from django.db.models import DecimalField, F, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.permissions import (
    FINANCE,
    MANAGERS,
    MONEY_READERS,
    OPERATION_ROLES,
    PURCHASE_APPROVERS,
    PURCHASE_READERS,
    WAREHOUSE,
    has_role,
    project_allowed,
    projects_for,
)

from ..models import Delivery, Entry, PurchaseOrder, Reconciliation, Task
from . import finance, payment_terms
from . import reconciliation as statements
from .common import ZERO
from .deletions import visible_rows

GROUPS = {'tasks': '任务执行', 'purchases': '采购到货', 'deliveries': '交付验收', 'entries': '收付款进度'}


def readable_projects(user, queryset):
    scope = Q(pk__in=[])
    if has_role(user, OPERATION_ROLES):
        scope |= Q(pk__in=projects_for(user, queryset).values('pk'))
    if has_role(user, {'sales_manager'}):
        scope |= Q(sale__manager=user, sale__is_deleted=False)
    return queryset.filter(scope).distinct()


def person(user):
    return {'id': user.pk, 'name': user.display_name or user.username, 'active': user.is_active} if user else None


class Progress:
    def __init__(self, user, project):
        self.user, self.project = user, project
        # A small staff directory is shared by every row; no rates or contact details are returned.
        self.staff = list(User.objects.filter(is_active=True))
        self.today = timezone.localdate()

    def candidates(self, allowed, exclude=()):
        selected = [
            user for user in self.staff if user.pk not in exclude and project_allowed(user, self.project, allowed)
        ]
        names = [user.display_name or user.username for user in selected]
        return [
            {**person(user), 'name': f'{name}（账号：{user.username}）' if names.count(name) > 1 else name}
            for user, name in zip(selected, names, strict=True)
        ]

    def row(self, obj, resource, title, status, pending, *, due=None, due_label='截止日期', record=None):
        operational = project_allowed(self.user, self.project)
        readable = operational
        tab = {'tasks': 'tasks', 'purchases': 'purchases', 'deliveries': 'deliveries', 'entries': 'finance'}[resource]
        if resource == 'purchases':
            readable = project_allowed(self.user, self.project, PURCHASE_READERS)
        elif resource == 'entries':
            readable = project_allowed(self.user, self.project, MONEY_READERS)
        return {
            'id': obj.pk,
            'resource': resource,
            'title': title,
            'status_label': status,
            'pending': pending,
            'due_date': due,
            'due_label': due_label,
            'overdue': bool(pending and due and due < self.today),
            'handlers': [],
            'handler_label': '跟进人',
            'hint': '',
            'record': record or {},
            'path': f'/projects/{self.project.pk}?tab={tab}&section={resource}&resource={resource}&focus={obj.pk}'
            if readable
            else None,
            'updated_at': obj.updated_at,
        }

    def task(self, task):
        row = self.row(
            task,
            'tasks',
            f'{task.get_kind_display()} · {task.title}',
            task.get_status_display(),
            task.status == 'open',
            due=task.due_date,
            record={'status': task.status},
        )
        row.update(handlers=[person(task.assignee)], handler_label='执行人')
        row['hint'] = '由项目经理登记验收后完成。' if task.kind == 'acceptance' else '按任务要求完成后更新状态。'
        if not row['pending']:
            row['hint'] = '任务已结束，完成或取消记录保留。'
        elif not task.assignee.is_active:
            row['hint'] = '执行人已停用，请联系项目负责人重新派工。'
        return row

    def purchase(self, purchase):
        pending = purchase.status not in {'received', 'cancelled'}
        lines = list(purchase.lines.all())
        dates = [
            line.due_date or purchase.due_date
            for line in lines
            if line.quantity > line.received_quantity + line.cancelled_quantity + line.pending_quantity
        ]
        quarantine = sum((line.pending_quantity for line in lines), ZERO)
        status = purchase.get_status_display()
        if quarantine > 0:
            status = '已到货待检' if not any(line.received_quantity for line in lines) else '部分入库 · 尚有待检'
        row = self.row(
            purchase,
            'purchases',
            purchase.code,
            status,
            pending,
            due=min(dates) if dates and pending else None,
            due_label='交货日期',
            record={'status': purchase.status},
        )
        row['handlers'] = [person(purchase.created_by)] if purchase.created_by else [person(self.project.manager)]
        row['handler_label'] = '采购跟进人' if purchase.created_by else '项目负责人（待安排采购）'
        row['hint'] = '跟进供应商交货；到货后由仓管登记收货。'
        if purchase.status == 'draft':
            row['hint'] = '完善采购草稿后提交审批。'
        elif purchase.status == 'submitted':
            submitter = (
                AuditLog.objects.filter(operation='purchase.submit', resource=f'purchaseorder:{purchase.pk}')
                .order_by('-id')
                .values_list('actor_id', flat=True)
                .first()
            )
            row['handlers'] = self.candidates(PURCHASE_APPROVERS, {purchase.created_by_id, submitter})
            row['handler_label'] = '可审批人员'
            row['hint'] = '由其他有权限的人员审批；超预算还需预算复核及人员分离校验。'
            if not row['handlers']:
                row['hint'] = '暂无独立审批人员，请联系管理员安排；管理员处理本人申请须说明例外原因。'
        elif quarantine > 0:
            row['handlers'] = self.candidates(WAREHOUSE)
            row['handler_label'] = '待检处理岗位'
            row['hint'] = (
                f'有 {sum(line.pending_quantity > 0 for line in lines)} 条明细待检；确认合格后入库，不合格退回供应商。'
            )
            if dates:
                buyer = person(purchase.created_by or self.project.manager)
                row['handlers'] = list({item['id']: item for item in [buyer, *row['handlers']]}.values())
                row['handler_label'] = '采购 / 待检跟进'
                row['hint'] += '另有未到货物料，采购继续跟进交货。'
            else:
                row['due_label'] = '待检期限'
        elif not pending:
            row['hint'] = '本单采购流程已结束。'
        return row

    def delivery(self, delivery):
        pending = not delivery.accepted_date
        tasks = [task for task in delivery.tasks.all() if task.status == 'open']
        install = [task for task in tasks if task.kind == 'install']
        following = install or [task for task in tasks if task.kind == 'acceptance']
        dates = [task.due_date for task in following if task.due_date]
        status = '安装中' if install else '待客户验收' if pending else '已验收'
        if not pending and delivery.warranty_until:
            status = '质保期满' if delivery.warranty_until < self.today else '质保中'
        row = self.row(
            delivery,
            'deliveries',
            delivery.code,
            status,
            pending,
            due=min(dates) if dates else None,
            due_label='安装 / 验收期限',
            record={'accepted_date': delivery.accepted_date, 'warranty_until': delivery.warranty_until},
        )
        row['handlers'] = list({task.assignee_id: person(task.assignee) for task in following}.values())
        if not row['handlers']:
            row['handlers'] = [person(self.project.manager)]
        row['handler_label'] = '安装执行人' if install else '验收跟进人' if pending else '项目负责人'
        row['hint'] = (
            '安装完成后安排客户验收，由项目经理登记验收结果。' if pending else '已完成客户验收，后续按质保约定跟进。'
        )
        return row

    def entry(self, entry):
        remaining = finance.balance(entry)
        # 取消只冲减原金额；已收已付超出的部分仍要退回，余额小于零一律是待退款，归零才算结束。
        refund = remaining < 0
        pending = refund or (not entry.cancelled and remaining != 0)
        schedule = payment_terms.schedule(entry) if pending else []
        due = schedule[0]['due_date'] if schedule else None
        flow = (
            'refund'
            if refund
            else 'cancelled'
            if entry.cancelled
            else 'settled'
            if remaining == 0
            else 'partial'
            if finance.paid(entry) or entry.credit_amount
            else 'pending'
        )
        status = {
            'cancelled': '已取消',
            'settled': '已结清',
            'refund': '待退款',
            'partial': '部分结算',
            'pending': '待结算',
        }[flow]
        title = f'采购 {entry.purchase.code}' if entry.purchase_id else f'客户收款节点 #{entry.pk}'
        row = self.row(
            entry, 'entries', title, status, pending, due=due, due_label='付款到期日', record={'progress_status': flow}
        )
        row['handlers'], row['handler_label'] = self.candidates(FINANCE), '财务跟进人员'
        row['hint'] = '财务核对原始业务后登记收付款。'
        if refund:
            row['hint'] = '已收付金额超过应结金额，由财务办理退款；退款前须先完成退款对账。'
        if entry.kind == 'receivable':
            row['due_label'] = '收款到期日'
        if entry.purchase_id and pending and remaining > 0 and not schedule:
            row['status_label'] = '待起算付款'
            row['hint'] = '尚无已到期的合格收货款项；预付款须单独核准。'
            if entry.purchase.payment_term == 'manual':
                row['agreed_date'] = entry.purchase.payment_due_date or entry.due_date
        drafts = getattr(entry, 'progress_drafts', None)
        if drafts is None:
            drafts = [item for item in entry.reconciliations.all() if item.status == 'draft']
        drafts = drafts if pending else []
        # 快照失效的草稿谁都不能确认（确认时同样校验），只能由财务作废后按最新业务重建。
        stale = [item for item in drafts if not statements.current(item)]
        prepayments = [item for item in drafts if item.kind == 'prepayment' and item not in stale]
        if stale:
            row['status_label'] = '原业务已变化，待财务作废重建'
            row['handlers'], row['handler_label'] = self.candidates(FINANCE), '财务跟进人员'
            row['hint'] = '生成对账后原单据、收退货或资金流水已变化，需由财务作废原对账单并按最新业务重新生成。'
        elif prepayments:
            row['status_label'] = '预付款待核准'
            row['handlers'] = list(
                {
                    candidate['id']: candidate
                    for item in prepayments
                    for candidate in self.candidates(MANAGERS, {item.created_by_id})
                }.values()
            )
            row['handler_label'] = '可核准人员'
            row['hint'] = '合同预付款须项目经理核准后交财务办理；申请人不能自行核准。'
        elif drafts:
            row['status_label'] = '对账待确认'
        if not pending:
            row['hint'] = '本节点已结束，原始收付记录保留。'
        return row


def summary(user, project, params):
    category, state = params.get('category', 'tasks'), params.get('state', 'open')
    if category not in GROUPS or state not in {'open', 'all'}:
        raise ValidationError('请选择有效的流程分类和查看范围。')
    try:
        page, size = int(params.get('page', '1')), int(params.get('page_size', '20'))
    except (ValueError, TypeError):
        raise ValidationError('页码必须为正整数，每页数量为1至50。')
    if page < 1 or not 1 <= size <= 50:
        raise ValidationError('页码必须为正整数，每页数量为1至50。')
    amount = DecimalField(max_digits=18, decimal_places=2)
    entries = Entry.objects.filter(project=project, kind__in=['receivable', 'payable']).annotate(
        net_paid=Coalesce(Sum('payments__amount'), Value(ZERO), output_field=amount)
    )
    # Sales-only observers follow customer progress; supplier payment status stays with operational participants.
    if not project_allowed(user, project):
        entries = entries.filter(kind='receivable')
    queries = {
        'tasks': Task.objects.filter(project=project),
        'purchases': PurchaseOrder.objects.filter(project=project),
        'deliveries': Delivery.objects.filter(project=project),
        'entries': entries,
    }
    queries = {key: visible_rows(query) for key, query in queries.items()}
    opened = {
        'tasks': queries['tasks'].filter(status='open'),
        'purchases': queries['purchases'].exclude(status__in=['received', 'cancelled']),
        'deliveries': queries['deliveries'].filter(accepted_date__isnull=True),
        # 与行内 pending 同一口径：未取消且余额非零，或已取消但仍有待退款（余额小于零）。
        'entries': queries['entries']
        .exclude(amount=F('credit_amount') + F('net_paid'))
        .filter(Q(cancelled=False) | Q(amount__lt=F('credit_amount') + F('net_paid'))),
    }
    counts = [
        {'key': key, 'label': label, 'open': opened[key].count(), 'total': queries[key].count()}
        for key, label in GROUPS.items()
    ]
    query = (opened if state == 'open' else queries)[category]
    query = query.select_related('created_by', 'updated_by')
    if category == 'tasks':
        query = query.select_related('assignee').order_by(F('due_date').asc(nulls_last=True), 'pk')
    elif category == 'purchases':
        query = query.prefetch_related('lines').order_by('due_date', 'pk')
    elif category == 'deliveries':
        query = query.prefetch_related('tasks__assignee').order_by('shipped_date', 'pk')
    else:
        drafts = statements.with_snapshot_sources(Reconciliation.objects.filter(status='draft')).order_by('pk')
        query = (
            payment_terms.with_sources(query)
            .prefetch_related(Prefetch('reconciliations', queryset=drafts, to_attr='progress_drafts'))
            .order_by('due_date', 'pk')
        )
    selected = Paginator(query, size).get_page(page)
    progress = Progress(user, project)
    build = {
        'tasks': progress.task,
        'purchases': progress.purchase,
        'deliveries': progress.delivery,
        'entries': progress.entry,
    }[category]
    rows = [build(obj) for obj in selected]
    stopped = project.status in {'closed', 'cancelled'}
    if stopped:
        for row in rows:
            row['overdue'] = False
            if row['record'].get('progress_status') == 'refund':
                # 已取消项目可以直接退款，只有已结项项目须先重新打开。
                if project.status == 'closed':
                    row['hint'] = '项目已结项，须先由项目负责人重新打开，再由财务办理退款。'
                continue
            row['hint'] = f'项目{project.get_status_display()}，先联系项目负责人确认是否需要重开。'
    return {
        'project': {
            'id': project.pk,
            'code': project.code,
            'name': project.name,
            'status': project.status,
            'manager': person(project.manager),
            'due_date': project.due_date,
        },
        'groups': counts,
        'category': category,
        'state': state,
        'count': selected.paginator.count,
        'page': selected.number,
        'page_size': size,
        'results': rows,
        'checked_at': timezone.now(),
    }
