"""核销工作台 API:待付款项台账列表 + 银行流水核销/反核销动作。

候选匹配(match_candidates)挂在 BankStatementViewSet 的 payable-candidates
detail action 上(见 bank_statement_views.py),因候选天然是"某条流水"的下属资源。
"""

from decimal import Decimal, InvalidOperation

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin
from apps.finance import payable_service as svc
from apps.finance.models import BankStatement
from apps.finance.payable_models import PayableItem, PayableSettlement
from apps.finance.payable_serializers import PayableItemSerializer


class PayableItemViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """待付款项台账(核销工作台左侧列表/详情)。"""

    permission_module = 'finance'
    permission_resource = 'payable_item'
    # 财务共享台账:可见性面向财务全量,不按创建人过滤。台账项由来源适配器 register_payable
    # 登记,created_by 常为空,若走 'self' 数据范围会把全部台账项错误隐藏。(同 H13 口径)
    skip_data_scope = True
    queryset = PayableItem.objects.select_related('supplier', 'currency', 'project').all()
    serializer_class = PayableItemSerializer
    # 工作台右侧台账筛选:状态/供应商/类别/来源精确匹配,应付日期/应付金额支持区间(gte/lte)。
    filterset_fields = {
        'status': ['exact'],
        'supplier': ['exact'],
        'category': ['exact'],
        'source_type': ['exact'],
        'due_date': ['gte', 'lte'],
        'amount_due': ['gte', 'lte'],
    }
    search_fields = ['source_no', 'payee_name']
    ordering_fields = ['due_date', 'amount_due', 'created_at']


class PayableReconcileViewSet(PermissionMixin, viewsets.ViewSet):
    """银行流水核销动作集:settle(核销) / unsettle(反核销)。

    复用 bank_statement 权限资源——核销本质是对一条银行流水的财务动作。
    """

    permission_module = 'finance'
    permission_resource = 'bank_statement'

    @action(detail=False, methods=['post'])
    def settle(self, request):
        bs = BankStatement.objects.filter(pk=request.data.get('bank_statement_id')).first()
        if bs is None:
            return Response({'detail': '银行流水不存在'}, status=status.HTTP_404_NOT_FOUND)
        raw = request.data.get('allocations') or []
        try:
            allocations = [
                {'payable_item_id': a['payable_item_id'], 'amount': Decimal(str(a['amount']))}
                for a in raw
            ]
        except (KeyError, TypeError, InvalidOperation):
            return Response({'detail': 'allocations 参数格式错误'}, status=status.HTTP_400_BAD_REQUEST)
        if not allocations:
            return Response({'detail': 'allocations 不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            settlements = svc.settle(bs, allocations, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'ok': True,
            'settlement_ids': [s.id for s in settlements],
            'bank_statement_status': bs.status,
        })

    @action(detail=False, methods=['post'])
    def unsettle(self, request):
        settlement = PayableSettlement.objects.filter(pk=request.data.get('settlement_id')).first()
        if settlement is None:
            return Response({'detail': '核销记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        svc.unsettle(settlement, request.user)
        return Response({'ok': True})
