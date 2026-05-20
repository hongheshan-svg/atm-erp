"""
CRM - 商机/线索管理序列化器
"""

from rest_framework import serializers

from .crm_models import Lead, LeadSource, Opportunity, OpportunityActivity, SalesForecast


class LeadSourceSerializer(serializers.ModelSerializer):
    """线索来源序列化器"""

    class Meta:
        model = LeadSource
        fields = '__all__'


class LeadSerializer(serializers.ModelSerializer):
    """销售线索序列化器"""

    source_name = serializers.CharField(source='source.name', read_only=True)
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    converted_customer_name = serializers.CharField(source='converted_customer.name', read_only=True)

    class Meta:
        model = Lead
        fields = '__all__'
        read_only_fields = ['lead_no', 'converted_at']


class LeadListSerializer(serializers.ModelSerializer):
    """线索列表序列化器（简化）"""

    source_name = serializers.CharField(source='source.name', read_only=True)
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id',
            'lead_no',
            'company_name',
            'contact_name',
            'contact_phone',
            'industry',
            'source',
            'source_name',
            'status',
            'status_display',
            'owner',
            'owner_name',
            'score',
            'created_at',
        ]


class OpportunityActivitySerializer(serializers.ModelSerializer):
    """商机活动序列化器"""

    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.name', read_only=True)

    class Meta:
        model = OpportunityActivity
        fields = '__all__'


class OpportunitySerializer(serializers.ModelSerializer):
    """销售商机序列化器"""

    customer_name = serializers.CharField(source='customer.name', read_only=True)
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    activities = OpportunityActivitySerializer(many=True, read_only=True)
    recent_activity = serializers.SerializerMethodField()
    days_in_stage = serializers.SerializerMethodField()

    class Meta:
        model = Opportunity
        fields = '__all__'
        read_only_fields = ['opportunity_no', 'weighted_amount', 'actual_close_date']

    def get_recent_activity(self, obj):
        activity = obj.activities.order_by('-activity_date').first()
        if activity:
            return {
                'type': activity.get_activity_type_display(),
                'subject': activity.subject,
                'date': activity.activity_date,
            }
        return None

    def get_days_in_stage(self, obj):
        from django.utils import timezone

        return (timezone.now() - obj.updated_at).days


class OpportunityListSerializer(serializers.ModelSerializer):
    """商机列表序列化器（简化）"""

    customer_name = serializers.CharField(source='customer.name', read_only=True)
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = Opportunity
        fields = [
            'id',
            'opportunity_no',
            'name',
            'customer',
            'customer_name',
            'stage',
            'stage_display',
            'priority',
            'priority_display',
            'probability',
            'estimated_amount',
            'weighted_amount',
            'expected_close_date',
            'owner',
            'owner_name',
            'created_at',
        ]


class SalesForecastSerializer(serializers.ModelSerializer):
    """销售预测序列化器"""

    owner_name = serializers.CharField(source='owner.name', read_only=True)

    class Meta:
        model = SalesForecast
        fields = '__all__'


class LeadConvertSerializer(serializers.Serializer):
    """线索转化序列化器"""

    create_customer = serializers.BooleanField(default=True, help_text='是否创建新客户')
    customer_id = serializers.IntegerField(required=False, help_text='已有客户ID')
    create_opportunity = serializers.BooleanField(default=True, help_text='是否创建商机')
    opportunity_name = serializers.CharField(required=False, help_text='商机名称')
    estimated_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)


class OpportunityStageChangeSerializer(serializers.Serializer):
    """商机阶段变更序列化器"""

    new_stage = serializers.ChoiceField(choices=Opportunity.STAGE_CHOICES)
    probability = serializers.IntegerField(required=False)
    notes = serializers.CharField(required=False)
    lost_reason = serializers.CharField(required=False, help_text='丢单原因（仅当阶段为CLOSED_LOST时）')


class SalesPipelineSerializer(serializers.Serializer):
    """销售漏斗统计序列化器"""

    stage = serializers.CharField()
    stage_display = serializers.CharField()
    count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    weighted_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
