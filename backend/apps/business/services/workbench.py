from django.core.paginator import Paginator
from django.db.models import (
    CharField,
    Count,
    DecimalField,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Cast, Coalesce, Concat
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.models import AuditLog
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

from ..models import Entry, Project, PurchaseOrder, Task
from ..serializers import EntrySerializer, PurchaseSerializer, TaskSerializer
from .common import ZERO
from .execution import with_task_flags
from .payment_terms import due_entries, with_sources


def _submitted_by(user):
    """Purchases whose latest submission was made by this user (same rule as progress.candidates)."""
    latest = (
        AuditLog.objects.filter(
            operation='purchase.submit', resource=Concat(Value('purchaseorder:'), Cast(OuterRef('pk'), CharField()))
        )
        .order_by('-id')
        .values('actor_id')[:1]
    )
    return (
        PurchaseOrder.objects.filter(status='submitted')
        .annotate(_submitter=Subquery(latest))
        .filter(_submitter=user.pk)
        .values('pk')
    )


def summary(request):
    user = request.user
    selected_bucket = request.query_params.get('bucket')
    allowed = {
        'sales',
        'tasks',
        'production_tasks',
        'approvals',
        'receipts',
        'drafts',
        'settlements',
        'overdue_purchases',
        'prepayments',
        'reconciliations',
        'bank_records',
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
        if name in {'tasks', 'production_tasks'}:
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
    if not has_role(user, OPERATION_ROLES):
        return {key: value for key, value in result.items() if value is not None}
    projects = projects_for(user, Project.objects.all())
    tasks = with_task_flags(
        Task.objects.filter(project__in=projects, assignee=user, status='open')
        .select_related('project', 'assignee', 'delivery', 'entry')
        .prefetch_related('project__members')
        .exclude(project__status__in=['closed', 'cancelled'])
        .order_by(F('due_date').asc(nulls_last=True), 'pk')
    )
    result['tasks'] = bucket(tasks, TaskSerializer, 'tasks')
    if has_role(user, {'production_manager'}):
        production_tasks = with_task_flags(
            Task.objects.filter(
                project__in=projects_for(user, Project.objects.all(), PRODUCTION_MANAGERS),
                kind__in=PRODUCTION_TASK_KINDS,
                status='open',
            )
            .exclude(project__status__in=['closed', 'cancelled'])
            .select_related('project', 'assignee', 'delivery', 'entry')
            .prefetch_related('project__members')
            .order_by(F('due_date').asc(nulls_last=True), 'pk')
        )
        result['production_tasks'] = bucket(production_tasks, TaskSerializer, 'production_tasks')
    purchases = (
        PurchaseOrder.objects.filter(project__in=projects)
        .select_related('project', 'supplier')
        .prefetch_related('lines__item', 'lines__bom_line', 'project__members')
        .order_by('due_date', 'pk')
    )
    if has_role(user, PURCHASE_APPROVERS):
        approvals = purchases.filter(
            status='submitted', project__in=projects_for(user, Project.objects.all(), PURCHASE_APPROVERS)
        )
        # 后端禁止申请人（创建人或最近一次提交人）审批自己的采购；管理员可按例外批准，保留并标注。
        own = Q(created_by=user) | Q(pk__in=_submitted_by(user))
        admin = has_role(user, ADMIN)
        if not admin:
            approvals = approvals.exclude(own)
        result['approvals'] = bucket(approvals, PurchaseSerializer, 'approvals')
        if admin and result['approvals'] is not None:
            mine = set(approvals.filter(own).values_list('pk', flat=True))
            for row in result['approvals']['results']:
                row['self_requested'] = row['id'] in mine
    if has_role(user, WAREHOUSE):
        result['receipts'] = bucket(
            purchases.filter(status__in=['approved', 'partial']), PurchaseSerializer, 'receipts'
        )
    if has_role(user, PURCHASERS):
        result['drafts'] = bucket(purchases.filter(status='draft', created_by=user), PurchaseSerializer, 'drafts')
    if has_role(user, PURCHASERS | WAREHOUSE):
        overdue = (
            purchases.filter(status__in=['approved', 'partial'])
            .filter(
                Q(lines__due_date__lt=timezone.localdate())
                | Q(lines__due_date__isnull=True, due_date__lt=timezone.localdate()),
                lines__quantity__gt=F('lines__received_quantity') + F('lines__cancelled_quantity'),
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
        if has_role(user, MANAGERS):
            prepayments = pending.filter(
                kind='prepayment', entry__project__in=projects_for(user, Project.objects.all(), MANAGERS)
            ).exclude(created_by=user)
            if prepayments.exists():
                result['prepayments'] = bucket(prepayments, ReconciliationSerializer, 'prepayments')
        if has_role(user, FINANCE):
            statements = pending.exclude(kind='prepayment')
            if statements.exists():
                result['reconciliations'] = bucket(statements, ReconciliationSerializer, 'reconciliations')
            banks = (
                bank_list(with_remaining(BankRecord.objects.filter(void_reason='')))
                .filter(net_remaining__gt=0)
                .select_related('project')
                .order_by('date', 'id')
            )
            if banks.exists():
                result['bank_records'] = bucket(banks, BankSerializer, 'bank_records')
    return {key: value for key, value in result.items() if value is not None}
