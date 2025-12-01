"""
Views for projects app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Sum, F
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin, DataScopeMixin
from apps.masterdata.models import Item
from .models import Project, ProjectMember, ProjectTask, ProjectBOM, TimeLog
from .serializers import (
    ProjectSerializer, ProjectMemberSerializer,
    ProjectTaskSerializer, ProjectBOMSerializer, TimeLogSerializer
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
    parser_classes = [MultiPartParser, FormParser]
    
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
        """Export BOM items to Excel file."""
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
        
        data = []
        for bom in bom_items:
            data.append({
                '物料编码': bom.item.sku,
                '物料名称': bom.item.name,
                '规格型号': bom.item.specification or '',
                '单位': bom.item.get_unit_display(),
                '物料类别': bom.item.category.name if bom.item.category else '',
                '计划数量': float(bom.planned_qty),
                '实际使用数量': float(bom.actual_qty),
                '预估单价': float(bom.item.standard_cost),
                '预估成本': float(bom.estimated_cost),
                '备注': bom.notes or '',
            })
        
        df = pd.DataFrame(data)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='BOM清单')
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['BOM清单']
            
            # Set column widths
            column_widths = [15, 25, 20, 8, 15, 12, 12, 12, 12, 25]
            for i, width in enumerate(column_widths):
                worksheet.set_column(i, i, width)
        
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=BOM_{project.code}.xlsx'
        return response
    
    @action(detail=False, methods=['get'])
    def export_template(self, request):
        """Export BOM import template."""
        # Create template with example data
        template_data = [
            {
                '物料编码(必填)': 'MAT001',
                '计划数量(必填)': 100,
                '预估单价': 10.00,
                '备注': '示例数据，请删除后填写实际数据',
            },
            {
                '物料编码(必填)': 'MAT002',
                '计划数量(必填)': 50,
                '预估单价': 25.50,
                '备注': '',
            },
        ]
        
        df = pd.DataFrame(template_data)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='BOM导入模板')
            
            workbook = writer.book
            worksheet = writer.sheets['BOM导入模板']
            
            # Set column widths
            worksheet.set_column(0, 0, 20)  # 物料编码
            worksheet.set_column(1, 1, 15)  # 计划数量
            worksheet.set_column(2, 2, 12)  # 预估单价
            worksheet.set_column(3, 3, 30)  # 备注
            
            # Add header format
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1
            })
            
            # Write headers with format
            for col, header in enumerate(df.columns):
                worksheet.write(0, col, header, header_format)
        
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
    
    @action(detail=False, methods=['get'])
    def copy_from_project(self, request):
        """Copy BOM from another project."""
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

