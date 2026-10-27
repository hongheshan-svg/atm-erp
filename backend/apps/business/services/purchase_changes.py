"""Submitted PO change requests use the existing immutable handling history as their only source."""

from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.models import AuditLog
from apps.core.permissions import PURCHASE_APPROVERS, PURCHASERS

from .approval import independent_approval
from .common import audit, fields, identity, save, state, text

REQUEST = 'purchase.request_change'
REVIEW = 'purchase.review_change'


def pending_requests(purchases):
    resources = {f'purchaseorder:{p.pk}': p.pk for p in purchases if p.status == 'submitted'}
    if not resources:
        return {}
    # One query per page, including resolutions so an older request never becomes pending again.
    latest = (
        AuditLog.objects.filter(
            resource__in=resources, operation__in=[REQUEST, REVIEW, 'purchase.reject', 'purchase.submit']
        )
        .order_by('resource', '-id')
        .distinct('resource')
        .select_related('actor')
    )
    return {
        resources[log.resource]: {
            'id': log.pk,
            'reason': log.detail['reason'],
            'requested_by': log.actor.display_name or log.actor.username,
            'requested_by_id': log.actor_id,
            'requested_at': log.created_at.isoformat(),
        }
        for log in latest
        if log.operation == REQUEST
    }


def require_no_request(purchase):
    if pending_requests([purchase]):
        raise Conflict('本单有待处理的修改申请，请先处理申请，再决定是否批准采购。')


def request_change(actor, key, purchase_id, data):
    from .supply import purchase_action

    def execute(user, purchase):
        fields(data, {'reason'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'submitted'})
        require_no_request(purchase)
        reason = text(data, 'reason')
        save(purchase, user)
        return audit(user, REQUEST, purchase, reason=reason)

    return purchase_action(actor, key, REQUEST, purchase_id, data, PURCHASERS, execute)


def review_change(actor, key, purchase_id, data):
    from .supply import purchase_action, purchase_applicants

    def execute(user, purchase):
        fields(data, {'request_id', 'decision', 'reason'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'submitted'})
        request_id = identity(data.get('request_id'), 'request_id')
        pending = pending_requests([purchase]).get(purchase.pk)
        if not pending or pending['id'] != request_id:
            raise Conflict('修改申请已处理或发生变化，请刷新采购单。')
        decision = data.get('decision')
        if not isinstance(decision, str) or decision not in {'approve', 'reject'}:
            raise ValidationError({'decision': '请选择同意退回修改或驳回申请。'})
        reason = text(data, 'reason')
        self_approval = independent_approval(user, purchase_applicants(purchase), reason)
        if decision == 'approve':
            purchase.status = 'draft'
        save(purchase, user)
        return audit(
            user,
            REVIEW,
            purchase,
            request_id=request_id,
            decision=decision,
            reason=reason,
            self_approval=self_approval,
        )

    return purchase_action(actor, key, REVIEW, purchase_id, data, PURCHASE_APPROVERS, execute)
