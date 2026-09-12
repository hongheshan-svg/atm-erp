from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import AuditLog
from apps.core.permissions import (
    MONEY_READERS,
    PURCHASE_APPROVERS,
    PURCHASE_READERS,
    require_role,
)

from ..models import (
    PurchaseOrder,
)
from ..serializers import (
    PurchaseSerializer,
)
from ..services import budgets, supply
from .common import ReadView, key


class PurchaseView(ReadView):
    read_roles = PURCHASE_READERS
    write_roles = PURCHASE_READERS
    queryset = PurchaseOrder.objects.select_related('supplier', 'project').prefetch_related(
        'lines__item', 'lines__bom_line'
    )
    serializer_class = PurchaseSerializer
    filterset_fields = ['project', 'supplier', 'status']
    search_fields = ['code', 'supplier__name', 'project__name']

    @action(detail=True, methods=['get', 'post'])
    def warranty(self, request, pk=None):
        from ..services import purchase_warranty

        purchase = self.get_object()
        if request.method == 'POST':
            return Response(purchase_warranty.record(request.user, key(request), purchase.pk, request.data))
        return Response(purchase_warranty.listing(purchase))

    @action(detail=True, methods=['get'], url_path='contract-preview')
    def contract_preview(self, request, pk=None):
        from ..services.purchase_contract import fingerprint, preview

        purchase = self.get_object()
        current = preview(request.user, purchase)
        versions = purchase.contract_versions.order_by('-version')
        selected = request.query_params.get('version')
        if selected and selected != 'current':
            from django.shortcuts import get_object_or_404
            from rest_framework.exceptions import ValidationError

            if not selected.isdecimal() or len(selected) > 9 or int(selected) < 1:
                raise ValidationError({'version': '请选择有效的合同版本。'})
            saved = get_object_or_404(versions, version=selected)
        else:
            saved = versions.first() if selected != 'current' else None
        return Response(
            {
                **(saved.snapshot if saved else current),
                'snapshot_hash': fingerprint(current),
                'archived_version': saved.version if saved else None,
                'signed_document': saved.document_id if saved else None,
                'versions': list(versions.values('version', 'created_at', 'document_id', 'reason')),
            }
        )

    @action(detail=True, methods=['post'], url_path='archive-contract')
    def archive_contract(self, request, pk=None):
        from ..services.purchase_contract import archive

        return Response(archive(request.user, key(request), self.get_object().pk, request.data), status=201)

    def create(self, request):
        return Response(supply.create_purchase(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        return Response(supply.submit(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return Response(supply.reject(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        return Response(supply.edit(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='delivery-plan')
    def delivery_plan(self, request, pk=None):
        return Response(supply.delivery_plan(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='quality-accept')
    def quality_accept(self, request, pk=None):
        return Response(
            supply.receive(request.user, key(request), self.get_object().pk, request.data, from_quarantine=True)
        )

    @action(detail=True, methods=['post'], url_path='quality-return')
    def quality_return(self, request, pk=None):
        return Response(supply.quality_return(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['get'], url_path='handling-history')
    def handling_history(self, request, pk=None):
        purchase = self.get_object()
        logs = AuditLog.objects.filter(
            resource=f'purchaseorder:{purchase.pk}',
            operation__in=[
                'purchase.reject',
                'purchase.edit',
                'purchase.receive',
                'purchase.quality_accept',
                'purchase.quality_return',
                'purchase.delivery_plan',
            ],
        ).select_related('actor')
        page = self.paginate_queryset(logs)
        return self.get_paginated_response(
            [
                {
                    'id': log.pk,
                    'date': log.created_at,
                    'actor': log.actor.display_name,
                    'operation': log.operation,
                    'reason': log.detail.get('reason', ''),
                    'lines': [
                        {
                            key: value
                            for key, value in row.items()
                            if key in {'line', 'id', 'quantity', 'pending_quantity', 'due_date'}
                        }
                        for row in log.detail.get('lines', [])
                    ],
                    'next_step': '等待供应商补货；不再补货时由采购取消未收余量'
                    if log.operation == 'purchase.quality_return'
                    else '',
                }
                for log in page
            ]
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return Response(supply.approve(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['get'], url_path='budget-check')
    def budget_check(self, request, pk=None):
        require_role(request.user, MONEY_READERS | PURCHASE_APPROVERS)
        return Response(budgets.purchase_visibility(request.user, budgets.purchase_check(self.get_object())))

    @action(detail=True, methods=['post'], url_path='approve-over-budget')
    def approve_over_budget(self, request, pk=None):
        return Response(supply.approve(request.user, key(request), self.get_object().pk, request.data, override=True))

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        return Response(supply.receive(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='cancel-remainder')
    def cancel_remainder(self, request, pk=None):
        return Response(supply.cancel_remainder(request.user, key(request), self.get_object().pk, request.data))
