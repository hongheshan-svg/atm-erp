"""Read-only operating report; all costs and commitments reuse their source projections."""

from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import serializers

from ..models import Entry, Project
from . import budgets, finance
from .common import ZERO, rounded


class ReportFilters(serializers.Serializer):
    search = serializers.CharField(required=False, default='', allow_blank=True, max_length=150)
    status = serializers.ChoiceField(choices=['', *Project.Status.values], required=False, default='')
    risk = serializers.ChoiceField(choices=['', 'over_budget', 'overdue', 'unbudgeted'], required=False, default='')
    page = serializers.IntegerField(min_value=1, max_value=1000000, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=200, required=False, default=20)


def summary(params, *, export=False):
    filters = ReportFilters(data=params)
    filters.is_valid(raise_exception=True)
    values = filters.validated_data
    projects = Project.objects.select_related('manager', 'sale').order_by('-pk')
    if values['search']:
        projects = projects.filter(Q(code__icontains=values['search']) | Q(name__icontains=values['search']))
    if values['status']:
        projects = projects.filter(status=values['status'])
    projects = list(projects)
    ids = [project.pk for project in projects]
    actuals, commitments, purchases = finance.costs(ids), budgets.commitments(ids), budgets.purchase_totals(ids)
    money_keys = ['receivable', 'payable', 'overdue_receivable', 'overdue_payable', 'refund_out', 'refund_in']
    balances = {pk: dict.fromkeys(money_keys, ZERO) for pk in ids}
    today = timezone.localdate()
    entries = Entry.objects.filter(project_id__in=ids).annotate(paid=Sum('payments__amount'))
    for entry in entries:
        remaining = entry.amount - entry.credit_amount - (entry.paid or ZERO)
        incoming = entry.kind == 'receivable'
        key = 'receivable' if incoming else 'payable'
        if remaining > ZERO:
            balances[entry.project_id][key] += remaining
            if entry.due_date < today:
                balances[entry.project_id]['overdue_' + key] += remaining
        elif remaining < ZERO:
            balances[entry.project_id]['refund_out' if incoming else 'refund_in'] -= remaining
    rows = []
    for project in projects:
        budget = budgets.analysis(
            project, actuals=actuals[project.pk], committed=commitments[project.pk], purchase_net=purchases[project.pk]
        )
        sale = getattr(project, 'sale', None)
        if sale and sale.is_deleted:
            sale = None
        contract = sale.contract_amount if sale and sale.status == 'signed' else ZERO
        overdue = bool(project.due_date and project.due_date < today and project.status in ['active', 'delivering'])
        flags = {'over_budget': budget['over_budget'], 'overdue': overdue, 'unbudgeted': not budget['configured']}
        if values['risk'] and not flags[values['risk']]:
            continue
        rows.append(
            {
                'id': project.pk,
                'code': project.code,
                'name': project.name,
                'manager': project.manager.display_name or project.manager.username,
                'status': project.status,
                'due_date': project.due_date,
                'contract_number': sale.contract_number if sale else None,
                'contract_amount': str(rounded(contract)),
                'actual_cost': budget['actual_total'],
                'committed_cost': budget['committed_total'],
                'budget': budget['budget_total'],
                'occupied_cost': budget['occupied_total'],
                'warnings': budget['warnings'],
                **flags,
                **{key: str(rounded(value)) for key, value in balances[project.pk].items()},
            }
        )
    totals = {
        key: str(rounded(sum((Decimal(row[key]) for row in rows), ZERO)))
        for key in ['contract_amount', 'actual_cost', 'committed_cost', *money_keys]
    }
    totals.update(
        projects=len(rows),
        active_projects=sum(row['status'] in ['active', 'delivering', 'warranty'] for row in rows),
        over_budget=sum(row['over_budget'] for row in rows),
        overdue=sum(row['overdue'] for row in rows),
        unbudgeted=sum(row['unbudgeted'] for row in rows),
    )
    size = values['page_size']
    start = (values['page'] - 1) * size
    return {
        'generated_at': timezone.now(),
        'filters': values,
        'summary': totals,
        'count': len(rows),
        'page': values['page'],
        'page_size': size,
        'results': rows if export else rows[start : start + size],
    }
