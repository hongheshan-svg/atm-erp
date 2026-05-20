"""
生产管理模块序列化器
"""
from rest_framework import serializers

from .models import (
    DebugCheckItem,
    DebugRecord,
    InspectionItem,
    ProductionLog,
    ProductionPlan,
    ProductionPlanProcess,
    ProductionProcess,
    QualityInspection,
)


class ProductionProcessSerializer(serializers.ModelSerializer):
    """生产工序序列化器"""
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    process_type_display = serializers.CharField(source='get_process_type_display', read_only=True)
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True)

    class Meta:
        model = ProductionProcess
        fields = [
            'id', 'project', 'project_code', 'project_name',
            'process_no', 'name', 'process_type', 'process_type_display',
            'sequence', 'planned_hours', 'actual_hours',
            'assignee', 'assignee_name', 'work_center',
            'description', 'work_instruction', 'quality_requirements',
            'bom_items', 'notes',
            'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProductionPlanProcessSerializer(serializers.ModelSerializer):
    """生产计划工序序列化器"""
    process_no = serializers.CharField(source='process.process_no', read_only=True)
    process_name = serializers.CharField(source='process.name', read_only=True)
    process_type = serializers.CharField(source='process.process_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)

    class Meta:
        model = ProductionPlanProcess
        fields = [
            'id', 'plan', 'process', 'process_no', 'process_name', 'process_type',
            'planned_start', 'planned_end', 'actual_start', 'actual_end',
            'status', 'status_display', 'progress_percent',
            'planned_hours', 'actual_hours',
            'operator', 'operator_name', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProductionPlanSerializer(serializers.ModelSerializer):
    """生产计划序列化器"""
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    planner_name = serializers.CharField(source='planner.get_full_name', read_only=True)
    production_manager_name = serializers.CharField(source='production_manager.get_full_name', read_only=True)
    plan_processes = ProductionPlanProcessSerializer(many=True, read_only=True)

    class Meta:
        model = ProductionPlan
        fields = [
            'id', 'project', 'project_code', 'project_name',
            'plan_no', 'title', 'planned_start', 'planned_end',
            'actual_start', 'actual_end', 'status', 'status_display',
            'progress_percent', 'planner', 'planner_name',
            'production_manager', 'production_manager_name',
            'description', 'notes', 'plan_processes',
            'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['plan_no', 'created_at', 'updated_at']


class ProductionLogSerializer(serializers.ModelSerializer):
    """生产日志序列化器"""
    plan_no = serializers.CharField(source='plan_process.plan.plan_no', read_only=True)
    process_name = serializers.CharField(source='plan_process.process.name', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)

    class Meta:
        model = ProductionLog
        fields = [
            'id', 'plan_process', 'plan_no', 'process_name',
            'log_date', 'operator', 'operator_name',
            'work_hours', 'work_content', 'progress_percent',
            'issues', 'solutions',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class DebugCheckItemSerializer(serializers.ModelSerializer):
    """调试检查项序列化器"""
    result_display = serializers.CharField(source='get_result_display', read_only=True)

    class Meta:
        model = DebugCheckItem
        fields = [
            'id', 'debug_record', 'sequence', 'item_name',
            'standard', 'method', 'result', 'result_display',
            'actual_value', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class DebugRecordSerializer(serializers.ModelSerializer):
    """调试记录序列化器"""
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    debug_type_display = serializers.CharField(source='get_debug_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    debugger_name = serializers.CharField(source='debugger.get_full_name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    check_items = DebugCheckItemSerializer(many=True, read_only=True)

    # 统计字段
    total_items = serializers.SerializerMethodField()
    pass_items = serializers.SerializerMethodField()
    fail_items = serializers.SerializerMethodField()

    class Meta:
        model = DebugRecord
        fields = [
            'id', 'project', 'project_code', 'project_name',
            'record_no', 'title', 'debug_type', 'debug_type_display',
            'status', 'status_display', 'result', 'result_display',
            'planned_date', 'debug_date', 'completed_at',
            'debugger', 'debugger_name', 'reviewer', 'reviewer_name',
            'debug_content', 'test_conditions', 'expected_result', 'actual_result',
            'issues_found', 'solutions', 'remaining_issues',
            'attachments', 'notes', 'check_items',
            'total_items', 'pass_items', 'fail_items',
            'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['record_no', 'created_at', 'updated_at']

    def get_total_items(self, obj):
        return obj.check_items.count()

    def get_pass_items(self, obj):
        return obj.check_items.filter(result='PASS').count()

    def get_fail_items(self, obj):
        return obj.check_items.filter(result='FAIL').count()


class InspectionItemSerializer(serializers.ModelSerializer):
    """检验项目序列化器"""
    result_display = serializers.CharField(source='get_result_display', read_only=True)

    class Meta:
        model = InspectionItem
        fields = [
            'id', 'inspection', 'sequence', 'item_name',
            'standard', 'method',
            'nominal_value', 'tolerance_upper', 'tolerance_lower',
            'actual_value', 'result', 'result_display', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class QualityInspectionSerializer(serializers.ModelSerializer):
    """质量检验序列化器"""
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    inspection_type_display = serializers.CharField(source='get_inspection_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    plan_no = serializers.CharField(source='production_plan.plan_no', read_only=True)
    process_name = serializers.CharField(source='process.name', read_only=True)
    items = InspectionItemSerializer(many=True, read_only=True)

    # 统计字段
    pass_rate = serializers.SerializerMethodField()

    class Meta:
        model = QualityInspection
        fields = [
            'id', 'project', 'project_code', 'project_name',
            'inspection_no', 'inspection_type', 'inspection_type_display',
            'title', 'production_plan', 'plan_no', 'process', 'process_name',
            'goods_receipt', 'status', 'status_display',
            'result', 'result_display',
            'planned_date', 'inspection_date',
            'inspector', 'inspector_name', 'reviewer', 'reviewer_name',
            'inspection_standard', 'sampling_method',
            'sample_qty', 'pass_qty', 'fail_qty',
            'conclusion', 'treatment', 'notes', 'items', 'pass_rate',
            'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['inspection_no', 'created_at', 'updated_at']

    def get_pass_rate(self, obj):
        if obj.sample_qty > 0:
            return round(obj.pass_qty / obj.sample_qty * 100, 2)
        return 0

