from django.db.models import DecimalField, Exists, F, OuterRef, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import (
    FINANCE,
    MONEY_READERS,
)

from ..models import (
    BankMatch,
    Entry,
    Payment,
)
from ..serializers import (
    EntrySerializer,
    PaymentSerializer,
)
from ..services import finance
from ..services.payment_terms import with_sources
from .common import ReadView, key


class EntryView(ReadView):
    read_roles = MONEY_READERS
    write_roles = FINANCE
    queryset = (
        with_sources(Entry.objects.select_related('project'))
        .annotate(
            net_paid=Coalesce(
                Sum('payments__amount'), Value(0), output_field=DecimalField(max_digits=18, decimal_places=2)
            )
        )
        .order_by('-id')
    )
    serializer_class = EntrySerializer
    filterset_fields = ['project', 'kind', 'cancelled']
    search_fields = ['title', 'project__name', 'project__code']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('unsettled') == 'true':
            queryset = queryset.exclude(amount=F('credit_amount') + F('net_paid'))
        return queryset

    @action(detail=False, methods=['post'])
    def expense(self, request):
        return Response(finance.expense(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        return Response(finance.pay(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        return Response(finance.pay(request.user, key(request), self.get_object().pk, request.data, refund=True))

    @action(detail=True, methods=['post'], url_path='cancel-expense')
    def cancel_expense(self, request, pk=None):
        return Response(finance.cancel_expense(request.user, key(request), self.get_object().pk, request.data))


class PaymentView(ReadView):
    read_roles = MONEY_READERS
    write_roles = FINANCE
    queryset = (
        Payment.objects.select_related('entry', 'reversal', 'document')
        .annotate(
            bank_matched=Exists(
                BankMatch.objects.filter(payment=OuterRef('pk'), reversal_of__isnull=True, reversal__isnull=True)
            )
        )
        .prefetch_related('evidence__document', 'evidence__created_by')
    )
    serializer_class = PaymentSerializer
    filterset_fields = ['entry', 'entry__project']

    @action(detail=True, methods=['post'], url_path='attach-evidence')
    def attach_evidence(self, request, pk=None):
        return Response(finance.attach_evidence(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        return Response(finance.reverse(request.user, key(request), self.get_object().pk, request.data))
