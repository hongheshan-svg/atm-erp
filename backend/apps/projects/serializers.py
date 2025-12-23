"""
Serializers for projects app.
"""
from rest_framework import serializers
from .models import Project, ProjectMember, ProjectTask, ProjectBOM, TimeLog


class ProjectSerializer(serializers.ModelSerializer):
    """Project serializer."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    sales_order_no = serializers.SerializerMethodField()
    
    # Calculated fields
    actual_material_cost = serializers.SerializerMethodField()
    actual_labor_cost = serializers.SerializerMethodField()
    actual_expense_cost = serializers.SerializerMethodField()
    total_actual_cost = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'code', 'name', 'customer', 'customer_name', 
            'sales_order', 'sales_order_no',
            'manager', 'manager_name',
            'start_date', 'end_date', 'status', 'status_display', 'budget_total',
            'budget_material', 'budget_labor', 'budget_expense', 'description', 'notes',
            'actual_material_cost', 'actual_labor_cost', 'actual_expense_cost',
            'total_actual_cost', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_sales_order_no(self, obj):
        return obj.sales_order.order_no if obj.sales_order else None
    
    def get_actual_material_cost(self, obj):
        # Will be calculated in reports service
        return 0
    
    def get_actual_labor_cost(self, obj):
        return float(obj.get_actual_labor_cost())
    
    def get_actual_expense_cost(self, obj):
        return 0
    
    def get_total_actual_cost(self, obj):
        return (
            self.get_actual_material_cost(obj) +
            self.get_actual_labor_cost(obj) +
            self.get_actual_expense_cost(obj)
        )


class ProjectMemberSerializer(serializers.ModelSerializer):
    """ProjectMember serializer."""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = ProjectMember
        fields = [
            'id', 'project', 'project_name', 'user', 'user_name', 'role',
            'hourly_rate', 'allocated_hours', 'actual_hours', 'is_active',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProjectTaskSerializer(serializers.ModelSerializer):
    """ProjectTask serializer."""
    project_name = serializers.CharField(source='project.name', read_only=True)
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ProjectTask
        fields = [
            'id', 'project', 'project_name', 'parent', 'code', 'name',
            'assignee', 'assignee_name', 'planned_hours', 'actual_hours',
            'progress_percent', 'status', 'status_display', 'start_date', 'end_date',
            'description', 'sort_order', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProjectBOMSerializer(serializers.ModelSerializer):
    """ProjectBOM serializer."""
    project_name = serializers.CharField(source='project.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    
    class Meta:
        model = ProjectBOM
        fields = [
            'id', 'project', 'project_name', 'item', 'item_sku', 'item_name',
            'item_unit', 'planned_qty', 'actual_qty', 'estimated_cost', 'notes',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TimeLogSerializer(serializers.ModelSerializer):
    """TimeLog serializer."""
    project_name = serializers.CharField(source='project.name', read_only=True)
    task_name = serializers.SerializerMethodField()
    user_name = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = TimeLog
        fields = [
            'id', 'project', 'project_name', 'task', 'task_name', 'user', 'user_name',
            'date', 'hours', 'description', 'status', 'status_display',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']
    
    def get_task_name(self, obj):
        return obj.task.name if obj.task else None
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
