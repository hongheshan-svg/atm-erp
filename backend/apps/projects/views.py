"""
Views for projects app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.db.models import Sum, F
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin, DataScopeMixin
from apps.masterdata.models import Item
from .models import (
    Project, ProjectMember, ProjectTask, ProjectBOM, TimeLog, 
    ECN, ECNItem, ECNApproval,
    AfterSalesOrder, ServiceRecord, SparePartUsage
)
from .serializers import (
    ProjectSerializer, ProjectMemberSerializer,
    ProjectTaskSerializer, ProjectBOMSerializer, TimeLogSerializer,
    ECNSerializer, ECNWriteSerializer, ECNItemSerializer, ECNApprovalSerializer,
    AfterSalesOrderSerializer, AfterSalesOrderListSerializer,
    ServiceRecordSerializer, SparePartUsageSerializer
)


class ProjectViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
    """
    ViewSet for Project management.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filterset_fields = ['customer', 'manager', 'status', 'is_deleted']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'start_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """Change project status."""
        project = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(Project.STATUS_CHOICES):
            return Response(
                {'error': '无效的状态'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        project.status = new_status
        project.save()
        
        return Response(ProjectSerializer(project).data)
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get project summary with costs and progress."""
        project = self.get_object()
        
        # Calculate task progress
        tasks = project.tasks.filter(is_deleted=False)
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status='COMPLETED').count()
        task_progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Get member stats
        members = project.members.filter(is_deleted=False, is_active=True)
        total_allocated_hours = members.aggregate(Sum('allocated_hours'))['allocated_hours__sum'] or 0
        total_actual_hours = members.aggregate(Sum('actual_hours'))['actual_hours__sum'] or 0
        
        # Get BOM stats
        bom_items = project.bom_items.filter(is_deleted=False)
        bom_count = bom_items.count()
        
        return Response({
            'project': ProjectSerializer(project).data,
            'task_stats': {
                'total': total_tasks,
                'completed': completed_tasks,
                'progress': round(task_progress, 2),
            },
            'member_stats': {
                'count': members.count(),
                'allocated_hours': float(total_allocated_hours),
                'actual_hours': float(total_actual_hours),
            },
            'bom_stats': {
                'count': bom_count,
            },
        })


class ProjectMemberViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for ProjectMember management.
    """
    queryset = ProjectMember.objects.all()
    serializer_class = ProjectMemberSerializer
    filterset_fields = ['project', 'user', 'is_active', 'is_deleted']
    search_fields = ['user__username', 'role']
    ordering_fields = ['created_at']
    
    @action(detail=True, methods=['post'])
    def update_hours(self, request, pk=None):
        """Update actual hours for a member."""
        member = self.get_object()
        actual_hours = request.data.get('actual_hours')
        
        if actual_hours is None:
            return Response(
                {'error': '请提供actual_hours'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        member.actual_hours = actual_hours
        member.save()
        
        return Response(ProjectMemberSerializer(member).data)


class ProjectTaskViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for ProjectTask management.
    """
    queryset = ProjectTask.objects.all()
    serializer_class = ProjectTaskSerializer
    filterset_fields = ['project', 'assignee', 'status', 'parent', 'is_deleted']
    search_fields = ['code', 'name']
    ordering_fields = ['project', 'sort_order', 'created_at']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get tasks as tree structure for a project."""
        project_id = request.query_params.get('project')
        if not project_id:
            return Response(
                {'error': '请提供project参数'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tasks = self.get_queryset().filter(
            project_id=project_id,
            is_deleted=False
        )
        
        def build_tree(parent_id=None):
            result = []
            items = tasks.filter(parent_id=parent_id)
            for item in items:
                node = ProjectTaskSerializer(item).data
                node['children'] = build_tree(item.id)
                result.append(node)
            return result
        
        tree_data = build_tree()
        return Response(tree_data)
    
    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """Update task progress."""
        task = self.get_object()
        progress = request.data.get('progress_percent')
        actual_hours = request.data.get('actual_hours')
        
        if progress is not None:
            task.progress_percent = progress
            if progress >= 100:
                task.status = 'COMPLETED'
            elif progress > 0:
                task.status = 'IN_PROGRESS'
        
        if actual_hours is not None:
            task.actual_hours = actual_hours
        
        task.save()
        
        return Response(ProjectTaskSerializer(task).data)


class ProjectBOMViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for ProjectBOM management.
    """
    queryset = ProjectBOM.objects.all()
    serializer_class = ProjectBOMSerializer
    filterset_fields = ['project', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']
    ordering_fields = ['created_at']
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    def create(self, request, *args, **kwargs):
        """
        创建BOM时，如果存在已软删除的相同记录，则恢复它而不是报错
        """
        project_id = request.data.get('project')
        item_id = request.data.get('item')
        
        if project_id and item_id:
            # 查找是否有已删除的相同记录
            existing_bom = ProjectBOM.objects.filter(
                project_id=project_id, 
                item_id=item_id, 
                is_deleted=True
            ).first()
            
            if existing_bom:
                # 恢复软删除的记录并更新数据
                existing_bom.is_deleted = False
                existing_bom.planned_qty = request.data.get('planned_qty', existing_bom.planned_qty)
                existing_bom.estimated_cost = request.data.get('estimated_cost', existing_bom.estimated_cost)
                existing_bom.notes = request.data.get('notes', existing_bom.notes)
                existing_bom.updated_by = request.user
                existing_bom.save()
                
                serializer = self.get_serializer(existing_bom)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return super().create(request, *args, **kwargs)
    
    @action(detail=False, methods=['post'])
    def batch_create(self, request):
        """Batch create BOM items for a project."""
        project_id = request.data.get('project')
        items_data = request.data.get('items', [])
        
        if not project_id or not items_data:
            return Response(
                {'error': '请提供project和items'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_items = []
        for item_data in items_data:
            serializer = self.get_serializer(data={
                'project': project_id,
                **item_data
            })
            serializer.is_valid(raise_exception=True)
            serializer.save(created_by=request.user)
            created_items.append(serializer.data)
        
        return Response(created_items, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """Export BOM items to Excel file with formatted headers."""
        project_id = request.query_params.get('project')
        
        if not project_id:
            return Response(
                {'error': '请提供project参数'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {'error': '项目不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bom_items = self.get_queryset().filter(
            project_id=project_id,
            is_deleted=False
        ).select_related('item', 'item__category')
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            worksheet = workbook.add_worksheet('BOM清单')
            
            # Define formats
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'left',
                'valign': 'vcenter'
            })
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
            number_format = workbook.add_format({
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '#,##0'
            })
            money_format = workbook.add_format({
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '¥#,##0.00'
            })
            
            # Write title
            from datetime import datetime
            worksheet.merge_range(0, 0, 0, 9, f'项目BOM清单 - {project.name} ({project.code})', title_format)
            worksheet.write(1, 0, f'导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
            
            # Column headers
            headers = [
                ('序号', 6),
                ('物料编码', 15),
                ('物料名称', 25),
                ('规格型号', 20),
                ('单位', 8),
                ('物料类别', 15),
                ('计划数量', 12),
                ('已使用', 10),
                ('预估单价', 12),
                ('预估成本', 12),
                ('备注', 25),
            ]
            
            # Write headers (row 3)
            for col, (header, width) in enumerate(headers):
                worksheet.write(3, col, header, header_format)
                worksheet.set_column(col, col, width)
            
            # Write data
            row = 4
            total_planned = 0
            total_actual = 0
            total_cost = 0
            
            for idx, bom in enumerate(bom_items, 1):
                planned = float(bom.planned_qty)
                actual = float(bom.actual_qty)
                price = float(bom.item.standard_cost)
                cost = float(bom.estimated_cost)
                
                total_planned += planned
                total_actual += actual
                total_cost += cost
                
                worksheet.write(row, 0, idx, data_format)
                worksheet.write(row, 1, bom.item.sku, data_format)
                worksheet.write(row, 2, bom.item.name, data_format)
                worksheet.write(row, 3, bom.item.specification or '', data_format)
                worksheet.write(row, 4, bom.item.get_unit_display(), data_format)
                worksheet.write(row, 5, bom.item.category.name if bom.item.category else '', data_format)
                worksheet.write(row, 6, planned, number_format)
                worksheet.write(row, 7, actual, number_format)
                worksheet.write(row, 8, price, money_format)
                worksheet.write(row, 9, cost, money_format)
                worksheet.write(row, 10, bom.notes or '', data_format)
                row += 1
            
            # Write totals
            total_format = workbook.add_format({
                'bold': True,
                'border': 1,
                'bg_color': '#E2EFDA',
                'align': 'right'
            })
            worksheet.write(row, 5, '合计:', total_format)
            worksheet.write(row, 6, total_planned, total_format)
            worksheet.write(row, 7, total_actual, total_format)
            worksheet.write(row, 8, '', total_format)
            worksheet.write(row, 9, total_cost, workbook.add_format({
                'bold': True,
                'border': 1,
                'bg_color': '#E2EFDA',
                'align': 'right',
                'num_format': '¥#,##0.00'
            }))
            worksheet.write(row, 10, '', total_format)
            
            # Set row heights
            worksheet.set_row(0, 25)
            worksheet.set_row(3, 22)
            
            # Freeze panes
            worksheet.freeze_panes(4, 0)
        
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=BOM_{project.code}.xlsx'
        return response
    
    @action(detail=False, methods=['get'])
    def export_template(self, request):
        """Export BOM import template with headers and example data."""
        output = BytesIO()
            
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # ========== Sheet 1: BOM导入数据 ==========
            worksheet = workbook.add_worksheet('BOM导入数据')
            
            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True
            })
            required_format = workbook.add_format({
                'bold': True,
                'bg_color': '#C00000',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True
            })
            readonly_format = workbook.add_format({
                'bold': True,
                'bg_color': '#808080',
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
            readonly_example_format = workbook.add_format({
                'bg_color': '#E0E0E0',
                'border': 1,
                'italic': True,
                'font_color': '#999999'
            })
            
            # Column headers: (name, width, type: 'required'/'optional'/'readonly')
            headers = [
                ('序号', 8, 'readonly'),
                ('物料编码*', 15, 'required'),
                ('物料名称', 20, 'readonly'),
                ('规格型号', 15, 'readonly'),
                ('单位', 8, 'readonly'),
                ('计划数量*', 12, 'required'),
                ('已领用', 10, 'readonly'),
                ('剩余需求', 10, 'readonly'),
                ('预估单价', 12, 'optional'),
                ('预估成本', 12, 'readonly'),
                ('备注', 25, 'optional'),
            ]
            
            # Write headers
            for col, (header, width, htype) in enumerate(headers):
                if htype == 'required':
                    fmt = required_format
                elif htype == 'readonly':
                    fmt = readonly_format
                else:
                    fmt = header_format
                worksheet.write(0, col, header, fmt)
                worksheet.set_column(col, col, width)
            
            # Write example data (row 1)
            example_data = [
                (1, example_format),
                ('MAT001', example_format),
                ('(系统自动填充)', readonly_example_format),
                ('(系统自动填充)', readonly_example_format),
                ('(自动)', readonly_example_format),
                (100, example_format),
                ('(自动)', readonly_example_format),
                ('(自动)', readonly_example_format),
                (10.00, example_format),
                ('(自动计算)', readonly_example_format),
                ('示例，请删除', example_format),
            ]
            for col, (value, fmt) in enumerate(example_data):
                worksheet.write(1, col, value, fmt)
            
            # Write second example row
            example_data2 = [
                (2, example_format),
                ('MAT002', example_format),
                ('(系统自动填充)', readonly_example_format),
                ('(系统自动填充)', readonly_example_format),
                ('(自动)', readonly_example_format),
                (50, example_format),
                ('(自动)', readonly_example_format),
                ('(自动)', readonly_example_format),
                (25.50, example_format),
                ('(自动计算)', readonly_example_format),
                ('', example_format),
            ]
            for col, (value, fmt) in enumerate(example_data2):
                worksheet.write(2, col, value, fmt)
            
            # Set row height
            worksheet.set_row(0, 30)
            
            # Freeze header row
            worksheet.freeze_panes(1, 0)
            
            # ========== Sheet 2: 填写说明 ==========
            help_sheet = workbook.add_worksheet('填写说明')
            
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 16,
                'font_color': '#4472C4'
            })
            section_format = workbook.add_format({
                'bold': True,
                'font_size': 12,
                'font_color': '#C00000'
            })
            bold_format = workbook.add_format({'bold': True})
            
            help_content = [
                ('BOM导入模板填写说明', title_format),
                ('', None),
                ('【列说明】', section_format),
                ('', None),
                ('红色表头 = 必填字段（导入时必须填写）', bold_format),
                ('  • 物料编码*：必须与系统中物料管理的SKU完全一致', None),
                ('  • 计划数量*：正整数，表示该物料在项目中的计划使用数量', None),
                ('', None),
                ('蓝色表头 = 选填字段（可以为空）', bold_format),
                ('  • 预估单价：物料的预估采购单价，不填则使用物料的标准成本', None),
                ('  • 备注：备注信息', None),
                ('', None),
                ('灰色表头 = 系统自动填充（导入时忽略，无需填写）', bold_format),
                ('  • 序号、物料名称、规格型号、单位：根据物料编码自动获取', None),
                ('  • 已领用、剩余需求、预估成本：系统自动计算', None),
                ('', None),
                ('【导入步骤】', section_format),
                ('', None),
                ('1. 删除示例数据行（黄色背景的行）', None),
                ('2. 只填写：物料编码、计划数量、预估单价（可选）、备注（可选）', None),
                ('3. 灰色列可以留空或删除，系统会自动忽略', None),
                ('4. 保存文件并在系统中导入', None),
                ('', None),
                ('【常见错误】', section_format),
                ('', None),
                ('• 物料编码不存在：请先在"物料管理"中创建该物料', None),
                ('• 数量格式错误：请输入正整数', None),
                ('• 物料已存在：勾选"更新已存在的物料"可覆盖', None),
            ]
            
            help_sheet.set_column(0, 0, 70)
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
        response['Content-Disposition'] = 'attachment; filename=BOM_import_template.xlsx'
        return response
    
    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """Import BOM items from Excel file."""
        file = request.FILES.get('file')
        project_id = request.data.get('project')
        update_existing = request.data.get('update_existing', 'false').lower() == 'true'
        
        if not file:
            return Response(
                {'error': '请上传Excel文件'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not project_id:
            return Response(
                {'error': '请选择项目'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {'error': '项目不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            df = pd.read_excel(file)
        except Exception as e:
            return Response(
                {'error': f'Excel文件读取失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find SKU column (support multiple names)
        sku_column = None
        for col in df.columns:
            if '物料编码' in col or 'SKU' in col.upper() or '编码' in col:
                sku_column = col
                break
        
        if not sku_column:
            return Response(
                {'error': 'Excel文件必须包含"物料编码"列'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find quantity column
        qty_column = None
        for col in df.columns:
            if '计划数量' in col or '数量' in col:
                qty_column = col
                break
        
        if not qty_column:
            return Response(
                {'error': 'Excel文件必须包含"计划数量"或"数量"列'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find optional columns
        price_column = None
        for col in df.columns:
            if '预估单价' in col or '单价' in col or '成本' in col:
                price_column = col
                break
        
        notes_column = None
        for col in df.columns:
            if '备注' in col or '说明' in col:
                notes_column = col
                break
        
        created_count = 0
        updated_count = 0
        error_rows = []
        
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row number (1-based, plus header)
            
            sku = str(row[sku_column]).strip() if pd.notna(row[sku_column]) else ''
            if not sku:
                error_rows.append({'row': row_num, 'error': '物料编码为空'})
                continue
            
            # Skip example/template rows
            if sku.startswith('MAT00') or sku.startswith('(') or '示例' in sku or '自动' in sku:
                continue
            
            # Find item by SKU
            try:
                item = Item.objects.get(sku=sku)
            except Item.DoesNotExist:
                error_rows.append({'row': row_num, 'error': f'物料编码 {sku} 不存在'})
                continue
            
            # Get quantity
            try:
                planned_qty = float(row[qty_column]) if pd.notna(row[qty_column]) else 0
            except (ValueError, TypeError):
                error_rows.append({'row': row_num, 'error': '计划数量格式错误'})
                continue
            
            if planned_qty <= 0:
                error_rows.append({'row': row_num, 'error': '计划数量必须大于0'})
                continue
            
            # Get price (optional)
            unit_price = item.standard_cost
            if price_column and pd.notna(row.get(price_column)):
                try:
                    unit_price = float(row[price_column])
                except (ValueError, TypeError):
                    pass  # Use item's standard cost
            
            estimated_cost = planned_qty * float(unit_price)
            
            # Get notes (optional)
            notes = ''
            if notes_column and pd.notna(row.get(notes_column)):
                notes = str(row[notes_column])
            
            # Check if BOM item exists
            existing_bom = ProjectBOM.objects.filter(
                project=project,
                item=item,
                is_deleted=False
            ).first()
            
            if existing_bom:
                if update_existing:
                    existing_bom.planned_qty = planned_qty
                    existing_bom.estimated_cost = estimated_cost
                    if notes:
                        existing_bom.notes = notes
                    existing_bom.save()
                    updated_count += 1
                else:
                    error_rows.append({
                        'row': row_num,
                        'error': f'物料 {sku} 已存在于BOM中'
                    })
            else:
                ProjectBOM.objects.create(
                    project=project,
                    item=item,
                    planned_qty=planned_qty,
                    estimated_cost=estimated_cost,
                    notes=notes,
                    created_by=request.user
                )
                created_count += 1
        
        return Response({
            'message': f'导入完成: 新增 {created_count} 条, 更新 {updated_count} 条',
            'created': created_count,
            'updated': updated_count,
            'errors': error_rows
        })
    
    @action(detail=False, methods=['post'])
    def generate_purchase_request(self, request):
        """
        Generate purchase request from BOM items.
        PRD requirement: BOM清单推送到采购模块
        """
        from apps.purchase.models import PurchaseRequest, PurchaseRequestLine
        from django.db import transaction
        
        project_id = request.data.get('project')
        item_ids = request.data.get('item_ids', [])  # Optional: specific items
        required_date = request.data.get('required_date')
        
        if not project_id:
            return Response(
                {'error': '请提供项目ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {'error': '项目不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get BOM items to convert
        bom_queryset = ProjectBOM.objects.filter(
            project=project,
            is_deleted=False
        ).select_related('item')
        
        if item_ids:
            bom_queryset = bom_queryset.filter(item_id__in=item_ids)
        
        # Filter items that need to be purchased (planned > actual)
        bom_items = []
        for bom in bom_queryset:
            needed_qty = bom.planned_qty - bom.actual_qty
            if needed_qty > 0:
                bom_items.append({
                    'bom': bom,
                    'needed_qty': needed_qty
                })
        
        if not bom_items:
            return Response(
                {'error': '没有需要采购的物料（计划数量已满足）'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Create purchase request
            pr = PurchaseRequest.objects.create(
                project=project,
                requestor=request.user,
                required_date=required_date or project.end_date,
                notes=f'从项目 {project.code} BOM自动生成',
                created_by=request.user
            )
            
            total_amount = 0
            for item_data in bom_items:
                bom = item_data['bom']
                needed_qty = item_data['needed_qty']
                estimated_price = bom.item.standard_cost
                line_amount = needed_qty * estimated_price
                
                PurchaseRequestLine.objects.create(
                    pr=pr,
                    item=bom.item,
                    qty=needed_qty,
                    estimated_price=estimated_price,
                    project=project,
                    notes=f'BOM计划: {bom.planned_qty}, 已用: {bom.actual_qty}',
                    created_by=request.user
                )
                total_amount += line_amount
            
            pr.total_amount = total_amount
            pr.save()
        
        from apps.purchase.serializers import PurchaseRequestSerializer
        return Response({
            'message': f'已生成采购申请 {pr.request_no}，包含 {len(bom_items)} 项物料',
            'purchase_request': PurchaseRequestSerializer(pr).data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def shortage_analysis(self, request):
        """
        Analyze BOM shortage - items that need to be purchased.
        """
        from apps.inventory.models import Stock
        
        project_id = request.query_params.get('project')
        
        if not project_id:
            return Response(
                {'error': '请提供项目ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {'error': '项目不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bom_items = ProjectBOM.objects.filter(
            project=project,
            is_deleted=False
        ).select_related('item')
        
        shortage_list = []
        for bom in bom_items:
            needed_qty = bom.planned_qty - bom.actual_qty
            if needed_qty <= 0:
                continue
            
            # Get current stock
            stock = Stock.objects.filter(item=bom.item).aggregate(
                total_on_hand=Sum('qty_on_hand'),
                total_available=Sum('qty_on_hand') - Sum('qty_reserved')
            )
            
            total_on_hand = stock['total_on_hand'] or 0
            total_available = stock['total_available'] or 0
            
            shortage = needed_qty - total_available
            
            shortage_list.append({
                'item_id': bom.item.id,
                'item_sku': bom.item.sku,
                'item_name': bom.item.name,
                'unit': bom.item.get_unit_display(),
                'planned_qty': float(bom.planned_qty),
                'actual_qty': float(bom.actual_qty),
                'needed_qty': float(needed_qty),
                'stock_on_hand': float(total_on_hand),
                'stock_available': float(total_available),
                'shortage': float(max(0, shortage)),
                'can_fulfill': shortage <= 0,
                'estimated_cost': float(shortage * bom.item.standard_cost) if shortage > 0 else 0
            })
        
        # Summary
        total_shortage_cost = sum(item['estimated_cost'] for item in shortage_list)
        items_with_shortage = [item for item in shortage_list if item['shortage'] > 0]
        
        return Response({
            'project_code': project.code,
            'project_name': project.name,
            'summary': {
                'total_bom_items': len(shortage_list),
                'items_with_shortage': len(items_with_shortage),
                'total_shortage_cost': total_shortage_cost
            },
            'items': shortage_list
        })
    
    @action(detail=False, methods=['get', 'post'])
    def copy_from_project(self, request):
        """Copy BOM from another project."""
        # Support both GET and POST
        if request.method == 'POST':
            source_project_id = request.data.get('source_project')
            target_project_id = request.data.get('target_project')
        else:
            source_project_id = request.query_params.get('source_project')
            target_project_id = request.query_params.get('target_project')
        
        if not source_project_id or not target_project_id:
            return Response(
                {'error': '请提供source_project和target_project参数'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            source_project = Project.objects.get(id=source_project_id)
            target_project = Project.objects.get(id=target_project_id)
        except Project.DoesNotExist:
            return Response(
                {'error': '项目不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        source_boms = ProjectBOM.objects.filter(
            project=source_project,
            is_deleted=False
        )
        
        if not source_boms.exists():
            return Response(
                {'error': '源项目没有BOM数据'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_count = 0
        skipped_count = 0
        
        for source_bom in source_boms:
            # Check if already exists in target
            existing = ProjectBOM.objects.filter(
                project=target_project,
                item=source_bom.item,
                is_deleted=False
            ).exists()
            
            if existing:
                skipped_count += 1
                continue
            
            ProjectBOM.objects.create(
                project=target_project,
                item=source_bom.item,
                planned_qty=source_bom.planned_qty,
                estimated_cost=source_bom.estimated_cost,
                notes=source_bom.notes,
                created_by=request.user
            )
            created_count += 1
        
        return Response({
            'message': f'复制完成: 新增 {created_count} 条, 跳过 {skipped_count} 条（已存在）',
            'created': created_count,
            'skipped': skipped_count
        })


class TimeLogViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for TimeLog management.
    """
    queryset = TimeLog.objects.all()
    serializer_class = TimeLogSerializer
    filterset_fields = ['project', 'task', 'user', 'status', 'is_deleted']
    search_fields = ['description']
    ordering_fields = ['date', 'created_at']
    
    def get_queryset(self):
        """Filter by current user unless admin."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # If not admin, only show own time logs
        if user.role and user.role.data_scope != 'ALL':
            queryset = queryset.filter(user=user)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def my_summary(self, request):
        """Get current user's time log summary."""
        from django.utils import timezone
        from datetime import timedelta
        
        user = request.user
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        logs = TimeLog.objects.filter(user=user, is_deleted=False)
        
        week_hours = logs.filter(date__gte=week_start).aggregate(Sum('hours'))['hours__sum'] or 0
        month_hours = logs.filter(date__gte=month_start).aggregate(Sum('hours'))['hours__sum'] or 0
        
        return Response({
            'week_hours': float(week_hours),
            'month_hours': float(month_hours),
        })
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a time log."""
        time_log = self.get_object()
        time_log.status = 'APPROVED'
        time_log.save()
        
        # Update task actual hours
        if time_log.task:
            time_log.task.actual_hours = F('actual_hours') + time_log.hours
            time_log.task.save()
        
        return Response(TimeLogSerializer(time_log).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a time log."""
        time_log = self.get_object()
        time_log.status = 'REJECTED'
        time_log.save()
        return Response(TimeLogSerializer(time_log).data)


class ECNViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
    """
    ViewSet for ECN (Engineering Change Notice) management.
    """
    queryset = ECN.objects.all()
    filterset_fields = ['project', 'change_type', 'priority', 'status', 'requested_by', 'is_deleted']
    search_fields = ['ecn_no', 'title', 'description']
    ordering_fields = ['ecn_no', 'requested_date', 'created_at']
    module_name = 'projects'
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ECNWriteSerializer
        return ECNSerializer
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit ECN for review."""
        ecn = self.get_object()
        
        if ecn.status != 'DRAFT':
            return Response(
                {'error': '只有草稿状态的ECN可以提交评审'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ecn.status = 'PENDING'
        ecn.save()
        
        # Create approval record
        ECNApproval.objects.create(
            ecn=ecn,
            approver=request.user,
            action='SUBMIT',
            comment=request.data.get('comment', ''),
            created_by=request.user
        )
        
        return Response(ECNSerializer(ecn, context={'request': request}).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve ECN."""
        ecn = self.get_object()
        
        if ecn.status not in ['PENDING', 'REVIEWING']:
            return Response(
                {'error': '当前状态无法批准'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        
        ecn.status = 'APPROVED'
        ecn.approved_by = request.user
        ecn.approved_date = timezone.now().date()
        ecn.save()
        
        # Create approval record
        ECNApproval.objects.create(
            ecn=ecn,
            approver=request.user,
            action='APPROVE',
            comment=request.data.get('comment', ''),
            created_by=request.user
        )
        
        return Response(ECNSerializer(ecn, context={'request': request}).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject ECN."""
        ecn = self.get_object()
        
        if ecn.status not in ['PENDING', 'REVIEWING']:
            return Response(
                {'error': '当前状态无法拒绝'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ecn.status = 'REJECTED'
        ecn.save()
        
        # Create approval record
        ECNApproval.objects.create(
            ecn=ecn,
            approver=request.user,
            action='REJECT',
            comment=request.data.get('comment', '拒绝'),
            created_by=request.user
        )
        
        return Response(ECNSerializer(ecn, context={'request': request}).data)
    
    @action(detail=True, methods=['post'])
    def return_to_draft(self, request, pk=None):
        """Return ECN to draft for modification."""
        ecn = self.get_object()
        
        if ecn.status not in ['PENDING', 'REVIEWING', 'REJECTED']:
            return Response(
                {'error': '当前状态无法退回'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ecn.status = 'DRAFT'
        ecn.save()
        
        # Create approval record
        ECNApproval.objects.create(
            ecn=ecn,
            approver=request.user,
            action='RETURN',
            comment=request.data.get('comment', '退回修改'),
            created_by=request.user
        )
        
        return Response(ECNSerializer(ecn, context={'request': request}).data)
    
    @action(detail=True, methods=['post'])
    def start_implementation(self, request, pk=None):
        """Start ECN implementation."""
        ecn = self.get_object()
        
        if ecn.status != 'APPROVED':
            return Response(
                {'error': '只有已批准的ECN可以开始实施'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ecn.status = 'IMPLEMENTING'
        ecn.implemented_by = request.user
        ecn.save()
        
        # Create approval record
        ECNApproval.objects.create(
            ecn=ecn,
            approver=request.user,
            action='IMPLEMENT',
            comment=request.data.get('comment', ''),
            created_by=request.user
        )
        
        return Response(ECNSerializer(ecn, context={'request': request}).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete ECN implementation."""
        ecn = self.get_object()
        
        if ecn.status != 'IMPLEMENTING':
            return Response(
                {'error': '只有实施中的ECN可以完成'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        
        ecn.status = 'COMPLETED'
        ecn.implemented_date = timezone.now().date()
        ecn.implementation_notes = request.data.get('implementation_notes', '')
        ecn.save()
        
        # Apply changes to BOM if applicable
        self._apply_bom_changes(ecn)
        
        # Create approval record
        ECNApproval.objects.create(
            ecn=ecn,
            approver=request.user,
            action='COMPLETE',
            comment=request.data.get('comment', '实施完成'),
            created_by=request.user
        )
        
        return Response(ECNSerializer(ecn, context={'request': request}).data)
    
    def _apply_bom_changes(self, ecn):
        """Apply ECN changes to project BOM."""
        for item in ecn.items.all():
            if item.change_type == 'ADD' and item.item:
                # Add new BOM item
                ProjectBOM.objects.get_or_create(
                    project=ecn.project,
                    item=item.item,
                    defaults={
                        'planned_qty': item.new_qty or 0,
                        'notes': f'通过ECN {ecn.ecn_no} 添加',
                        'created_by': ecn.implemented_by
                    }
                )
            elif item.change_type == 'DELETE' and item.bom_item:
                # Mark BOM item as deleted
                item.bom_item.is_deleted = True
                item.bom_item.notes = f'{item.bom_item.notes}\n通过ECN {ecn.ecn_no} 删除'
                item.bom_item.save()
            elif item.change_type == 'MODIFY' and item.bom_item:
                # Update BOM item quantity
                if item.new_qty is not None:
                    item.bom_item.planned_qty = item.new_qty
                    item.bom_item.notes = f'{item.bom_item.notes}\n通过ECN {ecn.ecn_no} 修改数量'
                    item.bom_item.save()
            elif item.change_type == 'REPLACE' and item.bom_item and item.new_item:
                # Replace BOM item
                old_bom = item.bom_item
                old_bom.is_deleted = True
                old_bom.notes = f'{old_bom.notes}\n通过ECN {ecn.ecn_no} 替换为 {item.new_item.sku}'
                old_bom.save()
                
                # Create new BOM item
                ProjectBOM.objects.create(
                    project=ecn.project,
                    item=item.new_item,
                    planned_qty=item.new_qty or old_bom.planned_qty,
                    notes=f'通过ECN {ecn.ecn_no} 替换自 {old_bom.item.sku}',
                    created_by=ecn.implemented_by
                )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel ECN."""
        ecn = self.get_object()
        
        if ecn.status in ['COMPLETED', 'CANCELLED']:
            return Response(
                {'error': '已完成或已取消的ECN无法取消'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ecn.status = 'CANCELLED'
        ecn.save()
        
        # Create approval record
        ECNApproval.objects.create(
            ecn=ecn,
            approver=request.user,
            action='CANCEL',
            comment=request.data.get('comment', '取消'),
            created_by=request.user
        )
        
        return Response(ECNSerializer(ecn, context={'request': request}).data)
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """Add item to ECN."""
        ecn = self.get_object()
        
        if ecn.status not in ['DRAFT']:
            return Response(
                {'error': '只有草稿状态可以添加明细'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ECNItemSerializer(data={**request.data, 'ecn': ecn.id})
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['delete'], url_path='remove_item/(?P<item_id>[^/.]+)')
    def remove_item(self, request, pk=None, item_id=None):
        """Remove item from ECN."""
        ecn = self.get_object()
        
        if ecn.status not in ['DRAFT']:
            return Response(
                {'error': '只有草稿状态可以删除明细'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            ecn_item = ECNItem.objects.get(id=item_id, ecn=ecn)
            ecn_item.delete()
            return Response({'message': '删除成功'})
        except ECNItem.DoesNotExist:
            return Response(
                {'error': '明细不存在'},
                status=status.HTTP_404_NOT_FOUND
            )


class ECNItemViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for ECN Item management.
    """
    queryset = ECNItem.objects.all()
    serializer_class = ECNItemSerializer
    filterset_fields = ['ecn', 'change_type', 'item']
    search_fields = ['notes']
    ordering_fields = ['created_at']


# ==================== 售后管理视图 ====================

class AfterSalesOrderViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
    """
    售后工单管理视图
    """
    queryset = AfterSalesOrder.objects.all()
    filterset_fields = ['project', 'customer', 'order_type', 'priority', 'status', 'assigned_to', 'is_warranty']
    search_fields = ['order_no', 'title', 'description', 'contact_person', 'contact_phone']
    ordering_fields = ['order_no', 'reported_at', 'priority', 'status', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AfterSalesOrderListSerializer
        return AfterSalesOrderSerializer
    
    def perform_create(self, serializer):
        from apps.core.utils import generate_code
        order_no = generate_code('AS')
        serializer.save(order_no=order_no, created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取售后统计数据"""
        from django.db.models import Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        queryset = self.filter_queryset(self.get_queryset())
        
        # 按状态统计
        status_stats = queryset.values('status').annotate(count=Count('id'))
        
        # 按类型统计
        type_stats = queryset.values('order_type').annotate(count=Count('id'))
        
        # 成本统计
        cost_stats = queryset.aggregate(
            total_labor=Sum('labor_cost'),
            total_travel=Sum('travel_cost'),
            total_parts=Sum('parts_cost'),
            total_other=Sum('other_cost')
        )
        
        # 满意度统计
        satisfaction_stats = queryset.filter(
            satisfaction_score__isnull=False
        ).aggregate(avg_score=Avg('satisfaction_score'))
        
        # 本月新增工单
        today = timezone.now().date()
        month_start = today.replace(day=1)
        monthly_count = queryset.filter(reported_at__date__gte=month_start).count()
        
        # 待处理工单
        pending_count = queryset.filter(status__in=['PENDING', 'ASSIGNED']).count()
        
        return Response({
            'status_stats': list(status_stats),
            'type_stats': list(type_stats),
            'cost_stats': cost_stats,
            'satisfaction_avg': satisfaction_stats.get('avg_score'),
            'monthly_count': monthly_count,
            'pending_count': pending_count
        })
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """派单"""
        order = self.get_object()
        assigned_to_id = request.data.get('assigned_to')
        
        if not assigned_to_id:
            return Response({'error': '请指定负责人'}, status=status.HTTP_400_BAD_REQUEST)
        
        from apps.accounts.models import User
        try:
            assigned_to = User.objects.get(id=assigned_to_id)
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        order.assigned_to = assigned_to
        order.status = 'ASSIGNED'
        order.save()
        
        return Response({'message': '派单成功', 'status': order.status})
    
    @action(detail=True, methods=['post'])
    def start_service(self, request, pk=None):
        """开始服务"""
        order = self.get_object()
        order.status = 'IN_PROGRESS'
        order.save()
        return Response({'message': '已开始服务', 'status': order.status})
    
    @action(detail=True, methods=['post'])
    def on_site(self, request, pk=None):
        """现场服务"""
        order = self.get_object()
        order.status = 'ON_SITE'
        order.save()
        return Response({'message': '已到达现场', 'status': order.status})
    
    @action(detail=True, methods=['post'])
    def waiting_parts(self, request, pk=None):
        """等待备件"""
        order = self.get_object()
        order.status = 'WAITING_PARTS'
        order.save()
        return Response({'message': '等待备件', 'status': order.status})
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决问题"""
        order = self.get_object()
        from django.utils import timezone
        
        solution = request.data.get('solution', '')
        root_cause = request.data.get('root_cause', '')
        preventive_action = request.data.get('preventive_action', '')
        
        order.solution = solution
        order.root_cause = root_cause
        order.preventive_action = preventive_action
        order.status = 'RESOLVED'
        order.resolved_at = timezone.now()
        order.save()
        
        return Response({'message': '问题已解决', 'status': order.status})
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭工单"""
        order = self.get_object()
        from django.utils import timezone
        
        satisfaction_score = request.data.get('satisfaction_score')
        customer_feedback = request.data.get('customer_feedback', '')
        
        if satisfaction_score:
            order.satisfaction_score = satisfaction_score
        order.customer_feedback = customer_feedback
        order.status = 'CLOSED'
        order.closed_at = timezone.now()
        order.save()
        
        return Response({'message': '工单已关闭', 'status': order.status})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消工单"""
        order = self.get_object()
        order.status = 'CANCELLED'
        order.save()
        return Response({'message': '工单已取消', 'status': order.status})
    
    @action(detail=True, methods=['post'])
    def update_cost(self, request, pk=None):
        """更新成本"""
        order = self.get_object()
        
        labor_cost = request.data.get('labor_cost')
        travel_cost = request.data.get('travel_cost')
        parts_cost = request.data.get('parts_cost')
        other_cost = request.data.get('other_cost')
        
        if labor_cost is not None:
            order.labor_cost = labor_cost
        if travel_cost is not None:
            order.travel_cost = travel_cost
        if parts_cost is not None:
            order.parts_cost = parts_cost
        if other_cost is not None:
            order.other_cost = other_cost
        
        order.save()
        
        return Response({
            'message': '成本更新成功',
            'total_cost': order.total_cost
        })


class ServiceRecordViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    服务记录管理视图
    """
    queryset = ServiceRecord.objects.all()
    serializer_class = ServiceRecordSerializer
    filterset_fields = ['aftersales_order', 'service_type', 'technician', 'service_date']
    search_fields = ['work_content', 'findings', 'actions_taken']
    ordering_fields = ['service_date', 'created_at']
    ordering = ['-service_date']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        
        # 更新工单人工和差旅费用
        record = serializer.instance
        order = record.aftersales_order
        
        from django.db.models import Sum
        totals = order.service_records.aggregate(
            labor=Sum('labor_cost'),
            travel=Sum('travel_cost')
        )
        order.labor_cost = totals['labor'] or 0
        order.travel_cost = totals['travel'] or 0
        order.save()


class SparePartUsageViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    备件使用记录管理视图
    """
    queryset = SparePartUsage.objects.all()
    serializer_class = SparePartUsageSerializer
    filterset_fields = ['aftersales_order', 'service_record', 'item', 'is_warranty']
    search_fields = ['serial_no', 'notes']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        
        # 更新工单备件费用
        usage = serializer.instance
        order = usage.aftersales_order
        
        from django.db.models import Sum, F
        total = order.spare_parts.aggregate(
            parts_cost=Sum(F('qty') * F('unit_cost'))
        )
        order.parts_cost = total['parts_cost'] or 0
        order.save()

