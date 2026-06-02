"""
编码规则视图
"""

from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permission_mixin import PermissionMixin
from apps.core.permissions import IsSystemAdmin

from .code_rule_models import CodeHistory, CodeRule
from .code_rule_serializers import CodeHistorySerializer, CodeRuleSerializer


class CodeRuleViewSet(PermissionMixin, viewsets.ModelViewSet):
    """
    编码规则管理
    只有管理员可以操作
    """

    permission_module = 'system'
    permission_resource = 'code_rule'
    queryset = CodeRule.objects.all()
    serializer_class = CodeRuleSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]
    filterset_fields = ['rule_type', 'is_active']
    search_fields = ['rule_name', 'prefix']
    ordering_fields = ['rule_type', 'created_at']

    @action(detail=True, methods=['post'])
    def reset_sequence(self, request, pk=None):
        """重置序列号"""
        rule = self.get_object()
        rule.current_seq = rule.seq_start - 1
        rule.last_reset_date = None
        rule.save()

        return Response({'message': '序列号已重置', 'current_seq': rule.current_seq})

    @action(detail=True, methods=['post'])
    def generate_test_code(self, request, pk=None):
        """生成测试编码（不保存）"""
        rule = self.get_object()
        test_code = rule.generate_example()

        return Response({'test_code': test_code, 'message': '这是测试编码，不会保存到系统中'})

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """查看编码生成历史"""
        rule = self.get_object()
        histories = CodeHistory.objects.filter(rule=rule).order_by('-generated_at')[:100]
        serializer = CodeHistorySerializer(histories, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """统计信息"""
        stats = CodeRule.objects.values('rule_type').annotate(count=Count('id'), total_generated=Count('history'))

        return Response(list(stats))

    @action(detail=False, methods=['post'])
    def init_default_rules(self, request):
        """初始化默认编码规则"""
        default_rules = [
            {
                'rule_type': 'PROJECT',
                'rule_name': '项目编号规则',
                'prefix': 'PRJ',
                'date_format': 'YYYYMM',
                'seq_length': 4,
                'seq_start': 1,
                'reset_mode': 'YEARLY',
                'separator': '-',
                'description': '格式：PRJ-YYYYMM-0001',
            },
            {
                'rule_type': 'ITEM',
                'rule_name': '物料编码规则（特殊规则）',
                'prefix': '',
                'date_format': '',
                'seq_length': 6,
                'seq_start': 1,
                'reset_mode': 'NONE',
                'separator': '',
                'is_active': False,
                'description': '⚠️ 物料编码使用特殊规则，不通过此处配置。\n规则：一级代码(1位)+二级代码(1位)+年份(2位)+流水号(6位)\n请在"物料管理"页面使用"生成编码"功能。',
            },
            {
                'rule_type': 'PURCHASE_CONTRACT',
                'rule_name': '采购合同编号规则',
                'prefix': 'PC',
                'date_format': 'YYYY',
                'seq_length': 5,
                'seq_start': 1,
                'reset_mode': 'YEARLY',
                'separator': '',
                'description': '格式：PC20250001',
            },
            {
                'rule_type': 'SALES_CONTRACT',
                'rule_name': '销售合同编号规则',
                'prefix': 'SC',
                'date_format': 'YYYY',
                'seq_length': 5,
                'seq_start': 1,
                'reset_mode': 'YEARLY',
                'separator': '',
                'description': '格式：SC20250001',
            },
            {
                'rule_type': 'PURCHASE_ORDER',
                'rule_name': '采购订单编号规则',
                'prefix': 'PO',
                'date_format': 'YYYYMMDD',
                'seq_length': 4,
                'seq_start': 1,
                'reset_mode': 'MONTHLY',
                'separator': '-',
                'description': '格式：PO-YYYYMMDD-0001',
            },
            {
                'rule_type': 'SALES_ORDER',
                'rule_name': '销售订单编号规则',
                'prefix': 'SO',
                'date_format': 'YYYYMMDD',
                'seq_length': 4,
                'seq_start': 1,
                'reset_mode': 'MONTHLY',
                'separator': '-',
                'description': '格式：SO-YYYYMMDD-0001',
            },
            {
                'rule_type': 'BUG',
                'rule_name': 'Bug编号规则',
                'prefix': 'BUG',
                'date_format': 'YYYY',
                'seq_length': 6,
                'seq_start': 1,
                'reset_mode': 'YEARLY',
                'separator': '',
                'description': '格式：BUG2025000001',
            },
        ]

        created_count = 0
        skipped_count = 0

        for rule_data in default_rules:
            rule_type = rule_data['rule_type']
            if not CodeRule.objects.filter(rule_type=rule_type).exists():
                CodeRule.objects.create(**rule_data)
                created_count += 1
            else:
                skipped_count += 1

        return Response({'message': '默认规则初始化完成', 'created': created_count, 'skipped': skipped_count})


class CodeHistoryViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    """
    编码历史查询
    只读接口
    """

    permission_module = 'system'
    permission_resource = 'code_history'
    queryset = CodeHistory.objects.all()
    serializer_class = CodeHistorySerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]
    filterset_fields = ['rule', 'business_model']
    search_fields = ['generated_code']
    ordering_fields = ['generated_at']
    ordering = ['-generated_at']
