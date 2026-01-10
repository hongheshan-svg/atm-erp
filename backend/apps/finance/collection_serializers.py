"""
回款计划管理序列化器
"""
from rest_framework import serializers
from .collection_models import (
    CollectionPlan, CollectionMilestone, CollectionRecord, CollectionReminder
)


class CollectionRecordSerializer(serializers.ModelSerializer):
    """收款记录序列化器"""
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.name', read_only=True)
    
    class Meta:
        model = CollectionRecord
        fields = '__all__'


class CollectionMilestoneSerializer(serializers.ModelSerializer):
    """回款节点序列化器"""
    milestone_type_display = serializers.CharField(source='get_milestone_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    overdue_days = serializers.IntegerField(read_only=True)
    records = CollectionRecordSerializer(many=True, read_only=True)
    remaining_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = CollectionMilestone
        fields = '__all__'
    
    def get_remaining_amount(self, obj):
        return float(obj.planned_amount - obj.collected_amount)


class CollectionMilestoneListSerializer(serializers.ModelSerializer):
    """回款节点列表序列化器（简化）"""
    milestone_type_display = serializers.CharField(source='get_milestone_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    overdue_days = serializers.IntegerField(read_only=True)
    plan_no = serializers.CharField(source='plan.plan_no', read_only=True)
    customer_name = serializers.CharField(source='plan.customer.name', read_only=True)
    project_name = serializers.CharField(source='plan.project.name', read_only=True)
    
    class Meta:
        model = CollectionMilestone
        fields = [
            'id', 'plan', 'plan_no', 'milestone_type', 'milestone_type_display',
            'name', 'percentage', 'planned_amount', 'collected_amount',
            'planned_date', 'actual_date', 'status', 'status_display',
            'is_overdue', 'overdue_days', 'customer_name', 'project_name'
        ]


class CollectionPlanSerializer(serializers.ModelSerializer):
    """回款计划序列化器"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    collection_rate = serializers.FloatField(read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    milestones = CollectionMilestoneSerializer(many=True, read_only=True)
    
    class Meta:
        model = CollectionPlan
        fields = '__all__'
        read_only_fields = ['plan_no', 'collected_amount']


class CollectionPlanListSerializer(serializers.ModelSerializer):
    """回款计划列表序列化器（简化）"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    collection_rate = serializers.FloatField(read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    milestone_count = serializers.SerializerMethodField()
    overdue_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CollectionPlan
        fields = [
            'id', 'plan_no', 'name', 'customer', 'customer_name',
            'project', 'project_name', 'total_amount', 'collected_amount',
            'status', 'status_display', 'owner', 'owner_name',
            'collection_rate', 'remaining_amount', 'milestone_count',
            'overdue_count', 'created_at'
        ]
    
    def get_milestone_count(self, obj):
        return obj.milestones.filter(is_deleted=False).count()
    
    def get_overdue_count(self, obj):
        from django.utils import timezone
        return obj.milestones.filter(
            is_deleted=False,
            status__in=['PENDING', 'PARTIAL'],
            planned_date__lt=timezone.now().date()
        ).count()


class CollectionReminderSerializer(serializers.ModelSerializer):
    """回款提醒序列化器"""
    reminder_type_display = serializers.CharField(source='get_reminder_type_display', read_only=True)
    milestone_name = serializers.CharField(source='milestone.name', read_only=True)
    plan_no = serializers.CharField(source='milestone.plan.plan_no', read_only=True)
    
    class Meta:
        model = CollectionReminder
        fields = '__all__'


class CreateMilestoneSerializer(serializers.Serializer):
    """批量创建节点序列化器"""
    milestones = serializers.ListField(child=serializers.DictField())


class CollectionSummarySerializer(serializers.Serializer):
    """回款汇总序列化器"""
    total_plans = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    collected_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    collection_rate = serializers.FloatField()
    overdue_count = serializers.IntegerField()
    overdue_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    upcoming_count = serializers.IntegerField()
    upcoming_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
