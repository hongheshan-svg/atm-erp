from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.models import CodeRule
from apps.core.permissions import MANAGERS, require_role, role

from ..models import Partner, Project, SalesOrder
from . import finance, projects
from .common import ZERO, audit, day, fields, identity, integer, lookup, number, rows, save, state, text

DETAIL_FIELDS = {'name', 'customer', 'manager', 'requirements', 'due_date', 'equipment_quantity', 'warranty_months'}


def detail_values(data):
    manager = lookup(User, data.get('manager'), 'manager', is_active=True)
    if role(manager) not in MANAGERS:
        raise ValidationError({'manager': '销售负责人必须是管理员或项目经理。'})
    return {
        'name': text(data, 'name', maximum=150),
        'customer': lookup(Partner, data.get('customer'), 'customer', is_active=True, kind__in=['customer', 'both']),
        'manager': manager,
        'requirements': text(data, 'requirements', default='', maximum=20000),
        'due_date': day(data, 'due_date', optional=True),
        'equipment_quantity': integer(data, 'equipment_quantity', 1, minimum=1),
        'warranty_months': integer(data, 'warranty_months', 12, maximum=120),
    }


def detail_snapshot(sale):
    return {
        'name': sale.name,
        'customer': sale.customer_id,
        'manager': sale.manager_id,
        'requirements': sale.requirements,
        'due_date': sale.due_date.isoformat() if sale.due_date else None,
        'equipment_quantity': sale.equipment_quantity,
        'warranty_months': sale.warranty_months,
    }


def create(actor, key, data):
    def execute(user):
        fields(data, DETAIL_FIELDS)
        sale = save(
            SalesOrder(
                code=CodeRule.generate_code('sale'),
                **detail_values(data),
            ),
            user,
        )
        return audit(user, 'sale.create', sale)

    return perform(
        actor=actor,
        key=key,
        operation='sale.create',
        payload=data,
        authorize=lambda user: require_role(user, MANAGERS),
        execute=execute,
    )


def action(actor, key, operation, sale_id, data, execute):
    return perform(
        actor=actor,
        key=key,
        operation=operation,
        payload={'id': sale_id, 'data': data},
        authorize=lambda user: require_role(user, MANAGERS),
        execute=lambda user: execute(
            user, get_object_or_404(SalesOrder.objects.select_for_update(), pk=identity(sale_id))
        ),
    )


def quote(actor, key, sale_id, data):
    def execute(user, sale):
        fields(data, {'amount', 'reason'})
        state(sale, {'draft', 'quoted'})
        reason = text(data, 'reason')
        before = str(sale.quote_amount)
        sale.quote_amount = number(data.get('amount'), 'amount', positive=True)
        sale.status = 'quoted'
        save(sale, user)
        return audit(user, 'sale.quote', sale, before=before, after=str(sale.quote_amount), reason=reason)

    return action(actor, key, 'sale.quote', sale_id, data, execute)


def edit(actor, key, sale_id, data):
    def execute(user, sale):
        fields(data, DETAIL_FIELDS | {'reason', 'expected_updated_at'})
        state(sale, {'draft', 'quoted'})
        reason = text(data, 'reason')
        version = data.get('expected_updated_at')
        try:
            expected = parse_datetime(version) if isinstance(version, str) else None
        except ValueError:
            expected = None
        if expected is None:
            raise ValidationError({'expected_updated_at': '请提供打开表单时的记录版本。'})
        if expected != sale.updated_at:
            raise Conflict('销售单已更新，请刷新后重新编辑。')
        before = detail_snapshot(sale)
        values = detail_values({**before, **{key: value for key, value in data.items() if key in DETAIL_FIELDS}})
        for field, value in values.items():
            setattr(sale, field, value)
        after = detail_snapshot(sale)
        if before == after:
            raise ValidationError('没有需要保存的修改。')
        previous_quote = str(sale.quote_amount)
        sale.status = 'draft'
        sale.quote_amount = ZERO
        save(sale, user)
        return audit(user, 'sale.edit', sale, before=before, after=after, previous_quote=previous_quote, reason=reason)

    return action(actor, key, 'sale.edit', sale_id, data, execute)


def sign(actor, key, sale_id, data):
    def execute(user, sale):
        fields(data, {'date', 'milestones', 'manager', 'members', 'contract_number'})
        state(sale, {'quoted'})
        # Serialize contract identifiers with the existing sales numbering lock.
        CodeRule.objects.select_for_update().get(key='sale')
        sale.contract_number = text(data, 'contract_number', default='', maximum=80) or None
        if sale.contract_number and SalesOrder.all_objects.filter(contract_number=sale.contract_number).exists():
            raise ValidationError({'contract_number': '合同编号已使用。'})
        milestones = []
        for row in rows(data, 'milestones'):
            fields(row, {'title', 'amount', 'due_date'})
            milestones.append(
                {
                    'title': text(row, 'title', maximum=150),
                    'amount': number(row.get('amount'), 'amount', positive=True),
                    'due_date': day(row, 'due_date'),
                }
            )
        if sum((row['amount'] for row in milestones), ZERO) != sale.quote_amount:
            raise ValidationError({'milestones': '收款节点合计必须等于最终报价。'})
        sale.contract_date = day(data, 'date')
        if sale.project_id:
            # Forward-migrated pre-contract records retain their original project identity and members.
            project = get_object_or_404(Project.objects.select_for_update(), pk=sale.project_id)
            state(project, {'draft', 'quoted'})
            if 'manager' in data or 'members' in data:
                raise ValidationError('历史项目请先在项目中维护执行人员。')
            for field in DETAIL_FIELDS - {'manager'}:
                setattr(project, field, getattr(sale, field))
            project.status = 'active'
            save(project, user)
        else:
            project = projects.create_record(
                user,
                {
                    'name': sale.name,
                    'customer': sale.customer_id,
                    'manager': data.get('manager', sale.manager_id),
                    'members': data.get('members', []),
                    'requirements': sale.requirements,
                    'due_date': str(sale.due_date) if sale.due_date else None,
                    'equipment_quantity': sale.equipment_quantity,
                    'warranty_months': sale.warranty_months,
                },
            )
        sale.project = project
        sale.contract_amount = sale.quote_amount
        sale.original_contract_amount = sale.quote_amount
        sale.status = 'signed'
        save(sale, user)
        finance.record_contract(user, project, milestones)
        result = audit(
            user,
            'sale.sign',
            sale,
            project=project.pk,
            amount=str(sale.contract_amount),
            milestones=len(milestones),
            contract_number=sale.contract_number,
        )
        return {**result, 'project': project.pk}

    return action(actor, key, 'sale.sign', sale_id, data, execute)


def cancel(actor, key, sale_id, data):
    def execute(user, sale):
        fields(data, {'reason'})
        state(sale, {'draft', 'quoted'})
        reason = text(data, 'reason')
        sale.status = 'cancelled'
        save(sale, user)
        return audit(user, 'sale.cancel', sale, reason=reason)

    return action(actor, key, 'sale.cancel', sale_id, data, execute)
