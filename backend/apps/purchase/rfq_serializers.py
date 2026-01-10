"""
RFQ serializers
询价单、供应商报价、比价分析序列化器
"""
from rest_framework import serializers
from .rfq_models import (
    RFQ, RFQLine, RFQSupplier, SupplierQuotation, SupplierQuotationLine,
    QuotationComparison, QuotationScore, ItemPriceHistory
)


class RFQLineSerializer(serializers.ModelSerializer):
    """RFQ line serializer"""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    
    class Meta:
        model = RFQLine
        fields = [
            'id', 'rfq', 'item', 'item_name', 'item_sku', 'qty',
            'required_date', 'specifications', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RFQSupplierSerializer(serializers.ModelSerializer):
    """RFQ supplier serializer"""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
    class Meta:
        model = RFQSupplier
        fields = [
            'id', 'rfq', 'supplier', 'supplier_name', 'sent_date',
            'is_responded', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'sent_date']


class RFQSerializer(serializers.ModelSerializer):
    """RFQ serializer"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = RFQLineSerializer(many=True, read_only=True)
    supplier_rfqs = RFQSupplierSerializer(many=True, read_only=True)
    
    class Meta:
        model = RFQ
        fields = [
            'id', 'rfq_no', 'project', 'project_name', 'request_date',
            'response_deadline', 'status', 'status_display', 'notes',
            'lines', 'supplier_rfqs', 'created_at', 'updated_at'
        ]
        read_only_fields = ['rfq_no', 'request_date', 'created_at', 'updated_at']


class SupplierQuotationLineSerializer(serializers.ModelSerializer):
    """Supplier quotation line serializer - 供应商报价明细"""
    item_name = serializers.CharField(source='rfq_line.item.name', read_only=True)
    item_sku = serializers.CharField(source='rfq_line.item.sku', read_only=True)
    item_unit = serializers.CharField(source='rfq_line.item.unit', read_only=True)
    
    class Meta:
        model = SupplierQuotationLine
        fields = [
            'id', 'quotation', 'rfq_line', 'item_name', 'item_sku', 'item_unit',
            'unit_price', 'unit_price_with_tax', 'qty', 'lead_time_days',
            'earliest_delivery_date', 'line_amount', 'line_amount_with_tax',
            'is_alternative', 'alternative_brand', 'alternative_model',
            'last_unit_price', 'price_change_rate', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'line_amount', 'line_amount_with_tax', 'unit_price_with_tax',
            'price_change_rate', 'created_at', 'updated_at'
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
            'id', 'quotation_no', 'rfq_supplier', 'supplier_id', 'supplier_name',
            'rfq_id', 'rfq_no', 'quotation_date', 'valid_until',
            'payment_terms', 'delivery_terms',
            'total_amount', 'tax_rate', 'tax_rate_display', 'tax_amount', 'total_with_tax',
            'warranty_period', 'min_order_qty',
            'last_purchase_price', 'price_change_rate',
            'status', 'status_display', 'notes',
            'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'quotation_no', 'quotation_date', 'tax_amount', 'total_with_tax',
            'price_change_rate', 'created_at', 'updated_at'
        ]


class QuotationScoreSerializer(serializers.ModelSerializer):
    """报价评分序列化器"""
    quotation_no = serializers.CharField(source='quotation.quotation_no', read_only=True)
    supplier_name = serializers.CharField(source='quotation.rfq_supplier.supplier.name', read_only=True)
    supplier_id = serializers.IntegerField(source='quotation.rfq_supplier.supplier.id', read_only=True)
    total_amount = serializers.DecimalField(
        source='quotation.total_amount',
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    total_with_tax = serializers.DecimalField(
        source='quotation.total_with_tax',
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = QuotationScore
        fields = [
            'id', 'comparison', 'quotation', 'quotation_no',
            'supplier_id', 'supplier_name', 'total_amount', 'total_with_tax',
            'score_price', 'score_quality', 'score_delivery', 'score_service',
            'total_score', 'ranking', 'is_recommended', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'quotation_no', 'supplier_id', 'supplier_name',
            'total_amount', 'total_with_tax', 'ranking',
            'created_at', 'updated_at'
        ]


class QuotationComparisonSerializer(serializers.ModelSerializer):
    """报价比价序列化器"""
    rfq_no = serializers.CharField(source='rfq.rfq_no', read_only=True)
    project_name = serializers.CharField(source='rfq.project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    scores = QuotationScoreSerializer(many=True, read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)
    recommended_supplier = serializers.CharField(
        source='recommended_quotation.rfq_supplier.supplier.name',
        read_only=True
    )
    supplier_count = serializers.SerializerMethodField()
    
    class Meta:
        model = QuotationComparison
        fields = [
            'id', 'comparison_no', 'rfq', 'rfq_no', 'project_name',
            'weight_price', 'weight_quality', 'weight_delivery', 'weight_service',
            'recommended_quotation', 'recommended_supplier', 'recommendation_reason',
            'min_price', 'max_price', 'avg_price',
            'status', 'status_display',
            'approved_by', 'approved_by_name', 'approved_at',
            'notes', 'scores', 'supplier_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'comparison_no', 'min_price', 'max_price', 'avg_price',
            'approved_by', 'approved_at', 'created_at', 'updated_at'
        ]
    
    def get_supplier_count(self, obj):
        return obj.scores.count()


class QuotationComparisonListSerializer(serializers.ModelSerializer):
    """报价比价列表序列化器（精简版）"""
    rfq_no = serializers.CharField(source='rfq.rfq_no', read_only=True)
    project_name = serializers.CharField(source='rfq.project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    recommended_supplier = serializers.CharField(
        source='recommended_quotation.rfq_supplier.supplier.name',
        read_only=True
    )
    supplier_count = serializers.SerializerMethodField()
    
    class Meta:
        model = QuotationComparison
        fields = [
            'id', 'comparison_no', 'rfq', 'rfq_no', 'project_name',
            'min_price', 'max_price', 'avg_price',
            'recommended_supplier', 'supplier_count',
            'status', 'status_display', 'created_at'
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
            'id', 'item', 'item_name', 'item_sku',
            'supplier', 'supplier_name',
            'unit_price', 'qty', 'tax_rate',
            'source_type', 'source_type_display', 'source_id', 'source_no',
            'price_date', 'created_at'
        ]
        read_only_fields = ['created_at']


class CreateComparisonSerializer(serializers.Serializer):
    """创建比价分析请求序列化器"""
    rfq_id = serializers.IntegerField(required=True)
    weight_price = serializers.DecimalField(max_digits=5, decimal_places=2, default=40)
    weight_quality = serializers.DecimalField(max_digits=5, decimal_places=2, default=25)
    weight_delivery = serializers.DecimalField(max_digits=5, decimal_places=2, default=20)
    weight_service = serializers.DecimalField(max_digits=5, decimal_places=2, default=15)
    
    def validate(self, data):
        """验证权重总和为100"""
        total = (
            float(data.get('weight_price', 40)) +
            float(data.get('weight_quality', 25)) +
            float(data.get('weight_delivery', 20)) +
            float(data.get('weight_service', 15))
        )
        if abs(total - 100) > 0.01:
            raise serializers.ValidationError(f"权重总和必须为100，当前为{total}")
        return data


class UpdateScoreSerializer(serializers.Serializer):
    """更新评分请求序列化器"""
    score_quality = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, min_value=0, max_value=100
    )
    score_service = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, min_value=0, max_value=100
    )
    notes = serializers.CharField(required=False, allow_blank=True)

