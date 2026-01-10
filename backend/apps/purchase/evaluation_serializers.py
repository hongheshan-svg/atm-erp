"""
供应商评价管理序列化器
"""
from rest_framework import serializers
from apps.accounts.serializers import UserSerializer
from apps.masterdata.serializers import SupplierSerializer
from .evaluation_models import (
    SupplierEvaluationTemplate, EvaluationCriteria,
    SupplierEvaluation, EvaluationScoreItem,
    SupplierGradeHistory, SupplierBlacklist
)


class EvaluationCriteriaSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = EvaluationCriteria
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class SupplierEvaluationTemplateSerializer(serializers.ModelSerializer):
    criteria = EvaluationCriteriaSerializer(many=True, read_only=True)
    criteria_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SupplierEvaluationTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']
    
    def get_criteria_count(self, obj):
        return obj.criteria.count()


class EvaluationScoreItemSerializer(serializers.ModelSerializer):
    criteria_detail = EvaluationCriteriaSerializer(source='criteria', read_only=True)
    
    class Meta:
        model = EvaluationScoreItem
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class SupplierEvaluationSerializer(serializers.ModelSerializer):
    supplier_detail = SupplierSerializer(source='supplier', read_only=True)
    template_detail = SupplierEvaluationTemplateSerializer(source='template', read_only=True)
    evaluator_detail = UserSerializer(source='evaluator', read_only=True)
    approver_detail = UserSerializer(source='approver', read_only=True)
    score_items = EvaluationScoreItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    period_type_display = serializers.CharField(source='get_period_type_display', read_only=True)
    
    class Meta:
        model = SupplierEvaluation
        fields = '__all__'
        read_only_fields = [
            'created_by', 'updated_by', 'evaluation_no',
            'total_score', 'quality_score', 'delivery_score',
            'price_score', 'service_score', 'grade',
            'approver', 'approved_at'
        ]


class SupplierEvaluationCreateSerializer(serializers.ModelSerializer):
    """创建评价时的序列化器"""
    score_items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = SupplierEvaluation
        fields = '__all__'
        read_only_fields = [
            'created_by', 'updated_by', 'evaluation_no',
            'total_score', 'quality_score', 'delivery_score',
            'price_score', 'service_score', 'grade',
            'approver', 'approved_at', 'status'
        ]
    
    def create(self, validated_data):
        score_items_data = validated_data.pop('score_items', [])
        evaluation = super().create(validated_data)
        
        # 创建评分明细
        for item_data in score_items_data:
            EvaluationScoreItem.objects.create(
                evaluation=evaluation,
                criteria_id=item_data['criteria'],
                score=item_data['score'],
                comments=item_data.get('comments', ''),
                created_by=evaluation.created_by
            )
        
        # 计算评分
        evaluation.calculate_scores()
        return evaluation


class SupplierGradeHistorySerializer(serializers.ModelSerializer):
    supplier_detail = SupplierSerializer(source='supplier', read_only=True)
    
    class Meta:
        model = SupplierGradeHistory
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class SupplierBlacklistSerializer(serializers.ModelSerializer):
    supplier_detail = SupplierSerializer(source='supplier', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lifted_by_detail = UserSerializer(source='lifted_by', read_only=True)
    
    class Meta:
        model = SupplierBlacklist
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'lifted_by', 'lifted_date']
