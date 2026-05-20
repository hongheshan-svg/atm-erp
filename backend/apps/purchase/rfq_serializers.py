"""
RFQ serializers
询价单、供应商报价、比价分析序列化器
"""

from rest_framework import serializers

from .rfq_models import (
    RFQ,
    ItemPriceHistory,
    QuotationComparison,
    QuotationScore,
    RFQLine,
    RFQSupplier,
    SupplierQuotation,
    SupplierQuotationLine,
)


class RFQLineSerializer(serializers.ModelSerializer):
    """RFQ line serializer - 询价单明细（非标自动化增强版）"""

    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.unit', read_only=True)
    drawing_name = serializers.CharField(source='drawing.name', read_only=True)
    last_supplier_name = serializers.CharField(source='last_supplier.name', read_only=True)

    class Meta:
        model = RFQLine
        fields = [
            'id',
            'rfq',
            'item',
            'item_name',
            'item_sku',
            'item_unit',
            'qty',
            'required_date',
            'specifications',
            # 非标自动化增强字段
            'bom_item',
            'drawing',
            'drawing_name',
            'drawing_no',
            'drawing_version',
            'technical_specs',
            'is_critical',
            'is_long_lead',
            'is_custom',
            'sample_qty',
            'sample_required_date',
            'target_price',
            'last_supplier',
            'last_supplier_name',
            'last_price',
            'attachment_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'attachment_count']


class RFQSupplierSerializer(serializers.ModelSerializer):
    """RFQ supplier serializer"""

    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = RFQSupplier
        fields = ['id', 'rfq', 'supplier', 'supplier_name', 'sent_date', 'is_responded', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'sent_date']


class RFQSerializer(serializers.ModelSerializer):
    """RFQ serializer - 询价单（非标自动化增强版）"""

    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    rfq_type_display = serializers.CharField(source='get_rfq_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    lines = RFQLineSerializer(many=True, read_only=True)
    supplier_rfqs = RFQSupplierSerializer(many=True, read_only=True)
    supplier_count = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()

    class Meta:
        model = RFQ
        fields = [
            'id',
            'rfq_no',
            'project',
            'project_name',
            'project_code',
            'request_date',
            'response_deadline',
            'status',
            'status_display',
            'notes',
            # 非标自动化增强字段
            'rfq_type',
            'rfq_type_display',
            'priority',
            'priority_display',
            'template',
            'template_name',
            'technical_requirements',
            'quality_requirements',
            'packaging_requirements',
            'delivery_requirements',
            'attachment_count',
            'lines',
            'supplier_rfqs',
            'supplier_count',
            'line_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['rfq_no', 'request_date', 'attachment_count', 'created_at', 'updated_at']

    def get_supplier_count(self, obj):
        return obj.supplier_rfqs.count()

    def get_line_count(self, obj):
        return obj.lines.filter(is_deleted=False).count()


class SupplierQuotationLineSerializer(serializers.ModelSerializer):
    """Supplier quotation line serializer - 供应商报价明细"""

    item_name = serializers.CharField(source='rfq_line.item.name', read_only=True)
    item_sku = serializers.CharField(source='rfq_line.item.sku', read_only=True)
    item_unit = serializers.CharField(source='rfq_line.item.unit', read_only=True)

    class Meta:
        model = SupplierQuotationLine
        fields = [
            'id',
            'quotation',
            'rfq_line',
            'item_name',
            'item_sku',
            'item_unit',
            'unit_price',
            'unit_price_with_tax',
            'qty',
            'lead_time_days',
            'earliest_delivery_date',
            'line_amount',
            'line_amount_with_tax',
            # 非标自动化增强字段
            'technical_specs',
            'drawing_version',
            'drawing_no',
            'sample_qty',
            'sample_delivery_days',
            'sample_delivery_date',
            'sample_unit_price',
            'batch_delivery_date',
            'process_capability',
            'quality_commitment',
            'inspection_report',
            'first_article_inspection',
            # 替代品信息
            'is_alternative',
            'alternative_brand',
            'alternative_model',
            'last_unit_price',
            'price_change_rate',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'line_amount',
            'line_amount_with_tax',
            'unit_price_with_tax',
            'price_change_rate',
            'created_at',
            'updated_at',
        ]


class SupplierQuotationSerializer(serializers.ModelSerializer):
    """Supplier quotation serializer - 供应商报价"""

    supplier_name = serializers.CharField(source='rfq_supplier.supplier.name', read_only=True)
    supplier_id = serializers.IntegerField(source='rfq_supplier.supplier.id', read_only=True)
    rfq_no = serializers.CharField(source='rfq_supplier.rfq.rfq_no', read_only=True)
    rfq_id = serializers.IntegerField(source='rfq_supplier.rfq.id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tax_rate_display = serializers.CharField(source='get_tax_rate_display', read_only=True)
    lines = SupplierQuotationLineSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierQuotation
        fields = [
            'id',
            'quotation_no',
            'rfq_supplier',
            'supplier_id',
            'supplier_name',
            'rfq_id',
            'rfq_no',
            'quotation_date',
            'valid_until',
            'payment_terms',
            'delivery_terms',
            'total_amount',
            'tax_rate',
            'tax_rate_display',
            'tax_amount',
            'total_with_tax',
            'warranty_period',
            'min_order_qty',
            'last_purchase_price',
            'price_change_rate',
            'status',
            'status_display',
            'notes',
            'lines',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'quotation_no',
            'quotation_date',
            'tax_amount',
            'total_with_tax',
            'price_change_rate',
            'created_at',
            'updated_at',
        ]


class QuotationScoreSerializer(serializers.ModelSerializer):
    """报价评分序列化器"""

    quotation_no = serializers.CharField(source='quotation.quotation_no', read_only=True)
    supplier_name = serializers.CharField(source='quotation.rfq_supplier.supplier.name', read_only=True)
    supplier_id = serializers.IntegerField(source='quotation.rfq_supplier.supplier.id', read_only=True)
    total_amount = serializers.DecimalField(
        source='quotation.total_amount', max_digits=15, decimal_places=2, read_only=True
    )
    total_with_tax = serializers.DecimalField(
        source='quotation.total_with_tax', max_digits=15, decimal_places=2, read_only=True
    )

    class Meta:
        model = QuotationScore
        fields = [
            'id',
            'comparison',
            'quotation',
            'quotation_no',
            'supplier_id',
            'supplier_name',
            'total_amount',
            'total_with_tax',
            'score_price',
            'score_quality',
            'score_delivery',
            'score_service',
            'score_technical',
            'score_reliability',  # 新增评分维度
            'total_score',
            'ranking',
            'price_rank',
            'delivery_rank',
            'quality_rank',  # 多维度排名
            'recommend_type',
            'is_recommended',
            'risk_warnings',  # 风险提示
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'quotation_no',
            'supplier_id',
            'supplier_name',
            'total_amount',
            'total_with_tax',
            'ranking',
            'price_rank',
            'delivery_rank',
            'quality_rank',
            'score_reliability',
            'risk_warnings',
            'created_at',
            'updated_at',
        ]


class QuotationComparisonSerializer(serializers.ModelSerializer):
    """报价比价序列化器"""

    rfq_no = serializers.CharField(source='rfq.rfq_no', read_only=True)
    project_name = serializers.CharField(source='rfq.project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    comparison_type_display = serializers.CharField(source='get_comparison_type_display', read_only=True)
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    weight_template_display = serializers.CharField(source='get_weight_template_display', read_only=True)
    scores = QuotationScoreSerializer(many=True, read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    recommended_supplier = serializers.CharField(
        source='recommended_quotation.rfq_supplier.supplier.name', read_only=True
    )
    supplier_count = serializers.SerializerMethodField()

    class Meta:
        model = QuotationComparison
        fields = [
            'id',
            'comparison_no',
            'rfq',
            'rfq_no',
            'project_name',
            # 非标自动化增强字段
            'comparison_type',
            'comparison_type_display',
            'risk_level',
            'risk_level_display',
            'critical_items_count',
            'long_lead_items_count',
            'weight_template',
            'weight_template_display',
            # 权重配置
            'weight_price',
            'weight_quality',
            'weight_delivery',
            'weight_service',
            'weight_technical',
            'recommended_quotation',
            'recommended_supplier',
            'recommendation_reason',
            'min_price',
            'max_price',
            'avg_price',
            'status',
            'status_display',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'notes',
            'scores',
            'supplier_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'comparison_no',
            'min_price',
            'max_price',
            'avg_price',
            'critical_items_count',
            'long_lead_items_count',
            'approved_by',
            'approved_at',
            'created_at',
            'updated_at',
        ]

    def get_supplier_count(self, obj):
        return obj.scores.count()


class QuotationComparisonListSerializer(serializers.ModelSerializer):
    """报价比价列表序列化器（精简版）"""

    rfq_no = serializers.CharField(source='rfq.rfq_no', read_only=True)
    project_name = serializers.CharField(source='rfq.project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    comparison_type_display = serializers.CharField(source='get_comparison_type_display', read_only=True)
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    recommended_supplier = serializers.CharField(
        source='recommended_quotation.rfq_supplier.supplier.name', read_only=True
    )
    supplier_count = serializers.SerializerMethodField()

    class Meta:
        model = QuotationComparison
        fields = [
            'id',
            'comparison_no',
            'rfq',
            'rfq_no',
            'project_name',
            'comparison_type',
            'comparison_type_display',
            'risk_level',
            'risk_level_display',
            'critical_items_count',
            'long_lead_items_count',
            'min_price',
            'max_price',
            'avg_price',
            'recommended_supplier',
            'supplier_count',
            'status',
            'status_display',
            'created_at',
        ]

    def get_supplier_count(self, obj):
        return obj.scores.count()


class ItemPriceHistorySerializer(serializers.ModelSerializer):
    """物料价格历史序列化器"""

    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = ItemPriceHistory
        fields = [
            'id',
            'item',
            'item_name',
            'item_sku',
            'supplier',
            'supplier_name',
            'unit_price',
            'qty',
            'tax_rate',
            'source_type',
            'source_type_display',
            'source_id',
            'source_no',
            'price_date',
            'created_at',
        ]
        read_only_fields = ['created_at']


class CreateComparisonSerializer(serializers.Serializer):
    """创建比价分析请求序列化器"""

    rfq_id = serializers.IntegerField(required=True)
    comparison_type = serializers.ChoiceField(
        choices=['NORMAL', 'SAMPLE', 'BATCH', 'URGENT', 'CHANGE'], default='NORMAL'
    )
    weight_template = serializers.ChoiceField(
        choices=['STANDARD', 'QUALITY_FIRST', 'DELIVERY_FIRST', 'PRICE_FIRST', 'CUSTOM'], default='STANDARD'
    )
    weight_price = serializers.DecimalField(max_digits=5, decimal_places=2, default=40, required=False)
    weight_quality = serializers.DecimalField(max_digits=5, decimal_places=2, default=25, required=False)
    weight_delivery = serializers.DecimalField(max_digits=5, decimal_places=2, default=20, required=False)
    weight_service = serializers.DecimalField(max_digits=5, decimal_places=2, default=15, required=False)
    weight_technical = serializers.DecimalField(max_digits=5, decimal_places=2, default=0, required=False)

    def validate(self, data):
        """验证权重总和为100（仅在自定义权重时）"""
        if data.get('weight_template') == 'CUSTOM':
            total = (
                float(data.get('weight_price', 40))
                + float(data.get('weight_quality', 25))
                + float(data.get('weight_delivery', 20))
                + float(data.get('weight_service', 15))
                + float(data.get('weight_technical', 0))
            )
            if abs(total - 100) > 0.01:
                raise serializers.ValidationError(f'权重总和必须为100，当前为{total}')
        return data


class UpdateScoreSerializer(serializers.Serializer):
    """更新评分请求序列化器"""

    score_quality = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, min_value=0, max_value=100)
    score_service = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, min_value=0, max_value=100)
    notes = serializers.CharField(required=False, allow_blank=True)
