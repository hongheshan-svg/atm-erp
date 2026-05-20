"""
RFQ views
询价单、供应商报价、比价分析视图

非标自动化增强:
- 供应商能力匹配和推荐
- 从项目BOM批量创建询价单
- 询价模板管理
- 附件管理
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin

from .comparison_service import QuotationComparisonService
from .rfq_models import (
    RFQ,
    ItemPriceHistory,
    QuotationComparison,
    QuotationScore,
    RFQAttachment,
    RFQLine,
    RFQSupplier,
    RFQTemplate,
    RFQTemplateItem,
    SupplierCapability,
    SupplierCapabilityMapping,
    SupplierQuotation,
    SupplierQuotationLine,
)
from .rfq_serializers import (
    CreateComparisonSerializer,
    ItemPriceHistorySerializer,
    QuotationComparisonListSerializer,
    QuotationComparisonSerializer,
    QuotationScoreSerializer,
    RFQLineSerializer,
    RFQSerializer,
    RFQSupplierSerializer,
    SupplierQuotationLineSerializer,
    SupplierQuotationSerializer,
    UpdateScoreSerializer,
)
from .rfq_service import BatchRFQService, RFQAttachmentService, RFQTemplateService, SupplierMatchingService


class RFQViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """RFQ viewset"""

    queryset = RFQ.objects.all()
    serializer_class = RFQSerializer
    filterset_fields = ['project', 'status', 'is_deleted']
    search_fields = ['rfq_no']
    ordering_fields = ['request_date', 'response_deadline', 'created_at']

    permission_module = 'purchase'
    permission_resource = 'rfq'

    @action(detail=True, methods=['post'])
    def send_to_suppliers(self, request, pk=None):
        """Send RFQ to selected suppliers"""
        rfq = self.get_object()

        if rfq.status != 'DRAFT':
            return Response({'error': '只能发送草稿状态的询价单'}, status=status.HTTP_400_BAD_REQUEST)

        supplier_ids = request.data.get('supplier_ids', [])

        if not supplier_ids:
            return Response({'error': '请选择至少一个供应商'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for supplier_id in supplier_ids:
                RFQSupplier.objects.create(
                    rfq=rfq, supplier_id=supplier_id, sent_date=timezone.now(), created_by=request.user
                )

            rfq.status = 'SENT'
            rfq.save()

        return Response({'message': f'已发送给 {len(supplier_ids)} 个供应商'})

    @action(detail=True, methods=['post'])
    def accept_quotation(self, request, pk=None):
        """Accept a supplier quotation"""
        rfq = self.get_object()
        quotation_id = request.data.get('quotation_id')

        if not quotation_id:
            return Response({'error': '请提供报价单ID'}, status=status.HTTP_400_BAD_REQUEST)

        quotation = SupplierQuotation.objects.get(id=quotation_id)

        with transaction.atomic():
            quotation.status = 'ACCEPTED'
            quotation.save()

            rfq.status = 'ACCEPTED'
            rfq.save()

        return Response({'message': '已接受该报价'})

    @action(detail=True, methods=['post'])
    def convert_to_po(self, request, pk=None):
        """Convert accepted quotation to purchase order"""
        rfq = self.get_object()

        if rfq.status != 'ACCEPTED':
            return Response({'error': '只能转换已接受的询价单'}, status=status.HTTP_400_BAD_REQUEST)

        quotation_id = request.data.get('quotation_id')

        if not quotation_id:
            return Response({'error': '请提供报价单ID'}, status=status.HTTP_400_BAD_REQUEST)

        from .models import PurchaseOrder, PurchaseOrderLine

        quotation = SupplierQuotation.objects.get(id=quotation_id)

        with transaction.atomic():
            po = PurchaseOrder.objects.create(
                supplier=quotation.rfq_supplier.supplier,
                project=rfq.project,
                order_date=timezone.now().date(),
                payment_terms=quotation.payment_terms,
                created_by=request.user,
            )

            for quot_line in quotation.lines.all():
                PurchaseOrderLine.objects.create(
                    po=po,
                    item=quot_line.rfq_line.item,
                    qty=quot_line.qty,
                    unit_price=quot_line.unit_price,
                    created_by=request.user,
                )

            # Update PO total
            from django.db.models import Sum

            total = po.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            po.total_amount = total
            po.save()

        from .serializers import PurchaseOrderSerializer

        return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_201_CREATED)

    # ==================== 非标自动化增强API ====================

    @action(detail=False, methods=['post'], url_path='create-from-bom')
    def create_from_bom(self, request):
        """从项目BOM批量创建询价单"""
        project_id = request.data.get('project_id')
        bom_item_ids = request.data.get('bom_item_ids', [])

        if not project_id or not bom_item_ids:
            return Response({'error': '请指定项目和BOM项'}, status=status.HTTP_400_BAD_REQUEST)

        options = {
            'rfq_type': request.data.get('rfq_type', 'NORMAL'),
            'priority': request.data.get('priority', 'NORMAL'),
            'deadline_days': request.data.get('deadline_days', 7),
            'template_id': request.data.get('template_id'),
            'supplier_ids': request.data.get('supplier_ids', []),
            'auto_match_suppliers': request.data.get('auto_match_suppliers', False),
        }

        try:
            rfq = BatchRFQService.create_rfq_from_bom(project_id, bom_item_ids, request.user, options)
            return Response(RFQSerializer(rfq).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='batch-send')
    def batch_send(self, request):
        """批量发送询价单"""
        rfq_ids = request.data.get('rfq_ids', [])

        if not rfq_ids:
            return Response({'error': '请指定询价单'}, status=status.HTTP_400_BAD_REQUEST)

        result = BatchRFQService.batch_send_rfq(rfq_ids, request.user)
        return Response(result)

    @action(detail=True, methods=['get'], url_path='match-suppliers')
    def match_suppliers(self, request, pk=None):
        """为询价单匹配供应商"""
        rfq = self.get_object()
        result = SupplierMatchingService.match_suppliers_for_rfq(rfq.id)
        return Response(result)

    @action(detail=True, methods=['post'], url_path='upload-attachment', parser_classes=[MultiPartParser])
    def upload_attachment(self, request, pk=None):
        """上传询价单附件"""
        rfq = self.get_object()
        file = request.FILES.get('file')

        if not file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            attachment = RFQAttachmentService.upload_attachment(
                file=file,
                rfq_id=rfq.id,
                category=request.data.get('category', 'OTHER'),
                description=request.data.get('description', ''),
                version=request.data.get('version', ''),
                user=request.user,
            )
            return Response(
                {
                    'id': attachment.id,
                    'file_name': attachment.file_name,
                    'file_size': attachment.file_size,
                    'category': attachment.category,
                }
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='attachments')
    def list_attachments(self, request, pk=None):
        """获取询价单附件列表"""
        rfq = self.get_object()
        attachments = RFQAttachment.objects.filter(rfq=rfq, is_deleted=False).order_by('category', '-created_at')

        result = []
        for att in attachments:
            result.append(
                {
                    'id': att.id,
                    'file_name': att.file_name,
                    'file_size': att.file_size,
                    'file_type': att.file_type,
                    'category': att.category,
                    'category_display': att.get_category_display(),
                    'description': att.description,
                    'version': att.version,
                    'created_at': att.created_at.isoformat() if att.created_at else None,
                }
            )
        return Response(result)

    @action(detail=False, methods=['post'], url_path='create-from-template')
    def create_from_template(self, request):
        """从模板创建询价单"""
        template_id = request.data.get('template_id')
        project_id = request.data.get('project_id')

        if not template_id:
            return Response({'error': '请指定模板'}, status=status.HTTP_400_BAD_REQUEST)

        options = {
            'rfq_type': request.data.get('rfq_type'),
            'priority': request.data.get('priority'),
            'deadline_days': request.data.get('deadline_days'),
        }

        try:
            rfq = RFQTemplateService.create_rfq_from_template(template_id, project_id, request.user, options)
            return Response(RFQSerializer(rfq).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='save-as-template')
    def save_as_template(self, request, pk=None):
        """将询价单保存为模板"""
        rfq = self.get_object()
        name = request.data.get('name')

        if not name:
            return Response({'error': '请指定模板名称'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            template = RFQTemplateService.create_template_from_rfq(
                rfq.id, name, request.user, description=request.data.get('description', '')
            )
            return Response({'id': template.id, 'name': template.name, 'message': '模板创建成功'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RFQLineViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """RFQ line viewset"""

    queryset = RFQLine.objects.all()
    serializer_class = RFQLineSerializer
    filterset_fields = ['rfq', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']

    permission_module = 'purchase'
    permission_resource = 'rfq_line'


class RFQSupplierViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """RFQ supplier viewset"""

    queryset = RFQSupplier.objects.all()
    serializer_class = RFQSupplierSerializer
    filterset_fields = ['rfq', 'supplier', 'is_responded']


class SupplierQuotationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """Supplier quotation viewset"""

    queryset = SupplierQuotation.objects.all()
    serializer_class = SupplierQuotationSerializer
    filterset_fields = ['rfq_supplier', 'status', 'is_deleted']
    search_fields = ['quotation_no']
    ordering_fields = ['quotation_date', 'valid_until', 'created_at']

    permission_module = 'purchase'
    permission_resource = 'supplier_quotation'

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit quotation"""
        quotation = self.get_object()

        if quotation.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的报价'}, status=status.HTTP_400_BAD_REQUEST)

        quotation.status = 'SUBMITTED'
        quotation.rfq_supplier.is_responded = True
        quotation.rfq_supplier.save()
        quotation.save()

        # Update RFQ status
        rfq = quotation.rfq_supplier.rfq
        if all(sq.is_responded for sq in rfq.supplier_rfqs.all()):
            rfq.status = 'QUOTED'
            rfq.save()

        return Response(SupplierQuotationSerializer(quotation).data)


class SupplierQuotationLineViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """Supplier quotation line viewset"""

    queryset = SupplierQuotationLine.objects.all()
    serializer_class = SupplierQuotationLineSerializer

    permission_module = 'purchase'
    permission_resource = 'supplier_quotation_line'
    filterset_fields = ['quotation', 'rfq_line', 'is_deleted']


class QuotationComparisonViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """报价比价分析视图"""

    queryset = QuotationComparison.objects.all()
    serializer_class = QuotationComparisonSerializer
    filterset_fields = ['rfq', 'status', 'is_deleted']
    search_fields = ['comparison_no', 'rfq__rfq_no']
    ordering_fields = ['created_at', 'status']

    permission_module = 'purchase'
    permission_resource = 'quotation_comparison'

    def get_serializer_class(self):
        if self.action == 'list':
            return QuotationComparisonListSerializer
        return QuotationComparisonSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related(
            'rfq',
            'rfq__project',
            'recommended_quotation',
            'recommended_quotation__rfq_supplier__supplier',
            'approved_by',
        ).prefetch_related('scores')

    @action(detail=False, methods=['get'], url_path='available-rfqs')
    def available_rfqs(self, request):
        """获取可用于比价的询价单列表（至少有2个有效报价）"""
        from django.db.models import Count, Q

        # 获取每个RFQ的有效报价数量（SUBMITTED或ACCEPTED状态）
        rfqs = (
            RFQ.objects.filter(
                is_deleted=False,
                status__in=['QUOTED', 'SENT'],  # 已报价或已发送状态
            )
            .annotate(
                valid_quotation_count=Count(
                    'supplier_rfqs__quotations',
                    filter=Q(
                        supplier_rfqs__quotations__status__in=['SUBMITTED', 'ACCEPTED'],
                        supplier_rfqs__quotations__is_deleted=False,
                    ),
                )
            )
            .filter(
                valid_quotation_count__gte=2  # 至少2个有效报价
            )
            .select_related('project')
            .order_by('-request_date')
        )

        result = []
        for rfq in rfqs:
            result.append(
                {
                    'id': rfq.id,
                    'rfq_no': rfq.rfq_no,
                    'project_name': rfq.project.name if rfq.project else None,
                    'status': rfq.status,
                    'status_display': rfq.get_status_display(),
                    'quotation_count': rfq.valid_quotation_count,
                    'request_date': rfq.request_date.isoformat() if rfq.request_date else None,
                }
            )

        return Response(result)

    @action(detail=False, methods=['post'], url_path='create-comparison')
    def create_comparison(self, request):
        """创建比价分析（非标自动化增强版）"""
        serializer = CreateComparisonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            weight_template = serializer.validated_data.get('weight_template', 'STANDARD')
            comparison_type = serializer.validated_data.get('comparison_type', 'NORMAL')

            # 如果使用模板，权重将由服务层根据模板自动设置
            weights = None
            if weight_template == 'CUSTOM':
                weights = {
                    'price': float(serializer.validated_data.get('weight_price', 40)),
                    'quality': float(serializer.validated_data.get('weight_quality', 25)),
                    'delivery': float(serializer.validated_data.get('weight_delivery', 20)),
                    'service': float(serializer.validated_data.get('weight_service', 15)),
                    'technical': float(serializer.validated_data.get('weight_technical', 0)),
                }

            comparison = QuotationComparisonService.create_comparison(
                rfq_id=serializer.validated_data['rfq_id'],
                user=request.user,
                weights=weights,
                comparison_type=comparison_type,
                weight_template=weight_template,
            )

            return Response(QuotationComparisonSerializer(comparison).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        """获取比价报告"""
        comparison = self.get_object()
        report = QuotationComparisonService.get_comparison_report(comparison)
        return Response(report)

    @action(detail=True, methods=['post'], url_path='update-weights')
    def update_weights(self, request, pk=None):
        """更新比价权重"""
        comparison = self.get_object()

        weights = {
            'price': float(request.data.get('weight_price', comparison.weight_price)),
            'quality': float(request.data.get('weight_quality', comparison.weight_quality)),
            'delivery': float(request.data.get('weight_delivery', comparison.weight_delivery)),
            'service': float(request.data.get('weight_service', comparison.weight_service)),
            'technical': float(request.data.get('weight_technical', comparison.weight_technical)),
        }

        try:
            comparison = QuotationComparisonService.update_weights(comparison.id, weights)
            return Response(QuotationComparisonSerializer(comparison).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='apply-template')
    def apply_template(self, request, pk=None):
        """应用权重模板"""
        comparison = self.get_object()
        template = request.data.get('template', 'STANDARD')

        try:
            comparison = QuotationComparisonService.apply_weight_template(comparison.id, template)
            return Response(QuotationComparisonSerializer(comparison).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='multi-recommendations')
    def multi_recommendations(self, request, pk=None):
        """获取多维度推荐结果"""
        comparison = self.get_object()
        recommendations = QuotationComparisonService.get_multi_dimension_recommendations(comparison.id)
        return Response(recommendations)

    @action(detail=True, methods=['post'], url_path='auto-score')
    def auto_score(self, request, pk=None):
        """自动评分（价格和交期）"""
        comparison = self.get_object()
        QuotationComparisonService.auto_score(comparison)
        return Response(QuotationComparisonSerializer(comparison).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成比价分析"""
        comparison = self.get_object()
        comparison = QuotationComparisonService.complete_comparison(comparison.id)
        return Response(QuotationComparisonSerializer(comparison).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批比价分析"""
        comparison = self.get_object()
        notes = request.data.get('notes', '')

        try:
            comparison = QuotationComparisonService.approve_comparison(comparison.id, request.user, notes)
            return Response(QuotationComparisonSerializer(comparison).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='convert-to-po')
    def convert_to_po(self, request, pk=None):
        """将推荐报价转换为采购订单"""
        comparison = self.get_object()

        try:
            from .serializers import PurchaseOrderSerializer

            po = QuotationComparisonService.convert_to_po(comparison.id, request.user)
            return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='update-score/(?P<score_id>[^/.]+)')
    def update_score(self, request, pk=None, score_id=None):
        """更新单个供应商的评分（质量和服务）"""
        serializer = UpdateScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            score = QuotationComparisonService.update_manual_scores(
                score_id=score_id,
                quality_score=serializer.validated_data.get('score_quality'),
                service_score=serializer.validated_data.get('score_service'),
                notes=serializer.validated_data.get('notes'),
            )
            return Response(QuotationScoreSerializer(score).data)
        except QuotationScore.DoesNotExist:
            return Response({'error': '评分记录不存在'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request):
        """批量删除比价分析（仅管理员）"""
        # 检查管理员权限
        if not request.user.is_superuser and not request.user.is_staff:
            return Response({'error': '无权限执行此操作'}, status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请选择要删除的记录'}, status=status.HTTP_400_BAD_REQUEST)

        from django.utils import timezone

        deleted_count = 0

        for comparison_id in ids:
            try:
                comparison = QuotationComparison.objects.get(id=comparison_id, is_deleted=False)
                # 使用软删除
                comparison.is_deleted = True
                comparison.deleted_at = timezone.now()
                comparison.save(update_fields=['is_deleted', 'deleted_at'])
                deleted_count += 1
            except QuotationComparison.DoesNotExist:
                continue

        return Response({'message': f'成功删除 {deleted_count} 条记录', 'deleted_count': deleted_count})


class QuotationScoreViewSet(PermissionMixin, viewsets.ModelViewSet):
    permission_module = 'purchase'
    permission_resource = 'quotation_score'
    """报价评分视图"""
    queryset = QuotationScore.objects.all()
    serializer_class = QuotationScoreSerializer
    filterset_fields = ['comparison', 'quotation', 'is_recommended']
    ordering_fields = ['ranking', 'total_score']

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('comparison', 'quotation', 'quotation__rfq_supplier__supplier')

    @action(detail=True, methods=['post'], url_path='update-manual')
    def update_manual(self, request, pk=None):
        """更新手动评分"""
        score = self.get_object()
        serializer = UpdateScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        score = QuotationComparisonService.update_manual_scores(
            score_id=score.id,
            quality_score=serializer.validated_data.get('score_quality'),
            service_score=serializer.validated_data.get('score_service'),
            notes=serializer.validated_data.get('notes'),
        )
        return Response(QuotationScoreSerializer(score).data)


class ItemPriceHistoryViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    permission_module = 'purchase'
    permission_resource = 'item_price_history'
    """物料价格历史视图（只读）"""
    queryset = ItemPriceHistory.objects.all()
    serializer_class = ItemPriceHistorySerializer
    filterset_fields = ['item', 'supplier', 'source_type']
    ordering_fields = ['price_date', 'unit_price']

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False)
        return queryset.select_related('item', 'supplier')

    @action(detail=False, methods=['get'], url_path='by-item/(?P<item_id>[^/.]+)')
    def by_item(self, request, item_id=None):
        """获取指定物料的价格历史"""
        supplier_id = request.query_params.get('supplier_id')
        limit = int(request.query_params.get('limit', 10))

        history = QuotationComparisonService.get_item_price_history(
            item_id=item_id, supplier_id=supplier_id, limit=limit
        )
        return Response(history)

    @action(detail=False, methods=['get'], url_path='last-price')
    def last_price(self, request):
        """获取物料上次采购价格"""
        item_id = request.query_params.get('item_id')
        supplier_id = request.query_params.get('supplier_id')

        if not item_id or not supplier_id:
            return Response({'error': '请提供 item_id 和 supplier_id'}, status=status.HTTP_400_BAD_REQUEST)

        price = QuotationComparisonService.get_last_purchase_price(item_id, supplier_id)
        return Response({'last_price': price})


# ==================== 非标自动化增强ViewSet ====================


class RFQTemplateViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """询价模板管理"""

    queryset = RFQTemplate.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['default_rfq_type', 'default_priority']
    search_fields = ['name', 'description']
    ordering_fields = ['use_count', 'name', 'created_at']

    def get_serializer_class(self):
        # 简单返回基础数据，实际项目中应该定义专门的序列化器
        from rest_framework import serializers

        class RFQTemplateSerializer(serializers.ModelSerializer):
            default_suppliers_count = serializers.SerializerMethodField()
            items_count = serializers.SerializerMethodField()

            class Meta:
                model = RFQTemplate
                fields = [
                    'id',
                    'name',
                    'description',
                    'default_rfq_type',
                    'default_priority',
                    'default_deadline_days',
                    'default_technical_requirements',
                    'default_quality_requirements',
                    'default_packaging_requirements',
                    'default_delivery_requirements',
                    'use_count',
                    'default_suppliers_count',
                    'items_count',
                    'created_at',
                    'updated_at',
                ]

            def get_default_suppliers_count(self, obj):
                return obj.default_suppliers.count()

            def get_items_count(self, obj):
                return obj.items.filter(is_deleted=False).count()

        return RFQTemplateSerializer

    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """获取模板物料列表"""
        template = self.get_object()
        items = template.items.filter(is_deleted=False).select_related('item')

        result = []
        for item in items:
            result.append(
                {
                    'id': item.id,
                    'item_id': item.item_id,
                    'item_sku': item.item.sku,
                    'item_name': item.item.name,
                    'default_qty': float(item.default_qty),
                    'specifications': item.specifications,
                    'technical_specs': item.technical_specs,
                }
            )
        return Response(result)

    @action(detail=True, methods=['get'])
    def suppliers(self, request, pk=None):
        """获取模板默认供应商"""
        template = self.get_object()
        suppliers = template.default_suppliers.all()

        result = []
        for supplier in suppliers:
            result.append(
                {
                    'id': supplier.id,
                    'code': supplier.code,
                    'name': supplier.name,
                }
            )
        return Response(result)

    @action(detail=True, methods=['post'], url_path='add-item')
    def add_item(self, request, pk=None):
        """添加模板物料"""
        template = self.get_object()
        item_id = request.data.get('item_id')

        if not item_id:
            return Response({'error': '请指定物料'}, status=status.HTTP_400_BAD_REQUEST)

        RFQTemplateItem.objects.create(
            template=template,
            item_id=item_id,
            default_qty=request.data.get('default_qty', 1),
            specifications=request.data.get('specifications', ''),
            technical_specs=request.data.get('technical_specs', {}),
            created_by=request.user,
        )
        return Response({'message': '物料添加成功'})


class SupplierCapabilityViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """供应商能力标签管理"""

    queryset = SupplierCapability.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['capability_type']
    search_fields = ['name', 'code', 'description']

    def get_serializer_class(self):
        from rest_framework import serializers

        class SupplierCapabilitySerializer(serializers.ModelSerializer):
            capability_type_display = serializers.CharField(source='get_capability_type_display', read_only=True)
            supplier_count = serializers.SerializerMethodField()

            class Meta:
                model = SupplierCapability
                fields = [
                    'id',
                    'name',
                    'code',
                    'capability_type',
                    'capability_type_display',
                    'description',
                    'supplier_count',
                    'created_at',
                ]

            def get_supplier_count(self, obj):
                return obj.supplier_mappings.filter(is_deleted=False).count()

        return SupplierCapabilitySerializer

    @action(detail=True, methods=['get'])
    def suppliers(self, request, pk=None):
        """获取具有此能力的供应商列表"""
        capability = self.get_object()
        mappings = capability.supplier_mappings.filter(is_deleted=False).select_related('supplier')

        result = []
        for mapping in mappings:
            result.append(
                {
                    'supplier_id': mapping.supplier_id,
                    'supplier_name': mapping.supplier.name,
                    'supplier_code': mapping.supplier.code,
                    'level': mapping.level,
                    'certification_no': mapping.certification_no,
                    'certification_valid_until': mapping.certification_valid_until.isoformat()
                    if mapping.certification_valid_until
                    else None,
                }
            )
        return Response(result)


class SupplierCapabilityMappingViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """供应商能力关联管理"""

    queryset = SupplierCapabilityMapping.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'capability', 'level']

    def get_serializer_class(self):
        from rest_framework import serializers

        class SupplierCapabilityMappingSerializer(serializers.ModelSerializer):
            supplier_name = serializers.CharField(source='supplier.name', read_only=True)
            capability_name = serializers.CharField(source='capability.name', read_only=True)
            capability_type = serializers.CharField(source='capability.capability_type', read_only=True)

            class Meta:
                model = SupplierCapabilityMapping
                fields = [
                    'id',
                    'supplier',
                    'supplier_name',
                    'capability',
                    'capability_name',
                    'capability_type',
                    'level',
                    'notes',
                    'certification_no',
                    'certification_valid_until',
                    'created_at',
                ]

        return SupplierCapabilityMappingSerializer

    @action(detail=False, methods=['get'], url_path='by-supplier/(?P<supplier_id>[^/.]+)')
    def by_supplier(self, request, supplier_id=None):
        """获取供应商的所有能力"""
        mappings = self.queryset.filter(supplier_id=supplier_id).select_related('capability')

        result = []
        for mapping in mappings:
            result.append(
                {
                    'id': mapping.id,
                    'capability_id': mapping.capability_id,
                    'capability_name': mapping.capability.name,
                    'capability_type': mapping.capability.capability_type,
                    'level': mapping.level,
                    'notes': mapping.notes,
                }
            )
        return Response(result)


class RFQAttachmentViewSet(PermissionMixin, SoftDeleteMixin, viewsets.ModelViewSet):
    """询价单附件管理"""

    queryset = RFQAttachment.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['rfq', 'rfq_line', 'category']

    def get_serializer_class(self):
        from rest_framework import serializers

        class RFQAttachmentSerializer(serializers.ModelSerializer):
            category_display = serializers.CharField(source='get_category_display', read_only=True)

            class Meta:
                model = RFQAttachment
                fields = [
                    'id',
                    'rfq',
                    'rfq_line',
                    'file_name',
                    'file_path',
                    'file_size',
                    'file_type',
                    'category',
                    'category_display',
                    'description',
                    'version',
                    'created_at',
                ]
                read_only_fields = ['file_path', 'file_size', 'file_type']

        return RFQAttachmentSerializer

    def create(self, request, *args, **kwargs):
        """上传附件"""
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            attachment = RFQAttachmentService.upload_attachment(
                file=file,
                rfq_id=request.data.get('rfq'),
                rfq_line_id=request.data.get('rfq_line'),
                category=request.data.get('category', 'OTHER'),
                description=request.data.get('description', ''),
                version=request.data.get('version', ''),
                user=request.user,
            )
            serializer = self.get_serializer(attachment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """删除附件"""
        instance = self.get_object()
        RFQAttachmentService.delete_attachment(instance.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
