"""
数据字典管理
Data Dictionary Management
用于管理系统中的各类下拉选项、枚举值等
"""

from django.db import models
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class DictType(BaseModel):
    """
    字典类型
    """

    code = models.CharField(max_length=50, unique=True, verbose_name='类型编码')
    name = models.CharField(max_length=100, verbose_name='类型名称')
    description = models.TextField(blank=True, verbose_name='描述')
    is_system = models.BooleanField(default=False, verbose_name='系统内置')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'core_dict_type'
        verbose_name = '字典类型'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class DictItem(BaseModel):
    """
    字典项
    """

    dict_type = models.ForeignKey(DictType, on_delete=models.CASCADE, related_name='items', verbose_name='字典类型')
    value = models.CharField(max_length=100, verbose_name='字典值')
    label = models.CharField(max_length=200, verbose_name='显示标签')
    description = models.TextField(blank=True, verbose_name='描述')
    extra_data = models.JSONField(default=dict, blank=True, verbose_name='扩展数据')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_default = models.BooleanField(default=False, verbose_name='默认项')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    color = models.CharField(max_length=20, blank=True, verbose_name='颜色标识')

    class Meta:
        db_table = 'core_dict_item'
        verbose_name = '字典项'
        verbose_name_plural = verbose_name
        ordering = ['dict_type', 'sort_order', 'value']
        unique_together = ['dict_type', 'value']

    def __str__(self):
        return f'{self.dict_type.code}.{self.value} - {self.label}'


# =====================
# Serializers
# =====================


class DictItemSerializer(serializers.ModelSerializer):
    dict_type_code = serializers.CharField(source='dict_type.code', read_only=True)
    dict_type_name = serializers.CharField(source='dict_type.name', read_only=True)

    class Meta:
        model = DictItem
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class DictItemSimpleSerializer(serializers.ModelSerializer):
    """简化版字典项序列化器，用于下拉选项"""

    class Meta:
        model = DictItem
        fields = ['id', 'value', 'label', 'color', 'extra_data', 'is_default']


class DictTypeSerializer(serializers.ModelSerializer):
    items = DictItemSimpleSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = DictType
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_items_count(self, obj):
        return obj.items.filter(is_deleted=False, is_enabled=True).count()


class DictTypeListSerializer(serializers.ModelSerializer):
    """列表序列化器"""

    items_count = serializers.SerializerMethodField()

    class Meta:
        model = DictType
        fields = ['id', 'code', 'name', 'description', 'is_system', 'sort_order', 'items_count']

    def get_items_count(self, obj):
        return obj.items.filter(is_deleted=False, is_enabled=True).count()


# =====================
# ViewSets
# =====================


class DictTypeViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    字典类型管理
    """

    queryset = DictType.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['code', 'is_system']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['sort_order', 'code', 'name']

    def get_serializer_class(self):
        if self.action == 'list':
            return DictTypeListSerializer
        return DictTypeSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_system:
            return Response({'error': '系统内置字典类型不能删除'}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def by_code(self, request):
        """根据编码获取字典类型及其项"""
        code = request.query_params.get('code')
        if not code:
            return Response({'error': '请提供字典类型编码'}, status=400)

        try:
            dict_type = DictType.objects.get(code=code, is_deleted=False)
        except DictType.DoesNotExist:
            return Response({'error': '字典类型不存在'}, status=404)

        items = dict_type.items.filter(is_deleted=False, is_enabled=True).order_by('sort_order', 'value')

        return Response(
            {'code': dict_type.code, 'name': dict_type.name, 'items': DictItemSimpleSerializer(items, many=True).data}
        )

    @action(detail=False, methods=['get'])
    def options(self, request):
        """批量获取多个字典类型的选项"""
        codes = request.query_params.get('codes', '').split(',')
        codes = [c.strip() for c in codes if c.strip()]

        if not codes:
            return Response({'error': '请提供字典类型编码列表'}, status=400)

        result = {}
        for code in codes:
            try:
                dict_type = DictType.objects.get(code=code, is_deleted=False)
                items = dict_type.items.filter(is_deleted=False, is_enabled=True).order_by('sort_order', 'value')
                result[code] = DictItemSimpleSerializer(items, many=True).data
            except DictType.DoesNotExist:
                result[code] = []

        return Response(result)

    @action(detail=False, methods=['post'])
    def init_system_dicts(self, request):
        """初始化系统内置字典"""
        if not request.user.is_superuser:
            return Response({'error': '仅超级管理员可执行此操作'}, status=403)

        system_dicts = [
            {
                'code': 'PROJECT_STATUS',
                'name': '项目状态',
                'items': [
                    {'value': 'DRAFT', 'label': '草稿', 'color': '#909399'},
                    {'value': 'PLANNING', 'label': '规划中', 'color': '#409EFF'},
                    {'value': 'IN_PROGRESS', 'label': '进行中', 'color': '#67C23A'},
                    {'value': 'ON_HOLD', 'label': '暂停', 'color': '#E6A23C'},
                    {'value': 'COMPLETED', 'label': '已完成', 'color': '#67C23A'},
                    {'value': 'CANCELLED', 'label': '已取消', 'color': '#F56C6C'},
                ],
            },
            {
                'code': 'ORDER_STATUS',
                'name': '订单状态',
                'items': [
                    {'value': 'DRAFT', 'label': '草稿', 'color': '#909399'},
                    {'value': 'SUBMITTED', 'label': '已提交', 'color': '#409EFF'},
                    {'value': 'APPROVED', 'label': '已审批', 'color': '#67C23A'},
                    {'value': 'IN_PROGRESS', 'label': '执行中', 'color': '#67C23A'},
                    {'value': 'COMPLETED', 'label': '已完成', 'color': '#67C23A'},
                    {'value': 'CANCELLED', 'label': '已取消', 'color': '#F56C6C'},
                ],
            },
            {
                'code': 'PAYMENT_TERMS',
                'name': '付款条款',
                'items': [
                    {'value': 'PREPAID', 'label': '预付款'},
                    {'value': 'COD', 'label': '货到付款'},
                    {'value': 'NET30', 'label': '月结30天'},
                    {'value': 'NET60', 'label': '月结60天'},
                    {'value': 'NET90', 'label': '月结90天'},
                    {'value': 'MILESTONE', 'label': '分期付款'},
                ],
            },
            {
                'code': 'PRIORITY',
                'name': '优先级',
                'items': [
                    {'value': 'LOW', 'label': '低', 'color': '#909399'},
                    {'value': 'MEDIUM', 'label': '中', 'color': '#409EFF', 'is_default': True},
                    {'value': 'HIGH', 'label': '高', 'color': '#E6A23C'},
                    {'value': 'URGENT', 'label': '紧急', 'color': '#F56C6C'},
                ],
            },
            {
                'code': 'CUSTOMER_INDUSTRY',
                'name': '客户行业',
                'items': [
                    {'value': 'NEW_ENERGY', 'label': '新能源'},
                    {'value': 'ELECTRONICS', 'label': '电子电器'},
                    {'value': 'AUTOMOTIVE', 'label': '汽车'},
                    {'value': 'MEDICAL', 'label': '医疗器械'},
                    {'value': 'AEROSPACE', 'label': '航空航天'},
                    {'value': 'SEMICONDUCTOR', 'label': '半导体'},
                    {'value': 'OTHER', 'label': '其他'},
                ],
            },
            {
                'code': 'SUPPLIER_LEVEL',
                'name': '供应商等级',
                'items': [
                    {'value': 'A', 'label': 'A级供应商', 'color': '#67C23A'},
                    {'value': 'B', 'label': 'B级供应商', 'color': '#409EFF'},
                    {'value': 'C', 'label': 'C级供应商', 'color': '#E6A23C'},
                    {'value': 'D', 'label': 'D级供应商', 'color': '#F56C6C'},
                ],
            },
            {
                'code': 'UNIT',
                'name': '计量单位',
                'items': [
                    {'value': 'PCS', 'label': '个'},
                    {'value': 'SET', 'label': '套'},
                    {'value': 'M', 'label': '米'},
                    {'value': 'KG', 'label': '千克'},
                    {'value': 'L', 'label': '升'},
                    {'value': 'BOX', 'label': '箱'},
                    {'value': 'ROLL', 'label': '卷'},
                ],
            },
        ]

        created_count = 0
        for dict_data in system_dicts:
            dict_type, created = DictType.objects.update_or_create(
                code=dict_data['code'],
                defaults={'name': dict_data['name'], 'is_system': True, 'created_by': request.user},
            )
            if created:
                created_count += 1

            for idx, item_data in enumerate(dict_data.get('items', [])):
                DictItem.objects.update_or_create(
                    dict_type=dict_type,
                    value=item_data['value'],
                    defaults={
                        'label': item_data['label'],
                        'color': item_data.get('color', ''),
                        'is_default': item_data.get('is_default', False),
                        'sort_order': idx,
                        'created_by': request.user,
                    },
                )

        return Response({'message': f'初始化完成，创建了 {created_count} 个新字典类型'})


class DictItemViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    字典项管理
    """

    queryset = DictItem.objects.filter(is_deleted=False)
    serializer_class = DictItemSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['dict_type', 'is_enabled', 'is_default']
    search_fields = ['value', 'label', 'description']
    ordering_fields = ['sort_order', 'value', 'label']

    def get_queryset(self):
        queryset = super().get_queryset()
        dict_type_code = self.request.query_params.get('dict_type_code')
        if dict_type_code:
            queryset = queryset.filter(dict_type__code=dict_type_code)
        return queryset

    @action(detail=True, methods=['post'])
    def toggle_enable(self, request, pk=None):
        """切换启用状态"""
        item = self.get_object()
        item.is_enabled = not item.is_enabled
        item.save()
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """设为默认项"""
        item = self.get_object()
        # 取消同类型下其他默认项
        DictItem.objects.filter(dict_type=item.dict_type, is_default=True).update(is_default=False)

        item.is_default = True
        item.save()
        return Response(self.get_serializer(item).data)
