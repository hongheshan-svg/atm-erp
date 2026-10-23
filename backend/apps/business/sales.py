from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import SALES, SALES_READERS, project_read_allowed, sales_for

from .api.common import ImportableMixin, ReadView, key
from .models import Project, SalesOrder
from .serializers import PersonNameField
from .services import amendments, finance, progress, sales

# 签约时合同额、原签约额均取自报价，三者都等于项目合同金额，按项目金额范围一起隐藏。
SALE_AMOUNTS = ('quote_amount', 'contract_amount', 'original_contract_amount')


def sale_amounts_visible(request, sale):
    """未签约（未关联项目）与本人负责的销售照常可见；关联项目后按该项目的金额读取范围（同项目合同额）。"""
    return (
        sale.project_id is None or sale.manager_id == request.user.pk or project_read_allowed(request, sale.project_id)
    )


class SalesSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    manager_name = PersonNameField(source='manager')
    project_code = serializers.CharField(source='project.code', read_only=True, default=None)
    project_status = serializers.CharField(source='project.status', read_only=True, default=None)
    amounts_visible = serializers.SerializerMethodField()
    can_transfer = serializers.SerializerMethodField()

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
            'project_status',
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
            'amounts_visible',
            'can_transfer',
        ]

    def get_amounts_visible(self, sale):
        return sale_amounts_visible(self.context['request'], sale)

    def get_can_transfer(self, sale):
        return sale.status == 'signed' and sales.may_transfer(self.context['request'].user, sale)

    def to_representation(self, instance):
        result = super().to_representation(instance)
        if not result['amounts_visible']:
            for field in SALE_AMOUNTS:
                result.pop(field, None)
        return result


class SalesView(ImportableMixin, ReadView):
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
            return Response({'project_status': None, 'deliveries': [], 'receivables': [], 'amounts_visible': True})
        # 无该项目金额权限时整体不返回应收节点：标题、到期日和结清状态同样会透露合同款安排与回款进度。
        visible = sale_amounts_visible(request, sale)
        return Response(
            {
                'progress_project': sale.project_id
                if progress.readable_projects(request.user, Project.objects.filter(pk=sale.project_id)).exists()
                else None,
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
                    for entry in (sale.project.entries.filter(kind='receivable') if visible else [])
                ],
                'amounts_visible': visible,
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
    def transfer(self, request, pk=None):
        return Response(sales.transfer(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def amend(self, request, pk=None):
        return Response(amendments.amend(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['get'], url_path='amendments')
    def amendment_history(self, request, pk=None):
        sale = self.get_object()
        records = list(
            sale.amendments.order_by('pk').values(
                'id', 'date', 'reason', 'before', 'after', 'document', 'document__original_name', 'created_by'
            )
        )
        if not sale_amounts_visible(request, sale):
            # 补充协议金额与协议合同附件随项目合同额一起隐藏，设备数量、质保月数等非金额变更仍可追溯。
            for record in records:
                for side in ('before', 'after'):
                    record[side] = {name: value for name, value in record[side].items() if name != 'amount'}
                record['document'] = record['document__original_name'] = None
        return Response(records)
