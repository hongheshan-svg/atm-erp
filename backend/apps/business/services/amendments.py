"""Append-only supplementary agreements; settlement adjustments reuse Entry."""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.permissions import MANAGERS

from ..models import ContractAmendment, Document, Entry, SalesOrder
from .common import ZERO, audit, day, fields, identity, integer, lookup, number, project_action, rows, save, state, text
from .finance import record_contract


def amend(actor, key, sale_id, data):
    source = lookup(SalesOrder, sale_id)
    if not source.project_id:
        raise Conflict('请先签约。')

    def execute(user, project):
        fields(
            data,
            {
                'expected_updated_at',
                'reason',
                'document',
                'date',
                'amount',
                'equipment_quantity',
                'warranty_months',
                'milestones',
                'credits',
            },
        )
        state(project, {'active', 'delivering', 'warranty'})
        sale = get_object_or_404(SalesOrder.objects.select_for_update(), pk=source.pk, project=project)
        state(sale, {'signed'})
        version = data.get('expected_updated_at')
        try:
            expected = parse_datetime(version) if isinstance(version, str) else None
        except ValueError:
            expected = None
        if expected != sale.updated_at:
            raise Conflict('合同已更新，请重新查看补充协议。')
        reason = text(data, 'reason')
        document = get_object_or_404(
            Document.objects.filter(Q(project=project) | Q(sale=sale)),
            pk=identity(data.get('document'), 'document'),
            category='contract',
        )
        date = day(data, 'date')
        if date < sale.contract_date:
            raise ValidationError('补充协议日期不能早于签约日期。')
        amount = number(data.get('amount'), 'amount')
        quantity = integer(data, 'equipment_quantity', None, minimum=1)
        warranty = integer(data, 'warranty_months', None, maximum=120)
        if quantity != project.equipment_quantity and project.deliveries.exists():
            raise Conflict('已发货项目不能改变设备总数及领料比例；新增设备请另建销售项目。')
        before = {
            'amount': str(sale.contract_amount),
            'equipment_quantity': project.equipment_quantity,
            'warranty_months': project.warranty_months,
        }
        after = {'amount': str(amount), 'equipment_quantity': quantity, 'warranty_months': warranty}
        if before == after:
            raise ValidationError('补充协议没有变更内容。')
        delta = amount - sale.contract_amount
        milestones, credits = data.get('milestones', []), data.get('credits', [])
        if not isinstance(milestones, list) or not isinstance(credits, list):
            raise ValidationError('收款节点与抵减必须为列表。')
        if delta > ZERO:
            if credits:
                raise ValidationError('增额协议不能抵减原应收。')
            prepared = []
            for row in rows({'lines': milestones}):
                fields(row, {'title', 'amount', 'due_date'})
                prepared.append(
                    {
                        'title': text(row, 'title', maximum=150),
                        'amount': number(row.get('amount'), 'amount', positive=True),
                        'due_date': day(row, 'due_date'),
                    }
                )
            if sum((row['amount'] for row in prepared), ZERO) != delta:
                raise ValidationError('新增收款节点合计必须等于合同增加金额。')
            record_contract(user, project, prepared)
        elif delta < ZERO:
            if milestones:
                raise ValidationError('减额协议不能新增应收。')
            seen, total = set(), ZERO
            for row in rows({'lines': credits}):
                fields(row, {'entry', 'amount'})
                pk = identity(row.get('entry'), 'entry')
                if pk in seen:
                    raise ValidationError('抵减款项重复。')
                seen.add(pk)
                entry = get_object_or_404(
                    Entry.objects.select_for_update(),
                    pk=pk,
                    project=project,
                    kind='receivable',
                    task__isnull=True,
                    cancelled=False,
                )
                credit = number(row.get('amount'), 'amount', positive=True)
                if credit > entry.amount - entry.credit_amount:
                    raise Conflict('抵减超过该合同款尚未抵减的金额。')
                entry.credit_amount += credit
                total += credit
                save(entry, user)
            if total != -delta:
                raise ValidationError('原合同款抵减合计必须等于合同减少金额。')
        elif milestones or credits:
            raise ValidationError('金额未变不能调整收款。')
        amendment = save(
            ContractAmendment(sale=sale, document=document, reason=reason, before=before, after=after, date=date), user
        )
        if sale.original_contract_amount is None:
            sale.original_contract_amount = sale.contract_amount
        sale.contract_amount = amount
        sale.equipment_quantity = project.equipment_quantity = quantity
        sale.warranty_months = project.warranty_months = warranty
        save(sale, user)
        save(project, user)
        return audit(user, 'sale.amend', amendment, before=before, after=after, reason=reason, document=document.pk)

    return project_action(
        actor, key, 'sale.amend', source.project_id, {'sale': source.pk, 'data': data}, MANAGERS, execute
    )
