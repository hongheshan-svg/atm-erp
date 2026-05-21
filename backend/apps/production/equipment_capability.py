"""
Equipment Capability Matrix with Process Types and Precision Grades
"""

from decimal import Decimal

from django.db import models
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class EquipmentCapability(BaseModel):
    PROCESS_TYPE_CHOICES = [
        ('milling', '铣削'),
        ('turning', '车削'),
        ('grinding', '磨削'),
        ('drilling', '钻孔'),
        ('boring', '镗孔'),
        ('edm', '电火花'),
        ('wire_cutting', '线切割'),
        ('laser_cutting', '激光切割'),
        ('welding', '焊接'),
        ('bending', '折弯'),
        ('stamping', '冲压'),
        ('casting', '铸造'),
        ('forging', '锻造'),
        ('heat_treatment', '热处理'),
        ('surface_treatment', '表面处理'),
        ('assembly', '装配'),
    ]
    PRECISION_GRADE_CHOICES = [
        ('standard', '标准'),
        ('precision', '精密'),
        ('high_precision', '高精度'),
        ('ultra_precision', '超精密'),
    ]

    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='capabilities',
        verbose_name='设备',
    )
    process_type = models.CharField(max_length=30, choices=PROCESS_TYPE_CHOICES, verbose_name='工艺类型')
    precision_grade = models.CharField(
        max_length=20, choices=PRECISION_GRADE_CHOICES, default='standard', verbose_name='精度等级'
    )
    max_length = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='最大长度(mm)'
    )
    max_width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='最大宽度(mm)')
    max_height = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='最大高度(mm)'
    )
    max_weight = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='最大重量(kg)'
    )
    positioning_accuracy = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True, verbose_name='定位精度(mm)'
    )
    repeat_accuracy = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True, verbose_name='重复精度(mm)'
    )
    efficiency_factor = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('0.85'), verbose_name='效率系数'
    )
    surface_finish_ra = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True, verbose_name='表面粗糙度Ra'
    )
    spindle_speed_range = models.CharField(max_length=100, null=True, blank=True, verbose_name='主轴转速范围')
    feed_rate_range = models.CharField(max_length=100, null=True, blank=True, verbose_name='进给速度范围')

    class Meta:
        db_table = 'production_equipment_capability'
        ordering = ['equipment', 'process_type']
        verbose_name = '设备能力'
        verbose_name_plural = '设备能力'

    def __str__(self):
        return f'{self.equipment} - {self.get_process_type_display()}'


# ─── Serializers ────────────────────────────────────────────────


class EquipmentCapabilitySerializer(serializers.ModelSerializer):
    process_type_display = serializers.CharField(source='get_process_type_display', read_only=True)
    precision_grade_display = serializers.CharField(source='get_precision_grade_display', read_only=True)

    class Meta:
        model = EquipmentCapability
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# ─── ViewSets ───────────────────────────────────────────────────


class EquipmentCapabilityViewSet(PermissionMixin, viewsets.ModelViewSet):
    permission_module = 'production'
    permission_resource = 'equipment_capability'
    serializer_class = EquipmentCapabilitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = EquipmentCapability.objects.filter(is_deleted=False)
        equipment_id = self.request.query_params.get('equipment_id')
        if equipment_id:
            qs = qs.filter(equipment_id=equipment_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def by_process(self, request):
        process_type = request.query_params.get('process_type')
        if not process_type:
            return Response({'error': '请指定工艺类型'}, status=status.HTTP_400_BAD_REQUEST)
        qs = self.get_queryset().filter(process_type=process_type)
        return Response(EquipmentCapabilitySerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def matrix(self, request):
        qs = self.get_queryset().values('equipment__id', 'process_type', 'precision_grade').distinct()
        matrix_data = {}
        for item in qs:
            eq_id = item['equipment__id']
            if eq_id not in matrix_data:
                matrix_data[eq_id] = []
            matrix_data[eq_id].append(
                {
                    'process_type': item['process_type'],
                    'precision_grade': item['precision_grade'],
                }
            )
        return Response(matrix_data)
