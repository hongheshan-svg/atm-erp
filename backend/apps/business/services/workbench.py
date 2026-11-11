from datetime import date

from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, Exists, F, OuterRef, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.permissions import (
    ADMIN,
    FINANCE,
    MANAGERS,
    MONEY_READERS,
    OPERATION_ROLES,
    PRODUCTION_MANAGERS,
    PRODUCTION_TASK_KINDS,
    PURCHASE_APPROVERS,
    PURCHASERS,
    WAREHOUSE,
    has_role,
    projects_for,
    sales_for,
)

from ..models import BOMLine, Entry, Project, PurchaseOrder, Task
from ..serializers import EntrySerializer, PurchaseSerializer, TaskSerializer
from .bom import allocations
from .common import ZERO
from .execution import with_task_flags
from .payment_terms import due_entries, with_sources
from .supply import applicants_by_purchase
from .task_supervision import supervised_tasks


class Plain:
    """已经整理好的字典行，按序列化器的调用方式交给 bucket 分页。"""

    def __init__(self, rows, many=True, context=None):
        self.data = list(rows)


def handover_projects(user):
    """本人负责、已签约执行但还没排任务或没建 BOM 的项目：签约交接后项目经理第一件要做的事。"""
    tasks = Task.objects.filter(project=OuterRef('pk')).exclude(status='cancelled')
    projects = (
        Project.objects.filter(manager=user, status='active')
        .annotate(has_tasks=Exists(tasks), has_bom=Exists(BOMLine.objects.filter(project=OuterRef('pk'))))
        .filter(Q(has_tasks=False) | Q(has_bom=False))
        .order_by(F('due_date').asc(nulls_last=True), 'pk')
    )
    for project in projects:
        missing = [
            label
            for label, absent in (
                ('任务计划', not project.has_tasks),
                ('BOM', not project.has_bom),
                ('预算', project.budget_materials is None),
            )
            if absent
        ]
        yield {
            'id': project.pk,
            'project': project.pk,
            'code': project.code,
            'title': f'{project.code} {project.name}',
            'project_name': project.name,
            'due_date': project.due_date,
            'missing': missing,
        }


def shortage_projects(user):
    """采购员可见的执行中项目里仍有缺料的 BOM 行（与 BOM 选料下单同一缺料口径），按最早需求日期排序。"""
    projects = list(
        projects_for(user, Project.objects.all(), PURCHASERS)
        .filter(status__in=['active', 'delivering'])
        .filter(Exists(BOMLine.objects.filter(project=OuterRef('pk'))))
        .order_by('pk')
    )
    # 各项目的 BOM、已领、库存与在途一次分组读取，再逐个项目分摊，与逐个调用 allocation 同一口径。
    planned = allocations([project.pk for project in projects])
    rows = []
    for project in projects:
        lines, plan = planned.get(project.pk, ([], {}))
        short = []
        for line in lines:
            entry = plan[line.pk]
            ordered = entry['assigned'] + entry['shared'] + entry['shared_unapproved']
            if max(ZERO, line.quantity - entry['used']) - ordered - entry['available'] > ZERO:
                short.append(line)
        if not short:
            continue
        dates = [line.required_date for line in short if line.required_date]
        rows.append(
            {
                'id': project.pk,
                'project': project.pk,
                'code': project.code,
                'title': f'{project.code} {project.name}',
                'project_name': project.name,
                'shortage_lines': len(short),
                'due_date': min(dates) if dates else None,
            }
        )
    rows.sort(key=lambda row: (row['due_date'] or date.max, row['code']))
    return rows


