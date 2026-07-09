"""
供应商评价管理视图
"""

from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin

from .evaluation_models import (
    EvaluationCriteria,
    EvaluationScoreItem,
    SupplierBlacklist,
    SupplierEvaluation,
    SupplierEvaluationTemplate,
    SupplierGradeHistory,
)
from .evaluation_serializers import (
    EvaluationCriteriaSerializer,
    EvaluationScoreItemSerializer,
    SupplierBlacklistSerializer,
    SupplierEvaluationCreateSerializer,
    SupplierEvaluationSerializer,
    SupplierEvaluationTemplateSerializer,
    SupplierGradeHistorySerializer,
)


class SupplierEvaluationTemplateViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    评价模板管理
    """

    permission_module = 'purchase'
    permission_resource = 'supplier_evaluation_template'
    queryset = SupplierEvaluationTemplate.objects.all()
    serializer_class = SupplierEvaluationTemplateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_active', 'is_default']
    search_fields = ['name', 'code']

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """设置为默认模板"""
        template = self.get_object()

        # 取消其他默认模板
        SupplierEvaluationTemplate.objects.filter(is_default=True).update(is_default=False)

        template.is_default = True
        template.save()

        return Response(self.get_serializer(template).data)

    @action(detail=True, methods=['post'])
    def add_criteria(self, request, pk=None):
        """添加评价指标"""
        template = self.get_object()
        serializer = EvaluationCriteriaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(template=template, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def copy_template(self, request, pk=None):
        """复制模板"""
        template = self.get_object()
        new_name = request.data.get('name', f'{template.name} (副本)')
        new_code = request.data.get('code', f'{template.code}_copy')

        new_template = SupplierEvaluationTemplate.objects.create(
            name=new_name,
            code=new_code,
            description=template.description,
            is_default=False,
            is_active=True,
            created_by=request.user,
        )

        # 复制评价指标
        for criteria in template.criteria.all():
            EvaluationCriteria.objects.create(
                template=new_template,
                name=criteria.name,
                category=criteria.category,
                weight=criteria.weight,
                max_score=criteria.max_score,
                description=criteria.description,
                sort_order=criteria.sort_order,
                created_by=request.user,
            )

        return Response(self.get_serializer(new_template).data, status=status.HTTP_201_CREATED)


class EvaluationCriteriaViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    评价指标管理
    """

    permission_module = 'purchase'
    permission_resource = 'evaluation_criteria'
    queryset = EvaluationCriteria.objects.all()
    serializer_class = EvaluationCriteriaSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template', 'category']
    search_fields = ['name']


class SupplierEvaluationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    供应商评价管理
    """

    queryset = SupplierEvaluation.objects.all()
    serializer_class = SupplierEvaluationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'template', 'status', 'period_type', 'grade', 'evaluator']
    search_fields = ['evaluation_no', 'supplier__name', 'comments']
    ordering_fields = ['evaluation_date', 'total_score', 'grade']

    permission_module = 'purchase'
    permission_resource = 'supplier_evaluation'

    def get_serializer_class(self):
        if self.action == 'create':
            return SupplierEvaluationCreateSerializer
        return SupplierEvaluationSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, evaluator=self.request.user, status='DRAFT')

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交评价"""
        evaluation = self.get_object()
        if evaluation.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的评价'}, status=status.HTTP_400_BAD_REQUEST)

        evaluation.status = 'SUBMITTED'
        evaluation.save()
        return Response(self.get_serializer(evaluation).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批评价"""
        evaluation = self.get_object()
        if evaluation.status != 'SUBMITTED':
            return Response({'error': '只能审批已提交的评价'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            evaluation.status = 'APPROVED'
            evaluation.approver = request.user
            evaluation.approved_at = timezone.now()
            evaluation.approval_comments = request.data.get('comments', '')
            evaluation.save()

            # 等级落地：把评价计算出的等级回写到供应商权威字段 Supplier.grade，
            # 仅当等级实际发生变化时才写库并记一条变更历史（避免每次审批都冗余建历史）。
            supplier = evaluation.supplier
            old_grade = supplier.grade or ''
            new_grade = evaluation.grade or ''
            if new_grade and old_grade != new_grade:
                supplier.grade = new_grade
                supplier.save(update_fields=['grade', 'updated_at'])
                SupplierGradeHistory.objects.create(
                    supplier=supplier,
                    evaluation=evaluation,
                    old_grade=old_grade,
                    new_grade=new_grade,
                    change_date=timezone.now().date(),
                    reason=f'评价审批通过，评分 {evaluation.total_score}',
                    created_by=request.user,
                )

        return Response(self.get_serializer(evaluation).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """驳回评价"""
        evaluation = self.get_object()
        if evaluation.status != 'SUBMITTED':
            return Response({'error': '只能驳回已提交的评价'}, status=status.HTTP_400_BAD_REQUEST)

        evaluation.status = 'REJECTED'
        evaluation.approver = request.user
        evaluation.approved_at = timezone.now()
        evaluation.approval_comments = request.data.get('comments', '')
        evaluation.save()

        return Response(self.get_serializer(evaluation).data)

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """重新计算评分"""
        evaluation = self.get_object()
        evaluation.calculate_scores()
        return Response(self.get_serializer(evaluation).data)

    @action(detail=True, methods=['post'])
    def update_scores(self, request, pk=None):
        """更新评分明细"""
        evaluation = self.get_object()
        if evaluation.status not in ['DRAFT', 'REJECTED']:
            return Response({'error': '只能修改草稿或驳回状态的评价'}, status=status.HTTP_400_BAD_REQUEST)

        score_items = request.data.get('score_items', [])
        for item_data in score_items:
            item_id = item_data.get('id')
            if item_id:
                try:
                    item = EvaluationScoreItem.objects.get(id=item_id, evaluation=evaluation)
                    item.score = item_data.get('score', item.score)
                    item.comments = item_data.get('comments', item.comments)
                    item.save()
                except EvaluationScoreItem.DoesNotExist:
                    pass
            else:
                EvaluationScoreItem.objects.create(
                    evaluation=evaluation,
                    criteria_id=item_data['criteria'],
                    score=item_data['score'],
                    comments=item_data.get('comments', ''),
                    created_by=request.user,
                )

        evaluation.calculate_scores()
        return Response(self.get_serializer(evaluation).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """评价统计"""
        queryset = self.get_queryset()

        total_evaluations = queryset.count()
        by_status = queryset.values('status').annotate(count=Count('status'))
        by_grade = queryset.filter(status='APPROVED').values('grade').annotate(count=Count('grade'))
        avg_scores = queryset.filter(status='APPROVED').aggregate(
            avg_total=Avg('total_score'),
            avg_quality=Avg('quality_score'),
            avg_delivery=Avg('delivery_score'),
            avg_price=Avg('price_score'),
            avg_service=Avg('service_score'),
        )

        return Response(
            {
                'total_evaluations': total_evaluations,
                'by_status': by_status,
                'by_grade': by_grade,
                'avg_scores': avg_scores,
            }
        )

    @action(detail=False, methods=['get'])
    def supplier_ranking(self, request):
        """供应商排名"""

        # 获取最近审批通过的评价，按供应商分组
        rankings = (
            SupplierEvaluation.objects.filter(status='APPROVED')
            .values('supplier', 'supplier__name', 'supplier__code')
            .annotate(avg_score=Avg('total_score'), evaluation_count=Count('id'))
            .order_by('-avg_score')[:20]
        )

        return Response(rankings)


class EvaluationScoreItemViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    评价得分明细管理
    """

    permission_module = 'purchase'
    permission_resource = 'evaluation_score_item'
    queryset = EvaluationScoreItem.objects.all()
    serializer_class = EvaluationScoreItemSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['evaluation', 'criteria']


class SupplierGradeHistoryViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    """
    供应商等级变更历史（只读）
    """

    permission_module = 'purchase'
    permission_resource = 'supplier_grade_history'
    queryset = SupplierGradeHistory.objects.all()
    serializer_class = SupplierGradeHistorySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier']
    ordering_fields = ['change_date']


class SupplierBlacklistViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    供应商黑名单管理
    """

    queryset = SupplierBlacklist.objects.all()
    serializer_class = SupplierBlacklistSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'status']
    search_fields = ['supplier__name', 'reason']

    permission_module = 'purchase'
    permission_resource = 'supplier_blacklist'

    @action(detail=True, methods=['post'])
    def lift(self, request, pk=None):
        """解除黑名单"""
        blacklist = self.get_object()
        if blacklist.status != 'ACTIVE':
            return Response({'error': '只能解除有效的黑名单记录'}, status=status.HTTP_400_BAD_REQUEST)

        blacklist.status = 'LIFTED'
        blacklist.lifted_date = timezone.now().date()
        blacklist.lifted_reason = request.data.get('reason', '')
        blacklist.lifted_by = request.user
        blacklist.save()

        return Response(self.get_serializer(blacklist).data)

    @action(detail=False, methods=['get'])
    def active_list(self, request):
        """获取当前有效黑名单"""
        blacklist = self.get_queryset().filter(status='ACTIVE')
        serializer = self.get_serializer(blacklist, many=True)
        return Response(serializer.data)
