from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import MANAGERS, MONEY_READERS

from .api.common import ReadView, key
from .models import SalesOrder
from .services import sales


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
            'contract_date',
            'created_at',
            'updated_at',
        ]


class SalesView(ReadView):
    queryset = SalesOrder.objects.select_related('customer', 'manager', 'project')
    serializer_class = SalesSerializer
    read_roles = MONEY_READERS
    write_roles = MANAGERS
    search_fields = ['code', 'name', 'customer__name']
    filterset_fields = ['status', 'customer', 'manager', 'project']

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
