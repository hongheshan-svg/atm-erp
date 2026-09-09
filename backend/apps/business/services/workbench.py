from django.core.paginator import Paginator
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.permissions import MANAGERS, MONEY_READERS, PURCHASERS, WAREHOUSE, projects_for, role

from ..models import Entry, Project, PurchaseOrder, Task
from ..serializers import EntrySerializer, PurchaseSerializer, TaskSerializer
from .common import ZERO


def summary(request):
    user = request.user
    projects = projects_for(user, Project.objects.all())

    def bucket(queryset, serializer, name):
        try:
            page = int(request.query_params.get(f'{name}_page', '1'))
        except (TypeError, ValueError):
            raise ValidationError('待办页码必须为正整数。')
        if page < 1:
            raise ValidationError('待办页码必须为正整数。')
        selected = Paginator(queryset, 20).get_page(page)
        return {
            'page': selected.number,
            'count': queryset.count(),
            'results': serializer(selected.object_list, many=True, context={'request': request}).data,
        }

    tasks = (
        Task.objects.filter(project__in=projects, assignee=user, status='open')
        .exclude(project__status__in=['closed', 'cancelled'])
        .order_by(F('due_date').asc(nulls_last=True), 'pk')
    )
    result = {'tasks': bucket(tasks, TaskSerializer, 'tasks')}
    purchases = (
        PurchaseOrder.objects.filter(project__in=projects)
        .select_related('project', 'supplier')
        .prefetch_related('lines__item', 'lines__bom_line')
        .order_by('due_date', 'pk')
    )
    if role(user) in MANAGERS:
        result['approvals'] = bucket(purchases.filter(status='submitted'), PurchaseSerializer, 'approvals')
    if role(user) in WAREHOUSE:
        result['receipts'] = bucket(
            purchases.filter(status__in=['approved', 'partial']), PurchaseSerializer, 'receipts'
        )
    if role(user) in PURCHASERS:
        result['drafts'] = bucket(purchases.filter(status='draft', created_by=user), PurchaseSerializer, 'drafts')
    if role(user) in PURCHASERS | WAREHOUSE:
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
    if role(user) in MONEY_READERS:
        amount = DecimalField(max_digits=18, decimal_places=2)
        entries = (
            Entry.objects.filter(project__in=projects)
            .exclude(project__status='closed')
            .select_related('project')
            .annotate(net_paid=Coalesce(Sum('payments__amount'), Value(ZERO), output_field=amount))
            .annotate(remaining=F('amount') - F('credit_amount') - F('net_paid'))
            .filter(Q(remaining__lt=0) | Q(remaining__gt=0, due_date__lte=timezone.localdate()))
            .order_by('due_date', 'pk')
        )
        result['settlements'] = bucket(entries, EntrySerializer, 'settlements')
    return result
