"""
Serializers for projects app.
"""
from rest_framework import serializers
from django.db import transaction
from django.db.models import F
from .models import (
    Project, ProjectMember, ProjectTask, ProjectBOM, TimeLog, 
    ECN, ECNItem, ECNApproval,
    AfterSalesOrder, ServiceRecord, SparePartUsage,
    Drawing, DrawingChangeNotice
)


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
    """
    ProjectMember serializer with salary privacy protection.
    
    时薪信息只对以下角色可见：
    - 超级管理员
    - 项目经理（该项目的manager）
    - HR部门成员
    - 财务部门成员
    """
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_department = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    total_hours = serializers.DecimalField(source='actual_hours', max_digits=10, decimal_places=2, read_only=True)
    join_date = serializers.SerializerMethodField()
    labor_cost = serializers.SerializerMethodField()
    can_view_salary = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectMember
        fields = [
            'id', 'project', 'project_name', 'user', 'user_name', 'user_email', 
            'user_department', 'role', 'hourly_rate', 'allocated_hours', 'actual_hours',
            'total_hours', 'labor_cost', 'join_date', 'can_view_salary',
            'is_active', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'labor_cost', 'can_view_salary']
    
    def get_user_department(self, obj):
        """获取用户部门名称"""
        if obj.user and hasattr(obj.user, 'department') and obj.user.department:
            return obj.user.department.name
        return ''
    
    def get_join_date(self, obj):
        """获取加入日期"""
        if obj.created_at:
            return obj.created_at.strftime('%Y-%m-%d')
        return ''
    
    def get_labor_cost(self, obj):
        """
        获取人工成本（工时×时薪）
        需要有查看薪资权限才返回真实值，否则返回null
        """
        if self._can_view_salary_info(obj):
            return float(obj.actual_hours * obj.hourly_rate)
        return None
    
    def get_can_view_salary(self, obj):
        """标记当前用户是否有查看薪资的权限"""
        return self._can_view_salary_info(obj)
    
    def _can_view_salary_info(self, obj):
        """
        判断当前用户是否有权限查看薪资信息
        """
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        user = request.user
        
        # 超级管理员可以查看所有薪资信息
        if user.is_superuser:
            return True
        
        # 项目经理可以查看本项目所有成员的薪资
        if obj.project.manager_id == user.id:
            return True
        
        # HR部门和财务部门可以查看所有薪资信息
        if hasattr(user, 'department') and user.department:
            dept_name = user.department.name
            if dept_name in ['人力资源部', 'HR', '人事部', '财务部', '财务']:
                return True
        
        # 检查用户是否有特定权限（通过角色权限系统）
        if hasattr(user, 'roles'):
            for role in user.roles.all():
                if role.code in ['hr_manager', 'finance_manager', 'ceo', 'cfo']:
                    return True
        
        return False
    
    def to_representation(self, instance):
        """
        重写序列化输出，根据权限过滤敏感字段
        """
        data = super().to_representation(instance)
        
        # 如果没有查看薪资权限，移除敏感字段或设置为null
        if not self._can_view_salary_info(instance):
            data['hourly_rate'] = None  # 时薪设置为null
            data['labor_cost'] = None  # 人工成本设置为null
        
        return data


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
    """
    ProjectBOM serializer - 针对非标自动化行业优化
    """
    # ===== 项目信息 =====
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    # ===== 物料信息 =====
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_specification = serializers.CharField(source='item.specification', read_only=True, allow_blank=True)
    specification = serializers.CharField(source='item.specification', read_only=True, allow_blank=True)  # 别名
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    unit = serializers.CharField(source='item.get_unit_display', read_only=True)  # 别名
    item_type = serializers.CharField(source='item.get_item_type_display', read_only=True)
    item_brand = serializers.CharField(source='item.brand', read_only=True, allow_blank=True)
    item_model = serializers.CharField(source='item.model', read_only=True, allow_blank=True)
    item_material = serializers.CharField(source='item.material', read_only=True, allow_blank=True)
    item_lead_time = serializers.IntegerField(source='item.lead_time', read_only=True)
    version_brand_display = serializers.SerializerMethodField()
    item_standard_cost = serializers.DecimalField(source='item.standard_cost', max_digits=15, decimal_places=2, read_only=True)
    
    # ===== 显示字段 =====
    requester_name = serializers.CharField(source='requester.get_full_name', read_only=True)
    has_drawing_display = serializers.CharField(source='get_has_drawing_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    item_property_display = serializers.SerializerMethodField()
    
    # ===== 采购与库存字段 =====
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, allow_null=True)
    supplier_code = serializers.CharField(source='supplier.code', read_only=True, allow_null=True)
    purchase_request_no = serializers.CharField(source='purchase_request.request_no', read_only=True, allow_null=True)
    purchase_order_no = serializers.CharField(source='purchase_order.order_no', read_only=True, allow_null=True)
    
    # ===== 询价字段 =====
    quote_status_display = serializers.CharField(source='get_quote_status_display', read_only=True)
    quote_supplier_name = serializers.CharField(source='quote_supplier.name', read_only=True, allow_null=True)
    quote_supplier_code = serializers.CharField(source='quote_supplier.code', read_only=True, allow_null=True)
    
    # ===== 工位与工序 =====
    work_center_name = serializers.CharField(source='work_center.name', read_only=True, allow_null=True)
    process_name = serializers.CharField(source='process.name', read_only=True, allow_null=True)
    
    # ===== 需求追溯 =====
    # requirement_id_ref用于存储需求ID，避免循环引用
    
    # ===== 图纸关联 =====
    drawing_name = serializers.CharField(source='drawing.name', read_only=True, allow_null=True)
    
    # ===== 多级BOM字段 =====
    parent_name = serializers.CharField(source='parent.item.name', read_only=True, allow_null=True)
    children_count = serializers.SerializerMethodField()
    has_children = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    
    # ===== 计算属性 =====
    shortage_qty = serializers.DecimalField(read_only=True, max_digits=15, decimal_places=2)
    is_overdue = serializers.BooleanField(read_only=True)
    effective_item_property = serializers.CharField(read_only=True)
    
    class Meta:
        model = ProjectBOM
        fields = [
            'id', 'project', 'project_code', 'project_name', 
            'item', 'item_sku', 'item_code', 'item_name',
            'item_specification', 'specification', 'item_unit', 'unit', 
            'item_type', 'item_brand', 'item_model', 'item_material',
            'item_lead_time', 'item_standard_cost',
            # 物料属性与状态
            'item_property', 'item_property_display', 'effective_item_property',
            'status', 'status_display', 'priority', 'priority_display',
            # 数量
            'planned_qty', 'actual_qty', 'unit_qty', 'scrap_rate',
            # 成本
            'estimated_cost', 'target_cost', 'actual_cost', 'total_cost',
            # 图纸与技术
            'version_brand', 'version_brand_display', 'has_drawing', 'has_drawing_display',
            'drawing', 'drawing_name', 'drawing_no', 'drawing_version',
            'material_spec', 'surface_treatment', 'technical_requirement',
            # 装配与工艺
            'work_center', 'work_center_name', 'process', 'process_name',
            'assembly_sequence', 'assembly_instruction',
            # 需求追溯
            'requirement_id_ref', 'function_module',
            # 日期与时间
            'required_date', 'latest_order_date', 'requester', 'requester_name',
            'description', 'notes',
            # 采购与库存跟踪
            'order_status', 'order_status_display',
            'supplier', 'supplier_name', 'supplier_code',
            'delivery_date', 'actual_delivery_date',
            'purchase_request', 'purchase_request_no', 'pr_qty',
            'ordered_qty', 'shipped_qty', 'received_qty', 'returned_qty',
            'issued_qty', 'reserved_qty',
            'purchase_order', 'purchase_order_no',
            'shortage_qty', 'is_overdue',
            # 质量与检验
            'inspection_required', 'inspection_passed', 'inspection_notes',
            # 多级BOM
            'parent', 'parent_name', 'level', 'sort_order',
            'children_count', 'has_children', 'children',
            # 关键件标识
            'is_critical', 'is_long_lead',
            # 询价信息
            'quote_status', 'quote_status_display',
            'quote_supplier', 'quote_supplier_name', 'quote_supplier_code',
            'price_with_tax', 'price_without_tax', 'tax_rate',
            'quote_delivery_days', 'quote_date', 'quote_notes',
            # 扩展字段
            'extra_fields',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'shortage_qty', 'is_overdue', 
                          'effective_item_property', 'total_cost']
    
    def get_item_property_display(self, obj):
        """获取物料属性显示值"""
        if obj.item_property:
            return obj.get_item_property_display()
        return f"[继承]{obj.item.get_item_property_display()}" if obj.item else ''

    def get_version_brand_display(self, obj):
        """
        版本/品牌显示规则：
        - 如果BOM行填写了 version_brand，则优先展示（允许项目级覆盖）
        - 否则回退到物料主数据 brand/model 组合
        """
        if getattr(obj, 'version_brand', None):
            return obj.version_brand
        brand = getattr(obj.item, 'brand', '') if getattr(obj, 'item', None) else ''
        model = getattr(obj.item, 'model', '') if getattr(obj, 'item', None) else ''
        if brand and model:
            return f'{brand}/{model}'
        return brand or model or ''
    
    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()
    
    def get_has_children(self, obj):
        return obj.children.filter(is_deleted=False).exists()
    
    def get_children(self, obj):
        """递归获取子BOM项（仅顶层请求时展开）"""
        request = self.context.get('request')
        expand = request.query_params.get('expand_children', 'false') if request else 'false'
        
        if expand.lower() == 'true':
            children = obj.children.filter(is_deleted=False).order_by('sort_order', 'id')
            return ProjectBOMSerializer(children, many=True, context=self.context).data
        return None


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
        extra_kwargs = {
            'project': {'required': False},
            'task': {'required': False},
        }
    
    def get_task_name(self, obj):
        return obj.task.name if obj.task else None
    
    def create(self, validated_data):
        # 如果未显式传project，但提供了task，则自动关联task的project
        task = validated_data.get('task')
        if task and not validated_data.get('project'):
            validated_data['project'] = task.project
        validated_data['user'] = self.context['request'].user
        # 工时默认直接通过，并累计到任务的实际工时
        validated_data.setdefault('status', 'APPROVED')
        with transaction.atomic():
            instance = super().create(validated_data)
            if instance.task:
                ProjectTask.objects.filter(id=instance.task_id).update(
                    actual_hours=F('actual_hours') + instance.hours
                )
        return instance


