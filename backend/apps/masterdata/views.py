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
        """Import items from Excel file with all fields."""
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': '请上传文件'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            df = pd.read_excel(file)
            
            # Helper function to find column by keywords
            def find_column(df, keywords):
                for col in df.columns:
                    for keyword in keywords:
                        if keyword in str(col):
                            return col
                return None
            
            # Find required columns
            sku_col = find_column(df, ['物料编码', 'SKU', 'sku', '编码'])
            name_col = find_column(df, ['物料名称', '名称', 'name'])
            
            if not sku_col or not name_col:
                return Response(
                    {'error': 'Excel文件必须包含"物料编码"和"物料名称"列'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Find optional columns
            spec_col = find_column(df, ['规格型号', '规格', 'specification'])
            brand_col = find_column(df, ['品牌', 'brand'])
            model_col = find_column(df, ['型号', 'model'])
            version_brand_col = find_column(df, ['版本/品牌'])
            unit_col = find_column(df, ['单位', 'unit'])
            type_col = find_column(df, ['物料类型', '类型', 'item_type'])
            purchase_col = find_column(df, ['采购单价', '采购价', 'purchase'])
            sale_col = find_column(df, ['销售单价', '销售价', 'sale'])
            cost_col = find_column(df, ['标准成本', 'standard_cost'])
            tax_col = find_column(df, ['税率', 'tax'])
            mfr_col = find_column(df, ['生产厂家', '厂家', 'manufacturer'])
            origin_col = find_column(df, ['产地', 'origin'])
            safety_col = find_column(df, ['安全库存', 'safety'])
            lead_col = find_column(df, ['采购周期', 'lead_time'])
            min_col = find_column(df, ['最小库存', 'min_stock'])
            max_col = find_column(df, ['最大库存', 'max_stock'])
            barcode_col = find_column(df, ['条形码', 'barcode'])
            desc_col = find_column(df, ['描述', 'description'])
            
            created_count = 0
            updated_count = 0
            error_rows = []
            
            for idx, row in df.iterrows():
                row_num = idx + 2
                
                sku = str(row[sku_col]).strip() if pd.notna(row[sku_col]) else ''
                name = str(row[name_col]).strip() if pd.notna(row[name_col]) else ''
                
                if not sku or not name:
                    error_rows.append({'row': row_num, 'error': '物料编码或名称为空'})
                    continue
                
                # Skip example rows
                if sku.startswith('MAT00') or '示例' in sku or '示例' in name:
                    continue
                
                # Get optional values
                def get_val(col, default=''):
                    if col and pd.notna(row.get(col)):
                        return str(row[col]).strip()
                    return default
                
                def get_num(col, default=0):
                    if col and pd.notna(row.get(col)):
                        try:
                            return float(row[col])
                        except (ValueError, TypeError):
                            return default
                    return default
                
                def get_int(col, default=0):
                    if col and pd.notna(row.get(col)):
                        try:
                            return int(float(row[col]))
                        except (ValueError, TypeError):
                            return default
                    return default
                
                try:
                    # Parse version/brand to brand/model if provided and brand/model not provided
                    vb = get_val(version_brand_col)
                    parsed_brand = get_val(brand_col)
                    parsed_model = get_val(model_col)
                    if vb and not (parsed_brand or parsed_model):
                        if '/' in vb:
                            parts = [p.strip() for p in vb.split('/', 1)]
                            parsed_brand = parts[0]
                            parsed_model = parts[1] if len(parts) > 1 else ''
                        else:
                            parsed_brand = vb

                    # Check if item exists
                    item, created = Item.objects.update_or_create(
                        sku=sku,
                        defaults={
                            'name': name,
                            'specification': get_val(spec_col),
                            'brand': parsed_brand,
                            'model': parsed_model,
                            'unit': get_val(unit_col, 'PCS'),
                            'item_type': get_val(type_col, 'MATERIAL'),
                            'purchase_price': get_num(purchase_col),
                            'sale_price': get_num(sale_col),
                            'standard_cost': get_num(cost_col),
                            'tax_rate': get_int(tax_col, 13),
                            'manufacturer': get_val(mfr_col),
                            'origin_country': get_val(origin_col),
                            'safety_stock': get_num(safety_col),
                            'lead_time': get_int(lead_col),
                            'min_stock': get_num(min_col),
                            'max_stock': get_num(max_col),
                            'barcode': get_val(barcode_col),
                            'description': get_val(desc_col),
                            'updated_by': request.user,
                        }
                    )
                    # created_by 只在创建时赋值，避免把历史 created_by 覆盖为 None
                    if created and hasattr(item, 'created_by') and item.created_by_id is None:
                        item.created_by = request.user
                        item.save(update_fields=['created_by'])
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                except Exception as e:
                    error_rows.append({'row': row_num, 'error': str(e)})
            
            return Response({
                'message': f'导入完成：新增 {created_count} 条，更新 {updated_count} 条',
                'created': created_count,
                'updated': updated_count,
                'errors': error_rows
            })
        
        except Exception as e:
            return Response(
                {'error': f'导入失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """Export items to Excel file with all fields matching BOM template."""
        items = self.filter_queryset(self.get_queryset())
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            worksheet = workbook.add_worksheet('物料主数据')
            
            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            data_format = workbook.add_format({
                'border': 1,
                'align': 'left',
                'valign': 'vcenter'
            })
            money_format = workbook.add_format({
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '¥#,##0.00'
            })
            number_format = workbook.add_format({
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '#,##0.00'
            })
            
            # Column headers matching BOM template
            headers = [
                ('序号', 6),
                ('物料编码', 12),
                ('物料名称', 20),
                ('规格型号', 15),
                ('版本/品牌', 12),
                ('单位', 8),
                ('物料类型', 10),
                ('采购单价', 10),
                ('销售单价', 10),
                ('标准成本', 10),
                ('税率(%)', 8),
                ('生产厂家', 15),
                ('产地', 10),
                ('安全库存', 10),
                ('采购周期(天)', 10),
                ('最小库存', 10),
                ('最大库存', 10),
                ('重量(kg)', 10),
                ('体积(m³)', 10),
                ('保质期(天)', 10),
                ('条形码', 15),
                ('状态', 8),
                ('描述', 25),
            ]
            
            # Write headers
            for col, (header, width) in enumerate(headers):
                worksheet.write(0, col, header, header_format)
                worksheet.set_column(col, col, width)
            
            # Write data
            for row_idx, item in enumerate(items, 1):
                version_brand = f"{item.brand or ''}/{item.model or ''}" if item.brand or item.model else ''
                version_brand = version_brand.strip('/')
                
                worksheet.write(row_idx, 0, row_idx, data_format)
                worksheet.write(row_idx, 1, item.sku, data_format)
                worksheet.write(row_idx, 2, item.name, data_format)
                worksheet.write(row_idx, 3, item.specification or '', data_format)
                worksheet.write(row_idx, 4, version_brand, data_format)
                worksheet.write(row_idx, 5, item.get_unit_display(), data_format)
                worksheet.write(row_idx, 6, item.get_item_type_display(), data_format)
                worksheet.write(row_idx, 7, float(item.purchase_price), money_format)
                worksheet.write(row_idx, 8, float(item.sale_price), money_format)
                worksheet.write(row_idx, 9, float(item.standard_cost), money_format)
                worksheet.write(row_idx, 10, item.tax_rate, data_format)
                worksheet.write(row_idx, 11, item.manufacturer or '', data_format)
                worksheet.write(row_idx, 12, item.origin_country or '', data_format)
                worksheet.write(row_idx, 13, float(item.safety_stock), number_format)
                worksheet.write(row_idx, 14, item.lead_time, data_format)
                worksheet.write(row_idx, 15, float(item.min_stock), number_format)
                worksheet.write(row_idx, 16, float(item.max_stock), number_format)
                worksheet.write(row_idx, 17, float(item.weight), number_format)
                worksheet.write(row_idx, 18, float(item.volume), number_format)
                worksheet.write(row_idx, 19, item.shelf_life, data_format)
                worksheet.write(row_idx, 20, item.barcode or '', data_format)
                worksheet.write(row_idx, 21, '启用' if item.is_active else '禁用', data_format)
                worksheet.write(row_idx, 22, item.description or '', data_format)
            
            worksheet.freeze_panes(1, 0)
        
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=items.xlsx'
        return response
    
    @action(detail=False, methods=['get'])
    def export_template(self, request):
        """Export item import template with headers and example data."""
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            worksheet = workbook.add_worksheet('物料导入模板')
            
            # Define formats
            required_format = workbook.add_format({
                'bold': True,
                'bg_color': '#C00000',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True
            })
            optional_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True
            })
            example_format = workbook.add_format({
                'bg_color': '#FFF2CC',
                'border': 1,
                'italic': True,
                'font_color': '#666666'
            })
            
            # Column headers: (name, width, required)
            headers = [
                ('物料编码*', 12, True),
                ('物料名称*', 20, True),
                ('规格型号', 15, False),
                ('版本/品牌', 12, False),
                ('单位', 8, False),
                ('物料类型', 10, False),
                ('采购单价', 10, False),
                ('销售单价', 10, False),
                ('标准成本', 10, False),
                ('税率(%)', 8, False),
                ('生产厂家', 15, False),
                ('产地', 10, False),
                ('安全库存', 10, False),
                ('采购周期(天)', 10, False),
                ('最小库存', 10, False),
                ('最大库存', 10, False),
                ('条形码', 15, False),
                ('描述', 25, False),
            ]
            
            # Write headers
            for col, (header, width, required) in enumerate(headers):
                fmt = required_format if required else optional_format
                worksheet.write(0, col, header, fmt)
                worksheet.set_column(col, col, width)
            
            # Write example data
            example_data = [
                'MAT001',
                '示例物料',
                '100x50x25mm',
                '品牌A/Model-X',
                'PCS',
                'MATERIAL',
                '100.00',
                '150.00',
                '100.00',
                '13',
                '示例厂家',
                '中国',
                '10',
                '7',
                '5',
                '100',
                '',
                '示例物料，请删除',
            ]
            for col, value in enumerate(example_data):
                worksheet.write(1, col, value, example_format)
            
            worksheet.set_row(0, 25)
            worksheet.freeze_panes(1, 0)
            
            # Help sheet
            help_sheet = workbook.add_worksheet('填写说明')
            title_format = workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#4472C4'})
            section_format = workbook.add_format({'bold': True, 'font_size': 12, 'font_color': '#C00000'})
            
            help_content = [
                ('物料导入模板填写说明', title_format),
                ('', None),
                ('【必填字段】', section_format),
                ('  • 物料编码*：唯一标识，不可重复', None),
                ('  • 物料名称*：物料的名称', None),
                ('', None),
                ('【选填字段】', section_format),
                ('  • 规格型号：物料规格描述', None),
                ('  • 品牌/型号：品牌和产品型号', None),
                ('  • 单位：PCS/KG/M/M2/M3/SET/BOX/PACK/HOUR', None),
                ('  • 物料类型：MATERIAL(原材料)/PRODUCT(产成品)/SEMI(半成品)/SERVICE(服务)', None),
                ('  • 各种价格和库存参数', None),
                ('', None),
                ('【注意事项】', section_format),
                ('  • 编码重复时将更新现有物料', None),
                ('  • 删除示例行后再导入', None),
            ]
            
            help_sheet.set_column(0, 0, 60)
            for row, (text, fmt) in enumerate(help_content):
                if fmt:
                    help_sheet.write(row, 0, text, fmt)
                else:
                    help_sheet.write(row, 0, text)
        
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=item_import_template.xlsx'
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

