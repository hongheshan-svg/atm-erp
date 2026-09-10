"""Budget limits are facts; actuals, open commitments and purchase usage are projections."""

import hashlib
import json
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.permissions import MANAGERS

from ..models import Entry, PurchaseLine
from .common import ZERO, audit, fields, number, project_action, rounded, save, state, text
from .finance import cost

CATEGORIES = {'materials': '材料', 'labor': '人工', 'expenses': '费用'}


def revise(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {*CATEGORIES, 'reason', 'expected_revision'})
        state(project, {'active', 'delivering', 'warranty'})
        revision = data.get('expected_revision')
        if type(revision) is not int or revision < 0:
            raise ValidationError({'expected_revision': '请提供打开预算时的版本。'})
        if revision != project.budget_revision:
            raise Conflict('预算已更新，请刷新后重新编辑。')
        reason = text(data, 'reason')
        before = {key: str(getattr(project, f'budget_{key}')) for key in CATEGORIES}
        values = {key: number(data.get(key), key) for key in CATEGORIES}
        if all(getattr(project, f'budget_{key}') == value for key, value in values.items()):
            raise ValidationError('预算没有变化。')
        for key, value in values.items():
            setattr(project, f'budget_{key}', value)
        project.budget_revision += 1
        project.budget_changed_by = user
        save(project, user)
        return audit(
            user,
            'project.budget',
            project,
            before=before,
            after={key: str(value) for key, value in values.items()},
            revision=project.budget_revision,
            reason=reason,
        )

    return project_action(actor, key, 'project.budget', project_id, data, MANAGERS, execute)


def commitments(project_ids):
    result = {pk: ZERO for pk in project_ids}
    for line in PurchaseLine.objects.filter(
        purchase__project_id__in=project_ids, purchase__status__in=['approved', 'partial']
    ).select_related('purchase'):
        result[line.purchase.project_id] += rounded(
            (line.quantity - line.cancelled_quantity) * line.unit_price
        ) - rounded(line.received_quantity * line.unit_price)
    return result


def purchase_totals(project_ids):
    result = {pk: ZERO for pk in project_ids}
    entries = Entry.objects.filter(project_id__in=project_ids, kind='payable', purchase__isnull=False, cancelled=False)
    for row in entries.values('project_id').annotate(amount=Sum('amount'), credit=Sum('credit_amount')):
        result[row['project_id']] = (row['amount'] or ZERO) - (row['credit'] or ZERO)
    return result


def analysis(project, additional=ZERO, *, actuals=None, committed=None, purchase_net=None):
    actuals = {key: Decimal(value) for key, value in (cost(project) if actuals is None else actuals).items()}
    # Use the same cumulative rounding as receipts and cancellation; returned goods
    # do not reopen a purchase line's unreceived quantity.
    committed = (commitments([project.pk])[project.pk] if committed is None else committed) + additional
    purchase_net = (purchase_totals([project.pk])[project.pk] if purchase_net is None else purchase_net) + additional
    configured = project.budget_materials is not None
    result = []
    for key, label in CATEGORIES.items():
        actual = actuals[key] + (actuals['purchase_return_variance'] if key == 'materials' else ZERO)
        pending = committed if key == 'materials' else ZERO
        budget = getattr(project, f'budget_{key}')
        occupied = actual + pending
        result.append(
            {
                'key': key,
                'label': label,
                'budget': str(budget) if configured else None,
                'actual': str(rounded(actual)),
                'committed': str(rounded(pending)),
                'occupied': str(rounded(occupied)),
                'remaining': str(rounded(budget - occupied)) if configured else None,
                'overrun': str(rounded(max(ZERO, occupied - budget))) if configured else None,
            }
        )
    budget_total = sum((getattr(project, f'budget_{key}') for key in CATEGORIES), ZERO) if configured else None
    occupied_total = actuals['total'] + committed
    warnings = []
    if configured:
        warnings = [f'{row["label"]}占用超预算 ¥{row["overrun"]}' for row in result if Decimal(row['overrun']) > ZERO]
        if purchase_net > project.budget_materials:
            warnings.append(f'累计采购净额超材料预算 ¥{rounded(purchase_net - project.budget_materials)}')
        if occupied_total > budget_total:
            warnings.append(f'合计占用超预算 ¥{rounded(occupied_total - budget_total)}')
    return {
        'configured': configured,
        'budget_revision': project.budget_revision,
        'rows': result,
        'budget_total': str(budget_total) if configured else None,
        'actual_total': str(actuals['total']),
        'committed_total': str(rounded(committed)),
        'occupied_total': str(rounded(occupied_total)),
        'purchase_net': str(rounded(purchase_net)),
        'warnings': warnings,
        'over_budget': bool(warnings),
        'forecast_revision': project.forecast_revision,
        'remaining_materials': str(project.remaining_materials) if project.remaining_materials is not None else None,
        'forecast_at': project.forecast_at.isoformat() if project.forecast_at else None,
        'forecast_by': project.forecast_by.display_name if project.forecast_by_id else None,
        'forecast_stale': project.forecast_at is None
        or (timezone.now() - project.forecast_at).days >= 30
        or project.updated_at > project.forecast_at,
        'remaining_labor': str(project.remaining_labor) if project.remaining_labor is not None else None,
        'remaining_expenses': str(project.remaining_expenses) if project.remaining_expenses is not None else None,
        'forecast_total': str(
            rounded(occupied_total + project.remaining_materials + project.remaining_labor + project.remaining_expenses)
        )
        if all(
            value is not None
            for value in (project.remaining_materials, project.remaining_labor, project.remaining_expenses)
        )
        else None,
    }


def forecast(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'remaining_materials', 'remaining_labor', 'remaining_expenses', 'expected_revision', 'reason'})
        state(project, {'active', 'delivering', 'warranty'})
        if type(data.get('expected_revision')) is not int or data['expected_revision'] != project.forecast_revision:
            raise Conflict('完工估算已更新，请刷新后重试。')
        reason = text(data, 'reason')
        before = {
            'materials': str(project.remaining_materials),
            'labor': str(project.remaining_labor),
            'expenses': str(project.remaining_expenses),
        }
        project.remaining_materials = (
            number(data['remaining_materials'], 'remaining_materials') if 'remaining_materials' in data else None
        )
        project.remaining_labor = number(data.get('remaining_labor'), 'remaining_labor')
        project.remaining_expenses = number(data.get('remaining_expenses'), 'remaining_expenses')
        project.forecast_revision += 1
        save(project, user)
        project.forecast_at = project.updated_at
        project.forecast_by = user
        project.save(update_fields=['forecast_at', 'forecast_by'])
        return audit(
            user,
            'project.forecast',
            project,
            before=before,
            materials=str(project.remaining_materials),
            labor=str(project.remaining_labor),
            expenses=str(project.remaining_expenses),
            reason=reason,
        )

    return project_action(actor, key, 'project.forecast', project_id, data, MANAGERS, execute)


def purchase_check(purchase):
    from .supply import total

    state(purchase, {'submitted'})
    amount = total(purchase)
    report = analysis(purchase.project, amount)
    report['purchase_amount'] = str(amount)
    report['purchase'] = purchase.pk
    report['snapshot'] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    return report