class ECNItemSerializer(serializers.ModelSerializer):
    """ECNItem serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    new_item_name = serializers.CharField(source='new_item.name', read_only=True)
    new_item_sku = serializers.CharField(source='new_item.sku', read_only=True)
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    bom_item_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ECNItem
        fields = [
            'id', 'ecn', 'bom_item', 'bom_item_name', 
            'item', 'item_name', 'item_sku',
            'new_item', 'new_item_name', 'new_item_sku',
            'change_type', 'change_type_display', 'field_name',
            'old_value', 'new_value', 'old_qty', 'new_qty', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_bom_item_name(self, obj):
        if obj.bom_item:
            return f"{obj.bom_item.item.sku} - {obj.bom_item.item.name}"
        return None


class ECNApprovalSerializer(serializers.ModelSerializer):
    """ECNApproval serializer."""
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = ECNApproval
        fields = [
            'id', 'ecn', 'approver', 'approver_name', 
            'action', 'action_display', 'comment',
            'created_at'
        ]
        read_only_fields = ['approver', 'created_at']


class ECNSerializer(serializers.ModelSerializer):
    """ECN serializer."""
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    implemented_by_name = serializers.SerializerMethodField()
    items = ECNItemSerializer(many=True, read_only=True)
    approvals = ECNApprovalSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ECN
        fields = [
            'id', 'ecn_no', 'project', 'project_name', 'project_code',
            'title', 'change_type', 'change_type_display',
            'priority', 'priority_display', 'status', 'status_display',
            'reason', 'description', 'impact_analysis',
            'cost_impact', 'schedule_impact',
            'requested_by', 'requested_by_name', 'requested_date',
            'approved_by', 'approved_by_name', 'approved_date',
            'implemented_by', 'implemented_by_name', 'implemented_date',
            'implementation_notes', 'items', 'approvals', 'items_count',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['ecn_no', 'requested_by', 'approved_by', 'approved_date',
                           'implemented_by', 'implemented_date', 'created_at', 'updated_at']
    
    def get_approved_by_name(self, obj):
        return obj.approved_by.get_full_name() if obj.approved_by else None
    
    def get_implemented_by_name(self, obj):
        return obj.implemented_by.get_full_name() if obj.implemented_by else None
    
    def get_items_count(self, obj):
        return obj.items.count()
    
    def create(self, validated_data):
        validated_data['requested_by'] = self.context['request'].user
        return super().create(validated_data)


class ECNWriteSerializer(serializers.ModelSerializer):
    """ECN write serializer with items support."""
    items = ECNItemSerializer(many=True, required=False)
    
    class Meta:
        model = ECN
        fields = [
            'id', 'project', 'title', 'change_type', 'priority',
            'reason', 'description', 'impact_analysis',
            'cost_impact', 'schedule_impact', 'requested_date', 'items'
        ]
    
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        validated_data['requested_by'] = self.context['request'].user
        ecn = ECN.objects.create(**validated_data)
        
        for item_data in items_data:
            item_data.pop('ecn', None)
            ECNItem.objects.create(ecn=ecn, **item_data)
        
        return ecn
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if items_data is not None:
            # 删除旧的明细，创建新的
            instance.items.all().delete()
            for item_data in items_data:
                item_data.pop('ecn', None)
                ECNItem.objects.create(ecn=instance, **item_data)
        
        return instance


# ==================== 售后管理序列化器 ====================

class SparePartUsageSerializer(serializers.ModelSerializer):
    """备件使用记录序列化器"""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    total_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = SparePartUsage
        fields = [
            'id', 'aftersales_order', 'service_record', 'item', 'item_name', 'item_sku',
            'qty', 'unit_cost', 'total_cost', 'is_warranty', 'is_replaced',
            'serial_no', 'notes', 'created_at'
        ]


class ServiceRecordSerializer(serializers.ModelSerializer):
    """服务记录序列化器"""
    technician_name = serializers.CharField(source='technician.get_full_name', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    spare_parts = SparePartUsageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ServiceRecord
        fields = [
            'id', 'aftersales_order', 'service_type', 'service_type_display',
            'technician', 'technician_name', 'service_date', 'start_time', 'end_time',
            'work_hours', 'work_content', 'findings', 'actions_taken', 'result',
            'next_steps', 'labor_cost', 'travel_cost', 'customer_signature',
            'signed_at', 'spare_parts', 'created_at'
        ]


class AfterSalesOrderSerializer(serializers.ModelSerializer):
    """售后工单序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    service_records = ServiceRecordSerializer(many=True, read_only=True)
    spare_parts = SparePartUsageSerializer(many=True, read_only=True)
    
    # 统计字段
    service_count = serializers.SerializerMethodField()
    total_work_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = AfterSalesOrder
        fields = [
            'id', 'order_no', 'project', 'project_name', 'project_code',
            'customer', 'customer_name', 'order_type', 'order_type_display',
            'priority', 'priority_display', 'status', 'status_display',
            'title', 'description', 'equipment_info', 'fault_code',
            'contact_person', 'contact_phone', 'site_address',
            'reported_at', 'expected_date', 'resolved_at', 'closed_at',
            'assigned_to', 'assigned_to_name',
            'is_warranty', 'labor_cost', 'travel_cost', 'parts_cost', 'other_cost', 'total_cost',
            'solution', 'root_cause', 'preventive_action',
            'satisfaction_score', 'customer_feedback',
            'service_records', 'spare_parts',
            'service_count', 'total_work_hours',
            'created_at', 'updated_at'
        ]
    
    def get_service_count(self, obj):
        return obj.service_records.count()
    
    def get_total_work_hours(self, obj):
        from django.db.models import Sum
        result = obj.service_records.aggregate(total=Sum('work_hours'))
        return result['total'] or 0


