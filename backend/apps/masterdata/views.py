"""
Views for masterdata app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin, DataScopeMixin
from .models import ItemCategory, Item, Customer, Supplier, Warehouse, WarehouseLocation
from .serializers import (
    ItemCategorySerializer, ItemSerializer, CustomerSerializer,
    SupplierSerializer, WarehouseSerializer, WarehouseLocationSerializer,
    WarehouseLocationTreeSerializer
)


class ItemCategoryViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for ItemCategory management.
    """
    queryset = ItemCategory.objects.all()
    serializer_class = ItemCategorySerializer
    filterset_fields = ['parent', 'is_deleted']
    search_fields = ['code', 'name']
    ordering_fields = ['sort_order', 'code', 'created_at']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get category tree structure."""
        categories = self.get_queryset().filter(is_deleted=False)
        
        def build_tree(parent_id=None):
            result = []
            items = categories.filter(parent_id=parent_id)
            for item in items:
                node = ItemCategorySerializer(item).data
                node['children'] = build_tree(item.id)
                result.append(node)
            return result
        
        tree_data = build_tree()
        return Response(tree_data)


class ItemViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for Item management.
    NOTE: 物料是主数据，所有用户都可以查看，不应用数据范围限制
    """
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    filterset_fields = ['category', 'item_type', 'is_active', 'is_deleted']
    search_fields = ['sku', 'name', 'specification', 'barcode']
    ordering_fields = ['sku', 'created_at', 'standard_cost']
    
    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """Import items from Excel file."""
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': '请上传文件'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            df = pd.read_excel(file)
            required_columns = ['sku', 'name', 'unit']
            
            if not all(col in df.columns for col in required_columns):
                return Response(
                    {'error': f'Excel文件必须包含以下列: {", ".join(required_columns)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            created_count = 0
            error_rows = []
            
            for idx, row in df.iterrows():
                try:
                    Item.objects.create(
                        sku=row['sku'],
                        name=row['name'],
                        specification=row.get('specification', ''),
                        unit=row.get('unit', 'PCS'),
                        standard_cost=row.get('standard_cost', 0),
                        created_by=request.user
                    )
                    created_count += 1
                except Exception as e:
                    error_rows.append({'row': idx + 2, 'error': str(e)})
            
            return Response({
                'message': f'成功导入 {created_count} 条记录',
                'errors': error_rows
            })
        
        except Exception as e:
            return Response(
                {'error': f'导入失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """Export items to Excel file."""
        items = self.filter_queryset(self.get_queryset())
        
        data = []
        for item in items:
            data.append({
                'SKU': item.sku,
                '名称': item.name,
                '规格': item.specification,
                '类别': item.category.name if item.category else '',
                '类型': item.get_item_type_display(),
                '单位': item.get_unit_display(),
                '标准成本': float(item.standard_cost),
                '最小库存': float(item.min_stock),
                '最大库存': float(item.max_stock),
                '条形码': item.barcode,
                '状态': '激活' if item.is_active else '停用',
            })
        
        df = pd.DataFrame(data)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='物料')
        
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=items.xlsx'
        return response
    
    @action(detail=True, methods=['get'])
    def generate_barcode(self, request, pk=None):
        """Generate barcode for item"""
        item = self.get_object()
        
        try:
            from apps.inventory.barcode_service import BarcodeService
            return BarcodeService.generate_item_barcode_response(item)
        except Exception as e:
            return Response(
                {'error': f'Barcode generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def generate_qrcode(self, request, pk=None):
        """Generate QR code for item"""
        item = self.get_object()
        
        try:
            from apps.inventory.barcode_service import BarcodeService
            return BarcodeService.generate_item_qrcode_response(item)
        except Exception as e:
            return Response(
                {'error': f'QR code generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomerViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for Customer management.
    NOTE: 客户是主数据，所有用户都可以查看，不应用数据范围限制
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filterset_fields = ['status', 'is_deleted']
    search_fields = ['code', 'name', 'contact_person', 'phone']
    ordering_fields = ['code', 'created_at']


class SupplierViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for Supplier management.
    NOTE: 供应商是主数据，所有用户都可以查看，不应用数据范围限制
    """
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filterset_fields = ['status', 'is_deleted']
    search_fields = ['code', 'name', 'contact_person', 'phone']
    ordering_fields = ['code', 'created_at']


class WarehouseViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for Warehouse management.
    """
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    filterset_fields = ['warehouse_type', 'is_active', 'is_deleted']
    search_fields = ['code', 'name', 'address']
    ordering_fields = ['code', 'created_at']
    
    @action(detail=True, methods=['get'])
    def locations(self, request, pk=None):
        """Get all locations for a warehouse."""
        warehouse = self.get_object()
        locations = warehouse.locations.filter(is_deleted=False).order_by('sort_order', 'code')
        serializer = WarehouseLocationSerializer(locations, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def location_tree(self, request, pk=None):
        """Get location tree for a warehouse."""
        warehouse = self.get_object()
        root_locations = warehouse.locations.filter(
            parent__isnull=True,
            is_deleted=False
        ).order_by('sort_order', 'code')
        serializer = WarehouseLocationTreeSerializer(root_locations, many=True)
        return Response(serializer.data)


class WarehouseLocationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for WarehouseLocation management.
    """
    queryset = WarehouseLocation.objects.all()
    serializer_class = WarehouseLocationSerializer
    filterset_fields = ['warehouse', 'parent', 'location_type', 'is_active', 'is_deleted']
    search_fields = ['code', 'name', 'full_path']
    ordering_fields = ['warehouse', 'sort_order', 'code', 'created_at']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get location tree for all warehouses."""
        warehouse_id = request.query_params.get('warehouse')
        
        if warehouse_id:
            root_locations = self.get_queryset().filter(
                warehouse_id=warehouse_id,
                parent__isnull=True,
                is_deleted=False
            ).order_by('sort_order', 'code')
        else:
            root_locations = self.get_queryset().filter(
                parent__isnull=True,
                is_deleted=False
            ).order_by('warehouse', 'sort_order', 'code')
        
        serializer = WarehouseLocationTreeSerializer(root_locations, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def children(self, request, pk=None):
        """Get direct children of a location."""
        location = self.get_object()
        children = location.children.filter(is_deleted=False).order_by('sort_order', 'code')
        serializer = WarehouseLocationSerializer(children, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def path(self, request, pk=None):
        """Get the full path from root to this location."""
        location = self.get_object()
        path = [location]
        current = location
        
        while current.parent:
            current = current.parent
            path.insert(0, current)
        
        serializer = WarehouseLocationSerializer(path, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create locations for a warehouse."""
        warehouse_id = request.data.get('warehouse')
        locations_data = request.data.get('locations', [])
        
        if not warehouse_id:
            return Response(
                {'error': '请选择仓库'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id)
        except Warehouse.DoesNotExist:
            return Response(
                {'error': '仓库不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created = []
        errors = []
        
        for loc_data in locations_data:
            try:
                location = WarehouseLocation.objects.create(
                    warehouse=warehouse,
                    code=loc_data.get('code'),
                    name=loc_data.get('name'),
                    location_type=loc_data.get('location_type', 'BIN'),
                    parent_id=loc_data.get('parent'),
                    created_by=request.user
                )
                created.append(WarehouseLocationSerializer(location).data)
            except Exception as e:
                errors.append({
                    'code': loc_data.get('code'),
                    'error': str(e)
                })
        
        return Response({
            'created': len(created),
            'errors': errors,
            'locations': created
        })

