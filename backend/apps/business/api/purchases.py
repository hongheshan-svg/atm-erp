from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import AuditLog
from apps.core.permissions import (
    MONEY_READERS,
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

    @action(detail=True, methods=['get'], url_path='contract-preview')
    def contract_preview(self, request, pk=None):
        from ..services.purchase_contract import preview

        return Response(preview(request.user, self.get_object()))

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
        require_role(request.user, MONEY_READERS)
        return Response(budgets.purchase_check(self.get_object()))

    @action(detail=True, methods=['post'], url_path='approve-over-budget')
    def approve_over_budget(self, request, pk=None):
        return Response(supply.approve(request.user, key(request), self.get_object().pk, request.data, override=True))

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        return Response(supply.receive(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='cancel-remainder')
    def cancel_remainder(self, request, pk=None):
        return Response(supply.cancel_remainder(request.user, key(request), self.get_object().pk, request.data))
