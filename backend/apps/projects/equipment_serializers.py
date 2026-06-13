"""
设备台账和工装夹具序列化器
"""

from rest_framework import serializers

from .equipment_models import (
    Equipment,
    EquipmentAcceptance,
    EquipmentInstallation,
    EquipmentShipment,
    InstallationLog,
    MaintenanceSchedule,
    TrainingRecord,
)
from .fixture_models import Fixture, FixtureCalibration, FixtureCategory, FixtureMaintenance, FixtureUsageRecord


def _display_name(user):
    """返回用户显示名：姓名优先，否则用户名。User(AbstractUser) 无 name 字段。"""
    if not user:
        return ''
    name = f'{user.last_name}{user.first_name}'
    return name if name else user.username


# ============================================================
# 设备台账序列化器
# ============================================================


class EquipmentSerializer(serializers.ModelSerializer):
    """设备台账序列化器"""

    project_name = serializers.CharField(source='project.name', read_only=True)
    project_no = serializers.CharField(source='project.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_in_warranty = serializers.BooleanField(read_only=True)

    class Meta:
        model = Equipment
        fields = '__all__'
        read_only_fields = ['equipment_no']


class EquipmentListSerializer(serializers.ModelSerializer):
    """设备台账列表序列化器（简化）"""

    project_name = serializers.CharField(source='project.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_in_warranty = serializers.BooleanField(read_only=True)

    class Meta:
        model = Equipment
        fields = [
            'id',
            'equipment_no',
            'name',
            'model',
            'serial_no',
            'project',
            'project_name',
            'customer',
            'customer_name',
            'status',
            'status_display',
            'acceptance_date',
            'warranty_end_date',
            'is_in_warranty',
            'installation_address',
        ]


class EquipmentShipmentSerializer(serializers.ModelSerializer):
    """设备发货记录序列化器"""

    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EquipmentShipment
        fields = '__all__'


class InstallationLogSerializer(serializers.ModelSerializer):
    """安装日志序列化器"""

    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InstallationLog
        fields = '__all__'

    def get_recorded_by_name(self, obj):
        return _display_name(obj.recorded_by)


class EquipmentInstallationSerializer(serializers.ModelSerializer):
    """现场安装记录序列化器"""

    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    team_leader_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    daily_logs = InstallationLogSerializer(many=True, read_only=True)

    class Meta:
        model = EquipmentInstallation
        fields = '__all__'

    def get_team_leader_name(self, obj):
        return _display_name(obj.team_leader)


class EquipmentAcceptanceSerializer(serializers.ModelSerializer):
    """设备验收记录序列化器"""

    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    our_representative_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EquipmentAcceptance
        fields = '__all__'

    def get_our_representative_name(self, obj):
        return _display_name(obj.our_representative)


class MaintenanceScheduleSerializer(serializers.ModelSerializer):
    """设备保养计划序列化器"""

    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    maintenance_type_display = serializers.CharField(source='get_maintenance_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MaintenanceSchedule
        fields = '__all__'


class TrainingRecordSerializer(serializers.ModelSerializer):
    """客户培训记录序列化器"""

    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    trainer_name = serializers.SerializerMethodField()
    training_type_display = serializers.CharField(source='get_training_type_display', read_only=True)

    class Meta:
        model = TrainingRecord
        fields = '__all__'
        read_only_fields = ['training_no']

    def get_trainer_name(self, obj):
        return _display_name(obj.trainer)


# ============================================================
# 工装夹具序列化器
# ============================================================


class FixtureCategorySerializer(serializers.ModelSerializer):
    """工装分类序列化器"""

    parent_name = serializers.CharField(source='parent.name', read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = FixtureCategory
        fields = '__all__'

    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()


class FixtureCategoryTreeSerializer(serializers.ModelSerializer):
    """工装分类树形序列化器"""

    children = serializers.SerializerMethodField()

    class Meta:
        model = FixtureCategory
        fields = ['id', 'code', 'name', 'description', 'sort_order', 'children']

    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False).order_by('sort_order', 'code')
        return FixtureCategoryTreeSerializer(children, many=True).data


class FixtureSerializer(serializers.ModelSerializer):
    """工装夹具序列化器"""

    category_name = serializers.CharField(source='category.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    custodian_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    ownership_display = serializers.CharField(source='get_ownership_display', read_only=True)
    is_calibration_due = serializers.BooleanField(read_only=True)

    class Meta:
        model = Fixture
        fields = '__all__'
        read_only_fields = ['fixture_no', 'usage_count']

    def get_custodian_name(self, obj):
        return _display_name(obj.custodian)


class FixtureListSerializer(serializers.ModelSerializer):
    """工装夹具列表序列化器（简化）"""

    category_name = serializers.CharField(source='category.name', read_only=True)
    custodian_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_calibration_due = serializers.BooleanField(read_only=True)

    class Meta:
        model = Fixture
        fields = [
            'id',
            'fixture_no',
            'name',
            'model',
            'category',
            'category_name',
            'status',
            'status_display',
            'location',
            'custodian',
            'custodian_name',
            'needs_calibration',
            'next_calibration',
            'is_calibration_due',
            'usage_count',
            'max_usage',
        ]

    def get_custodian_name(self, obj):
        return _display_name(obj.custodian)


class FixtureUsageRecordSerializer(serializers.ModelSerializer):
    """工装使用记录序列化器"""

    fixture_name = serializers.CharField(source='fixture.name', read_only=True)
    fixture_no = serializers.CharField(source='fixture.fixture_no', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    used_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FixtureUsageRecord
        fields = '__all__'

    def get_used_by_name(self, obj):
        return _display_name(obj.used_by)


class FixtureCalibrationSerializer(serializers.ModelSerializer):
    """工装校验记录序列化器"""

    fixture_name = serializers.CharField(source='fixture.name', read_only=True)
    fixture_no = serializers.CharField(source='fixture.fixture_no', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)

    class Meta:
        model = FixtureCalibration
        fields = '__all__'


class FixtureMaintenanceSerializer(serializers.ModelSerializer):
    """工装维护记录序列化器"""

    fixture_name = serializers.CharField(source='fixture.name', read_only=True)
    fixture_no = serializers.CharField(source='fixture.fixture_no', read_only=True)
    performed_by_name = serializers.SerializerMethodField()
    maintenance_type_display = serializers.CharField(source='get_maintenance_type_display', read_only=True)

    class Meta:
        model = FixtureMaintenance
        fields = '__all__'
        read_only_fields = ['total_cost']

    def get_performed_by_name(self, obj):
        return _display_name(obj.performed_by)