class AfterSalesOrderListSerializer(serializers.ModelSerializer):
    """售后工单列表序列化器（简化版）"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    service_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AfterSalesOrder
        fields = [
            'id', 'order_no', 'project', 'project_name', 'project_code',
            'customer', 'customer_name', 'order_type', 'order_type_display',
            'priority', 'priority_display', 'status', 'status_display',
            'title', 'contact_person', 'contact_phone',
            'reported_at', 'expected_date', 'resolved_at',
            'assigned_to', 'assigned_to_name', 'is_warranty',
            'total_cost', 'service_count', 'satisfaction_score',
            'created_at'
        ]
    
    def get_service_count(self, obj):
        return obj.service_records.count()


class DrawingSerializer(serializers.ModelSerializer):
    """图纸序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    file_type_display = serializers.CharField(source='get_file_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    designer_name = serializers.CharField(source='designer.get_full_name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    
    class Meta:
        model = Drawing
        fields = [
            'id', 'drawing_no', 'name', 'version', 'revision',
            'project', 'project_name', 'project_code',
            'item', 'item_name', 'item_sku', 'bom_item',
            'file_type', 'file_type_display', 'file_path', 'file_size',
            'public_share_path', 'status', 'status_display',
            'designer', 'designer_name', 'reviewer', 'reviewer_name',
            'approver', 'approver_name', 'approved_at', 'released_at',
            'change_description', 'notes',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class DrawingChangeNoticeSerializer(serializers.ModelSerializer):
    """图纸变更通知序列化器"""
    drawing_no = serializers.CharField(source='drawing.drawing_no', read_only=True)
    drawing_name = serializers.CharField(source='drawing.name', read_only=True)
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    
    class Meta:
        model = DrawingChangeNotice
        fields = [
            'id', 'drawing', 'drawing_no', 'drawing_name',
            'change_type', 'change_type_display',
            'old_version', 'new_version', 'change_description',
            'email_sent', 'email_sent_at',
            'created_at'
        ]