def summary(request):
    user = request.user
    selected_bucket = request.query_params.get('bucket')
    allowed = {
        'sales',
        'tasks',
        'production_tasks',
        'supervised_tasks',
        'approvals',
        'receipts',
        'drafts',
        'settlements',
        'overdue_purchases',
        'prepayments',
        'reconciliations',
        'bank_records',
        'quoted_sales',
        'sale_receivables',
        'handover_projects',
        'approved_purchases',
        'shortage_projects',
    }
    if selected_bucket and selected_bucket not in allowed:
        raise ValidationError('未知待办分类。')
    try:
        page_size = int(request.query_params.get('page_size', '20'))
    except (TypeError, ValueError):
        raise ValidationError('待办每页数量必须为 1 至 20。')
    if not 1 <= page_size <= 20:
        raise ValidationError('待办每页数量必须为 1 至 20。')

    def bucket(queryset, serializer, name):
        if selected_bucket and selected_bucket != name:
            return None
        try:
            page = int(request.query_params.get(f'{name}_page', '1'))
        except (TypeError, ValueError):
            raise ValidationError('待办页码必须为正整数。')
        if page < 1:
            raise ValidationError('待办页码必须为正整数。')
        selected = Paginator(queryset, page_size).get_page(page)
        data = {
            'page': selected.number,
            'page_size': page_size,
            'count': selected.paginator.count,
            'results': serializer(selected.object_list, many=True, context={'request': request}).data,
        }
        if name in {'tasks', 'production_tasks', 'supervised_tasks'}:
            data.update(
                queryset.aggregate(
                    overdue_count=Count('pk', filter=Q(due_date__lt=timezone.localdate())),
                    today_count=Count('pk', filter=Q(due_date=timezone.localdate())),
                )
            )
        return data

    result = {}
    if has_role(user, {'sales_manager'}):
        from ..models import SalesOrder
        from ..sales import SalesSerializer

        sales = (
            sales_for(user, SalesOrder.objects.all()).select_related('project', 'customer', 'manager').order_by('-id')
        )
        from .deletions import visible_rows

        # 已结项/已取消项目的销售单与管理员移入“已删除记录”的销售单不再是待跟进事项。
        sales = visible_rows(sales.exclude(status='cancelled').exclude(project__status__in=['closed', 'cancelled']))
        result['sales'] = bucket(sales, SalesSerializer, 'sales')
        # 已报价待签约单独列出，免得淹没在全部销售单里。
        result['quoted_sales'] = bucket(sales.filter(status='quoted'), SalesSerializer, 'quoted_sales')
        # 本人销售单关联项目的逾期应收：销售负责催款，与「交付与回款」同一读取范围（本人负责的销售单）。
        amount = DecimalField(max_digits=18, decimal_places=2)
        receivables = (
            Entry.objects.filter(
                kind='receivable',
                cancelled=False,
                project__sale__manager=user,
                project__sale__is_deleted=False,
                due_date__lt=timezone.localdate(),
            )
            .exclude(project__status__in=['closed', 'cancelled'])
            .select_related('project__customer', 'project__sale')
            .annotate(net_paid=Coalesce(Sum('payments__amount'), Value(ZERO), output_field=amount))
            .annotate(remaining=F('amount') - F('credit_amount') - F('net_paid'))
            .filter(remaining__gt=0)
            .order_by('due_date', 'pk')
        )
        result['sale_receivables'] = bucket(receivables, EntrySerializer, 'sale_receivables')
        if result['sale_receivables'] is not None:
            page = [row['id'] for row in result['sale_receivables']['results']]
            codes = dict(receivables.filter(pk__in=page).values_list('pk', 'project__sale__code'))
            for row in result['sale_receivables']['results']:
                row['sale_code'] = codes.get(row['id'])
    if not has_role(user, OPERATION_ROLES):
        return {key: value for key, value in result.items() if value is not None}
    projects = projects_for(user, Project.objects.all())
    tasks = with_task_flags(
        Task.objects.filter(Q(assignee=user) | Q(co_assignees=user), project__in=projects, status='open')
        .distinct()
        .select_related('project', 'assignee', 'delivery', 'entry')
        .prefetch_related('project__members', 'co_assignees')
        .exclude(project__status__in=['closed', 'cancelled'])
        .order_by(F('due_date').asc(nulls_last=True), 'pk')
    )
    result['tasks'] = bucket(tasks, TaskSerializer, 'tasks')
    supervised = supervised_tasks(
        user.pk,
        with_task_flags(
            Task.objects.filter(project__in=projects, status='open')
            .exclude(project__status__in=['closed', 'cancelled'])
            .select_related('project', 'assignee', 'delivery', 'entry')
            .prefetch_related('project__members', 'co_assignees')
        ),
    ).order_by(F('due_date').asc(nulls_last=True), 'pk')
    result['supervised_tasks'] = bucket(supervised, TaskSerializer, 'supervised_tasks')
    if result['tasks'] is not None and result['supervised_tasks'] is not None:
        # 「任务逾期」卡片要包含我负责确认的逾期任务；与本人任务重叠的只算一次。
        overdue = Q(due_date__lt=timezone.localdate())
        result['tasks']['overdue_total'] = len(
            set(tasks.filter(overdue).values_list('pk', flat=True))
            | set(supervised.filter(overdue).values_list('pk', flat=True))
        )
    if has_role(user, MANAGERS) and (not selected_bucket or selected_bucket == 'handover_projects'):
        result['handover_projects'] = bucket(list(handover_projects(user)), Plain, 'handover_projects')
    if has_role(user, {'production_manager'}):
        production_tasks = with_task_flags(
            Task.objects.filter(
                project__in=projects_for(user, Project.objects.all(), PRODUCTION_MANAGERS),
                kind__in=PRODUCTION_TASK_KINDS,
                status='open',
            )
            .exclude(project__status__in=['closed', 'cancelled'])
            .select_related('project', 'assignee', 'delivery', 'entry')
            .prefetch_related('project__members', 'co_assignees')
            .order_by(F('due_date').asc(nulls_last=True), 'pk')
        )
        result['production_tasks'] = bucket(production_tasks, TaskSerializer, 'production_tasks')
    purchases = (
        PurchaseOrder.objects.filter(project__in=projects)
        .select_related('project', 'supplier')
        .prefetch_related('lines__item', 'lines__bom_line', 'project__members')
        .order_by('due_date', 'pk')
    )

    def wanted(name):
        """只请求某一分类时，其他分类不再做额外查询（bucket 本来也会返回 None）。"""
        return not selected_bucket or selected_bucket == name

    if has_role(user, PURCHASE_APPROVERS) and wanted('approvals'):
        approvals = purchases.filter(
            status='submitted', project__in=projects_for(user, Project.objects.all(), PURCHASE_APPROVERS)
        )
        # 后端禁止申请人（创建、最近提交或改过数量/单价的人）审批自己的采购；管理员可按例外批准，保留并标注。
        mine = {pk for pk, applicants in applicants_by_purchase(approvals).items() if user.pk in applicants}
        admin = has_role(user, ADMIN)
        if not admin:
            approvals = approvals.exclude(pk__in=mine)
        result['approvals'] = bucket(approvals, PurchaseSerializer, 'approvals')
        if admin and result['approvals'] is not None:
            for row in result['approvals']['results']:
                row['self_requested'] = row['id'] in mine
    if has_role(user, WAREHOUSE):
        result['receipts'] = bucket(
            purchases.filter(status__in=['approved', 'partial']), PurchaseSerializer, 'receipts'
        )
    if has_role(user, PURCHASERS):
        result['drafts'] = bucket(purchases.filter(status='draft', created_by=user), PurchaseSerializer, 'drafts')
        # 批准后还没发合同、也没到货的本人采购：提醒采购员归档合同、向供应商下单。
        approved = purchases.filter(status='approved', created_by=user, contract_versions__isnull=True).distinct()
        result['approved_purchases'] = bucket(approved, PurchaseSerializer, 'approved_purchases')
        if wanted('shortage_projects'):
            result['shortage_projects'] = bucket(shortage_projects(user), Plain, 'shortage_projects')
    if has_role(user, PURCHASERS | WAREHOUSE) and wanted('overdue_purchases'):
        overdue = (
            purchases.filter(status__in=['approved', 'partial'])
            .filter(
                Q(lines__due_date__lt=timezone.localdate())
                | Q(lines__due_date__isnull=True, due_date__lt=timezone.localdate()),
                lines__quantity__gt=F('lines__received_quantity')
                + F('lines__cancelled_quantity')
                + F('lines__pending_quantity'),
            )
            .distinct()
        )
        if overdue.exists():
            result['overdue_purchases'] = bucket(overdue, PurchaseSerializer, 'overdue_purchases')
    if has_role(user, MONEY_READERS):
        amount = DecimalField(max_digits=18, decimal_places=2)
        entries = with_sources(
            Entry.objects.filter(project__in=projects_for(user, Project.objects.all(), MONEY_READERS))
            .exclude(project__status='closed')
            .select_related('project')
            .annotate(net_paid=Coalesce(Sum('payments__amount'), Value(ZERO), output_field=amount))
            .annotate(remaining=F('amount') - F('credit_amount') - F('net_paid'))
            .filter(Q(remaining__lt=0) | Q(remaining__gt=0))
            .order_by('due_date', 'pk')
        )
        entries = due_entries(entries, timezone.localdate())
        result['settlements'] = bucket(entries, EntrySerializer, 'settlements')
    if has_role(user, FINANCE | MANAGERS):
        from ..api.reconciliation import BankSerializer, ReconciliationSerializer, bank_list
        from ..models import BankRecord, Reconciliation
        from .banking import with_remaining
        from .reconciliation import with_snapshot_sources

        pending = with_snapshot_sources(
            Reconciliation.objects.filter(status='draft', entry__project__in=projects)
        ).order_by('id')
        if has_role(user, MANAGERS) and wanted('prepayments'):
            prepayments = pending.filter(
                kind='prepayment', entry__project__in=projects_for(user, Project.objects.all(), MANAGERS)
            )
            # 与采购审批同一口径：不能核准本人申请；管理员可按例外核准，保留并标注。
            admin = has_role(user, ADMIN)
            if not admin:
                prepayments = prepayments.exclude(created_by=user)
            if prepayments.exists():
                result['prepayments'] = bucket(prepayments, ReconciliationSerializer, 'prepayments')
                if admin and result['prepayments'] is not None:
                    mine = set(prepayments.filter(created_by=user).values_list('pk', flat=True))
                    for row in result['prepayments']['results']:
                        row['self_requested'] = row['id'] in mine
        if has_role(user, FINANCE):
            statements = pending.exclude(kind='prepayment')
            if wanted('reconciliations') and statements.exists():
                result['reconciliations'] = bucket(statements, ReconciliationSerializer, 'reconciliations')
            banks = (
                bank_list(with_remaining(BankRecord.objects.filter(void_reason='')))
                .filter(net_remaining__gt=0)
                .select_related('project')
                .order_by('date', 'id')
            )
            if wanted('bank_records') and banks.exists():
                result['bank_records'] = bucket(banks, BankSerializer, 'bank_records')
    return {key: value for key, value in result.items() if value is not None}
