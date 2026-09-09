from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import SALES, SALES_READERS, sales_for

from .api.common import ReadView, key
from .models import SalesOrder
from .services import amendments, finance, sales


class SalesSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    manager_name = serializers.CharField(source='manager.display_name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True, default=None)

    class Meta:
        model = SalesOrder
        fields = [
            'id',
            'code',
            'name',
            'customer',
            'customer_name',
            'manager',
            'manager_name',
            'project',
            'project_code',
            'status',
            'requirements',
            'due_date',
            'equipment_quantity',
            'warranty_months',
            'quote_amount',
            'contract_amount',
            'original_contract_amount',
            'contract_date',
            'contract_number',
            'created_at',
            'updated_at',
        ]


class SalesView(ReadView):
    queryset = SalesOrder.objects.select_related('customer', 'manager', 'project')
    serializer_class = SalesSerializer
    read_roles = SALES_READERS
    write_roles = SALES
    search_fields = ['code', 'name', 'customer__name', 'contract_number']
    filterset_fields = ['status', 'customer', 'manager', 'project']

    def get_queryset(self):
        return sales_for(self.request.user, super().get_queryset())

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        sale = self.get_object()
        if not sale.project_id:
            return Response({'project_status': None, 'deliveries': [], 'receivables': []})
        return Response(
            {
                'project_status': sale.project.status,
                'deliveries': list(sale.project.deliveries.values('code', 'quantity', 'shipped_date', 'accepted_date')),
                'receivables': [
                    {
                        'title': entry.title,
                        'due_date': entry.due_date,
                        'amount': str(entry.amount),
                        'credit_amount': str(entry.credit_amount),
                        'paid': f'{finance.paid(entry):.2f}',
                        'balance': f'{finance.balance(entry):.2f}',
                    }
                    for entry in sale.project.entries.filter(kind='receivable')
                ],
            }
        )

    def create(self, request):
        return Response(sales.create(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['post'])
    def quote(self, request, pk=None):
        return Response(sales.quote(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        return Response(sales.edit(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        return Response(sales.sign(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return Response(sales.cancel(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def amend(self, request, pk=None):
        return Response(amendments.amend(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['get'], url_path='amendments')
    def amendment_history(self, request, pk=None):
        return Response(
            list(
                self.get_object()
                .amendments.order_by('pk')
                .values('id', 'date', 'reason', 'before', 'after', 'document', 'document__original_name', 'created_by')
            )
        )
