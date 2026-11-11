from django.db.models import Case, DecimalField, Exists, F, OuterRef, Sum, Value, When
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
from .common import ImportableMixin, ReadView, key


class EntryView(ImportableMixin, ReadView):
    read_roles = MONEY_READERS
    write_roles = FINANCE
    queryset = (
        with_sources(Entry.objects.select_related('project__customer', 'purchase__supplier'))
        .annotate(
            net_paid=Coalesce(
                Sum('payments__amount'), Value(0), output_field=DecimalField(max_digits=18, decimal_places=2)
            )
        )
        # 未结在前、按到期日先后：同一合同的预付款、发货款、验收款按节点顺序排列，逾期项排在最上面；已结清的排后。
        .annotate(
            settled=Case(When(amount=F('credit_amount') + F('net_paid'), then=Value(1)), default=Value(0)),
        )
        .order_by('settled', 'due_date', 'id')
    )
    serializer_class = EntrySerializer
    filterset_fields = ['project', 'kind', 'cancelled']
    search_fields = ['title', 'project__name', 'project__code']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('unsettled') == 'true':
            queryset = queryset.exclude(amount=F('credit_amount') + F('net_paid'))
        return queryset

    @action(detail=False, methods=['get'])
    def summary(self, request):
        # 与列表同一套筛选和项目边界，页头卡片显示的就是当前这批款项的余额。
        # 已结清的款项不计入任何余额，先在数据库里筛掉，免得把全部历史款项连同到货明细拉进内存。
        queryset = self.filter_queryset(self.get_queryset())
        return Response(finance.balances(queryset.exclude(amount=F('credit_amount') + F('net_paid'))))

    @action(detail=False, methods=['post'])
    def expense(self, request):
        return Response(finance.expense(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        return Response(finance.pay(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        return Response(finance.pay(request.user, key(request), self.get_object().pk, request.data, refund=True))

    @action(detail=True, methods=['post'], url_path='adjust-due-date')
    def adjust_due_date(self, request, pk=None):
        return Response(finance.adjust_due_date(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='cancel-expense')
    def cancel_expense(self, request, pk=None):
        return Response(finance.cancel_expense(request.user, key(request), self.get_object().pk, request.data))


class PaymentView(ImportableMixin, ReadView):
    read_roles = MONEY_READERS
    write_roles = FINANCE
    queryset = (
        Payment.objects.select_related(
            'entry__project__customer', 'entry__purchase__supplier', 'reversal', 'document', 'reconciliation'
        )
        .annotate(
            bank_matched=Exists(
                BankMatch.objects.filter(payment=OuterRef('pk'), reversal_of__isnull=True, reversal__isnull=True)
            )
        )
        .prefetch_related('evidence__document', 'evidence__created_by')
    )
    serializer_class = PaymentSerializer
    # 银行匹配按结算方式和账户找候选流水；不开出来前端只能拉全量再过滤。
    filterset_fields = ['entry', 'entry__project', 'method', 'account']

    @action(detail=True, methods=['post'], url_path='attach-evidence')
    def attach_evidence(self, request, pk=None):
        return Response(finance.attach_evidence(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        return Response(finance.reverse(request.user, key(request), self.get_object().pk, request.data))
