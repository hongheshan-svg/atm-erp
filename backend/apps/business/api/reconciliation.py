from django.db.models import Prefetch
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import FINANCE, MANAGERS, MONEY_READERS

from ..models import BankMatch, BankOffset, BankRecord, Reconciliation
from ..services import bank_import, banking, reconciliation
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
    queryset = reconciliation.with_snapshot_sources(Reconciliation.objects.all()).order_by('-id')
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
        cached = getattr(obj, 'list_returns' if obj.amount > 0 else 'list_return_sources', None)
        if cached is not None:
            return [
                {
                    'id': r.pk,
                    'source_id': r.source_id,
                    'returned_id': r.returned_id,
                    'amount': r.amount,
                    'reason': r.reason,
                    'reversal_of': r.reversal_of_id,
                    'reversal__id': getattr(getattr(r, 'reversal', None), 'pk', None),
                }
                for r in cached
            ]
        records = obj.returned_funds if obj.amount > 0 else obj.return_sources
        return list(
            records.order_by('pk').values(
                'id', 'source_id', 'returned_id', 'amount', 'reason', 'reversal_of', 'reversal__id'
            )
        )

    def get_remaining_amount(self, obj):
        return str(banking.remaining(obj))

    def get_matches(self, obj):
        if hasattr(obj, 'list_matches'):
            return [
                {
                    'id': r.pk,
                    'payment_id': r.payment_id,
                    'payment__entry__title': r.payment.entry.title,
                    'amount': r.amount,
                    'reason': r.reason,
                    'reversal_of': r.reversal_of_id,
                    'reversal__id': getattr(getattr(r, 'reversal', None), 'pk', None),
                }
                for r in obj.list_matches
            ]
        return list(
            obj.matches.order_by('pk').values(
                'id', 'payment_id', 'payment__entry__title', 'amount', 'reason', 'reversal_of', 'reversal__id'
            )
        )

    class Meta:
        model = BankRecord
        fields = [
            'id',
            'source',
            'needs_review',
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


def bank_list(queryset):
    returns = BankOffset.objects.select_related('reversal').order_by('pk')
    return queryset.prefetch_related(
        Prefetch(
            'matches',
            queryset=BankMatch.objects.select_related('payment__entry', 'reversal').order_by('pk'),
            to_attr='list_matches',
        ),
        Prefetch('returned_funds', queryset=returns, to_attr='list_returns'),
        Prefetch('return_sources', queryset=returns, to_attr='list_return_sources'),
    )


class BankView(ReadView):
    read_roles = write_roles = FINANCE
    queryset = bank_list(banking.with_remaining(BankRecord.objects.select_related('project'))).order_by('-id')
    serializer_class = BankSerializer
    filterset_fields = ['project', 'needs_review']
    search_fields = ['account', 'reference', 'counterparty']

    def create(self, request):
        return Response(banking.create(request.user, key(request), request.data), status=201)

    @action(detail=False, methods=['post'], url_path='import-file', parser_classes=[MultiPartParser])
    def import_file(self, request):
        if set(request.data) != {'file'} or len(request.FILES.getlist('file')) != 1:
            raise ValidationError('请上传一个银行流水文件。')
        return Response(bank_import.preview(request.user, request.FILES['file']))

    @action(detail=False, methods=['post'], url_path='import-confirm')
    def import_confirm(self, request):
        if set(request.data) != {'token'}:
            raise ValidationError('请提交预览凭据。')
        return Response(bank_import.confirm(request.user, request.data['token']))

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        return Response(banking.review(request.user, key(request), self.get_object().pk, request.data))

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
