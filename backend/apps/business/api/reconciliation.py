from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import FINANCE, MANAGERS, MONEY_READERS

from ..models import BankMatch, BankRecord, Reconciliation
from ..services import banking, reconciliation
from .common import ReadView, key


class ReconciliationSerializer(serializers.ModelSerializer):
    project = serializers.IntegerField(source='entry.project_id', read_only=True)
    project_name = serializers.CharField(source='entry.project.name', read_only=True)
    entry_title = serializers.CharField(source='entry.title', read_only=True)
    valid = serializers.SerializerMethodField()
    difference = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    confirmed_name = serializers.CharField(source='confirmed_by.display_name', read_only=True, default='')

    def get_valid(self, obj):
        return obj.status != 'void' and reconciliation.current(obj)

    def get_difference(self, obj):
        return str(reconciliation.difference(obj))

    def get_remaining_amount(self, obj):
        return str(obj.approved_amount - reconciliation.used(obj))

    class Meta:
        model = Reconciliation
        fields = [
            'id',
            'code',
            'entry',
            'entry_title',
            'project',
            'project_name',
            'kind',
            'settlement_month',
            'status',
            'snapshot',
            'counterparty_balance',
            'difference',
            'approved_amount',
            'remaining_amount',
            'valid',
            'basis',
            'document',
            'reason',
            'confirmed_name',
            'confirmed_at',
            'void_reason',
            'created_at',
        ]


class ReconciliationView(ReadView):
    read_roles = MONEY_READERS
    write_roles = FINANCE | MANAGERS
    queryset = Reconciliation.objects.select_related(
        'entry__project', 'entry__purchase__supplier', 'confirmed_by'
    ).order_by('-id')
    serializer_class = ReconciliationSerializer
    filterset_fields = ['entry', 'entry__project', 'status', 'kind']
    search_fields = ['code', 'entry__title', 'entry__project__name']

    @action(detail=False, methods=['get', 'post'], url_path='supplier-monthly')
    def supplier_monthly(self, request):
        from ..services import monthly

        if request.method == 'POST':
            return Response(monthly.confirm(request.user, key(request), request.data))
        return Response(
            monthly.summary(request.user, request.query_params.get('supplier'), request.query_params.get('month'))
        )

    def create(self, request):
        return Response(reconciliation.create(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        return Response(reconciliation.action(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        return Response(
            reconciliation.action(request.user, key(request), self.get_object().pk, request.data, void=True)
        )


class BankSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True, default='未指定')
    remaining_amount = serializers.SerializerMethodField()
    matches = serializers.SerializerMethodField()
    returns = serializers.SerializerMethodField()

    def get_returns(self, obj):
        records = obj.returned_funds if obj.amount > 0 else obj.return_sources
        return list(
            records.order_by('pk').values(
                'id', 'source_id', 'returned_id', 'amount', 'reason', 'reversal_of', 'reversal__id'
            )
        )

    def get_remaining_amount(self, obj):
        return str(banking.remaining(obj))

    def get_matches(self, obj):
        return list(
            obj.matches.order_by('pk').values(
                'id', 'payment_id', 'payment__entry__title', 'amount', 'reason', 'reversal_of', 'reversal__id'
            )
        )

    class Meta:
        model = BankRecord
        fields = [
            'id',
            'project',
            'project_name',
            'amount',
            'remaining_amount',
            'date',
            'account',
            'reference',
            'counterparty',
            'reason',
            'void_reason',
            'matches',
            'returns',
            'created_at',
        ]


class BankView(ReadView):
    read_roles = write_roles = FINANCE
    queryset = banking.with_remaining(BankRecord.objects.select_related('project')).order_by('-id')
    serializer_class = BankSerializer
    filterset_fields = ['project']
    search_fields = ['account', 'reference', 'counterparty']

    def create(self, request):
        return Response(banking.create(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['post'])
    def allocate(self, request, pk=None):
        return Response(banking.match(request.user, key(request), self.get_object().pk, request.data, allocate=True))

    @action(detail=True, methods=['post'])
    def match(self, request, pk=None):
        return Response(banking.match(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def unmatch(self, request, pk=None):
        from ..services.common import fields, lookup

        fields(request.data, {'match', 'reason'})
        source = lookup(BankMatch, request.data.get('match'), 'match', bank=self.get_object())
        return Response(banking.unmatch(request.user, key(request), source.pk, {'reason': request.data.get('reason')}))

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        return Response(banking.void(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='return-unclaimed')
    def return_unclaimed(self, request, pk=None):
        return Response(banking.return_unclaimed(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='reverse-return')
    def reverse_return(self, request, pk=None):
        return Response(
            banking.return_unclaimed(request.user, key(request), self.get_object().pk, request.data, reverse=True)
        )


class BankMatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankMatch
        fields = ['id', 'bank', 'payment', 'amount', 'reversal_of', 'reason']


class BankMatchView(ReadView):
    read_roles = write_roles = FINANCE
    queryset = BankMatch.objects.all().order_by('-id')
    serializer_class = BankMatchSerializer
    filterset_fields = ['bank', 'payment']

    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        return Response(banking.unmatch(request.user, key(request), self.get_object().pk, request.data))
