"""
Views for projects app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.db import transaction
from django.db.models import Sum, F, Q
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin
from apps.core.permission_service import resolve_data_scope, get_department_tree_ids
from apps.masterdata.models import Item
from .models import (
    Project, ProjectMember, ProjectTask, ProjectBOM, TimeLog, 
    ECN, ECNItem, ECNApproval,
    AfterSalesOrder, ServiceRecord, SparePartUsage,
    Drawing, DrawingChangeNotice
)
from .serializers import (
    ProjectSerializer, ProjectMemberSerializer,
    ProjectTaskSerializer, ProjectBOMSerializer, TimeLogSerializer,
    ECNSerializer, ECNWriteSerializer, ECNItemSerializer, ECNApprovalSerializer,
    AfterSalesOrderSerializer, AfterSalesOrderListSerializer,
    ServiceRecordSerializer, SparePartUsageSerializer,
    DrawingSerializer, DrawingChangeNoticeSerializer
)


class ProjectViewSet(SoftDeleteMixin, UserTrackingMixin, PermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for Project management.
    """
    permission_module = 'projects'
    permission_resource = 'project'

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filterset_fields = ['customer', 'manager', 'status', 'is_deleted']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'start_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交项目审批 - 审批步骤由流程配置决定"""
        project = self.get_object()
        if project.status not in ['DRAFT', 'PLANNING', 'REJECTED']:
            return Response(
                {'error': '只能提交草稿、规划中或已拒绝状态的项目'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 使用项目预算作为金额
        amount = project.budget_total or 0
        
        try:
            from apps.core.workflow.services import WorkflowService
            
            instance, error = WorkflowService.start_workflow(
                business_type='PROJECT',
                business_id=project.id,
                business_no=project.code,
                submitter=request.user,
                amount=amount
            )
            
            if instance:
                project.status = 'PENDING'
                project.save()
                return Response({
                    **ProjectSerializer(project).data,
                    'workflow_started': True,
                    'workflow_id': instance.id,
                    'message': '已提交审批，请在审批中心查看审批进度'
                })
            else:
                # 未配置审批流程，直接激活
                project.status = 'IN_PROGRESS'
                project.save()
                return Response({
                    **ProjectSerializer(project).data,
                    'workflow_started': False,
                    'message': error or '未配置审批流程，项目已直接启动'
                })
                
        except Exception as e:
            # 审批模块不可用，直接激活
            project.status = 'IN_PROGRESS'
            project.save()
            return Response({
                **ProjectSerializer(project).data,
                'workflow_started': False,
                'message': f'项目已启动，但工作流服务异常: {e}'
            })
    
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """Change project status."""
        ALLOWED_TRANSITIONS = {
            'DRAFT': ['PLANNING', 'CANCELLED'],
            'PLANNING': ['IN_PROGRESS', 'DRAFT', 'CANCELLED'],
            'IN_PROGRESS': ['DEBUGGING', 'ON_HOLD', 'CANCELLED'],
            'DEBUGGING': ['INSTALLATION', 'IN_PROGRESS', 'ON_HOLD'],
            'INSTALLATION': ['ACCEPTANCE', 'DEBUGGING', 'ON_HOLD'],
            'ACCEPTANCE': ['COMPLETED', 'INSTALLATION'],
            'ON_HOLD': ['IN_PROGRESS', 'DEBUGGING', 'INSTALLATION', 'CANCELLED'],
            'COMPLETED': ['WARRANTY'],
            'WARRANTY': ['CLOSED'],
        }

        project = self.get_object()
        new_status = request.data.get('status')

        if new_status not in dict(Project.STATUS_CHOICES):
            return Response(
                {'error': '无效的状态'},
                status=status.HTTP_400_BAD_REQUEST
            )

        allowed = ALLOWED_TRANSITIONS.get(project.status, [])
        if new_status not in allowed:
            return Response(
                {'error': f'不允许从 {project.status} 转换到 {new_status}'},
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


class ProjectMemberViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for ProjectMember management.
    """
    permission_module = 'projects'
    permission_resource = 'project_member'

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


class ProjectTaskViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for ProjectTask management.
    """
    permission_module = 'projects'
    permission_resource = 'project_task'

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
    
    @action(detail=True, methods=['post'])
    def recalculate_hours(self, request, pk=None):
        """重新计算任务的实际工时（从工时填报汇总）"""
        task = self.get_object()
        
        # 汇总该任务下所有已审批的工时记录
        total_hours = TimeLog.objects.filter(
            task=task,
            status='APPROVED',
            is_deleted=False
        ).aggregate(total=Sum('hours'))['total'] or 0
        
        task.actual_hours = total_hours
        task.save(update_fields=['actual_hours'])
        
        return Response({
            'message': '工时已重新计算',
            'actual_hours': float(task.actual_hours),
            'task': ProjectTaskSerializer(task).data
        })
    
    @action(detail=False, methods=['post'])
    def batch_recalculate_hours(self, request):
        """批量重新计算所有任务的实际工时"""
        project_id = request.data.get('project')
        
        queryset = self.get_queryset().filter(is_deleted=False)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        updated_count = 0
        for task in queryset:
            total_hours = TimeLog.objects.filter(
                task=task,
                status='APPROVED',
                is_deleted=False
            ).aggregate(total=Sum('hours'))['total'] or 0
            
            if task.actual_hours != total_hours:
                task.actual_hours = total_hours
                task.save(update_fields=['actual_hours'])
                updated_count += 1
        
        return Response({
            'message': f'已重新计算 {updated_count} 个任务的工时',
            'updated_count': updated_count
        })


class ProjectBOMViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for ProjectBOM management.
    """
    permission_module = 'projects'
    permission_resource = 'project_bom'

    queryset = ProjectBOM.objects.all()
    serializer_class = ProjectBOMSerializer
    filterset_fields = ['project', 'item', 'is_deleted', 'quote_status', 'order_status', 'has_drawing']
    search_fields = ['item__sku', 'item__name', 'project__name', 'project__code', 'specification', 'version_brand']
    ordering_fields = ['created_at', 'project', 'item', 'quote_status']
    ordering = ['-created_at']  # 默认按创建时间倒序
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    def get_queryset(self):
        """支持更多筛选参数"""
        queryset = super().get_queryset()
        
        # 物料类型筛选
        item_type = self.request.query_params.get('item_type')
        if item_type:
            queryset = queryset.filter(item__item_type__icontains=item_type)
        
        # 版本/品牌筛选（同时搜索BOM的version_brand和物料主数据的brand）
        version_brand = self.request.query_params.get('version_brand')
        if version_brand:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(version_brand__icontains=version_brand) | Q(item__brand__icontains=version_brand)
            )
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """
        创建BOM时，如果存在已软删除的相同记录，则恢复它而不是报错
        """
        # 直接调用父类创建方法
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
        ).select_related(
            'item', 'item__category', 'requester',
            'work_center', 'process', 'drawing', 'purchase_order'
        )
        
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
            required_header = workbook.add_format({
                'bold': True,
                'bg_color': '#C00000',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            yellow_header = workbook.add_format({
                'bold': True,
                'bg_color': '#FFFF00',
                'font_color': 'black',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            green_header = workbook.add_format({
                'bold': True,
                'bg_color': '#92D050',
                'font_color': 'black',
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
                'num_format': '#,##0.00'
            })
            money_format = workbook.add_format({
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '¥#,##0.00'
            })
            date_format = workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'num_format': 'yyyy-mm-dd'
            })
            
            # Column headers: 精简为用户要求的字段
            headers = [
                ('序号', 6, 'normal'),
                ('物料编码', 15, 'required'),
                ('有图/无图', 10, 'normal'),
                ('物料类型', 10, 'normal'),
                ('物料名称', 20, 'normal'),
                ('规格型号', 15, 'normal'),
                ('版本/品牌', 12, 'normal'),
                ('单位', 8, 'normal'),
                ('数量', 12, 'required'),
                ('需求日期', 12, 'normal'),
                ('申请人', 10, 'normal'),
            ]

            # Write title
            from datetime import datetime
            last_col = len(headers) - 1
            worksheet.merge_range(0, 0, 0, last_col, f'项目BOM清单 - {project.name} ({project.code})', title_format)
            worksheet.write(1, 0, f'导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}')

            # Write headers (row 3)
            for col, (header, width, fmt_type) in enumerate(headers):
                if fmt_type == 'required':
                    fmt = required_header
                elif fmt_type == 'yellow':
                    fmt = yellow_header
                elif fmt_type == 'green':
                    fmt = green_header
                else:
                    fmt = header_format
                worksheet.write(3, col, header, fmt)
                worksheet.set_column(col, col, width)
            
            # Write data
            row = 4
            total_planned = 0
            
            for idx, bom in enumerate(bom_items, 1):
                planned = float(bom.planned_qty)
                total_planned += planned
                
                # 物料类型：使用物料主数据分类显示
                item_type_display = bom.item.get_item_type_display()
                # 有图/无图
                has_drawing_display = bom.get_has_drawing_display()
                
                col = 0
                worksheet.write(row, col, idx, data_format); col += 1
                worksheet.write(row, col, bom.item.sku, data_format); col += 1
                worksheet.write(row, col, has_drawing_display, data_format); col += 1
                worksheet.write(row, col, item_type_display, data_format); col += 1
                worksheet.write(row, col, bom.item.name, data_format); col += 1
                worksheet.write(row, col, bom.item.specification or '', data_format); col += 1
                worksheet.write(row, col, bom.version_brand or bom.item.brand or '', data_format); col += 1
                worksheet.write(row, col, bom.item.get_unit_display(), data_format); col += 1
                worksheet.write(row, col, planned, number_format); col += 1
                worksheet.write(row, col, bom.required_date.strftime('%Y-%m-%d') if bom.required_date else '', data_format); col += 1
                worksheet.write(row, col, bom.requester.get_full_name() if bom.requester else '', data_format); col += 1
                row += 1
            
            # Write totals
            total_format = workbook.add_format({
                'bold': True,
                'border': 1,
                'bg_color': '#E2EFDA',
                'align': 'right'
            })
            worksheet.write(row, 6, '合计:', total_format)  # 位于数量列前一列
            worksheet.write(row, 7, total_planned, total_format)  # 数量合计
            for col in range(8, len(headers)):
                worksheet.write(row, col, '', total_format)
            
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
            yellow_format = workbook.add_format({
                'bold': True,
                'bg_color': '#FFFF00',
                'font_color': 'black',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True
            })
            green_format = workbook.add_format({
                'bold': True,
                'bg_color': '#92D050',
                'font_color': 'black',
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
            
            # Column headers: 精简版导入模板（与用户需求一致）
            headers = [
                ('序号', 8, 'readonly'),
                ('物料编码*', 15, 'required'),
                ('有图/无图', 10, 'optional'),
                ('物料类型', 10, 'optional'),
                ('物料名称', 20, 'readonly'),
                ('规格型号', 15, 'readonly'),
                ('版本/品牌', 12, 'optional'),
                ('单位', 8, 'readonly'),
                ('数量*', 12, 'required'),
                ('需求日期', 12, 'optional'),
                ('申请人', 10, 'optional'),
            ]
            
            # Write headers
            for col, (header, width, htype) in enumerate(headers):
                if htype == 'required':
                    fmt = required_format
                elif htype == 'readonly':
                    fmt = readonly_format
                elif htype == 'yellow':
                    fmt = yellow_format
                elif htype == 'green':
                    fmt = green_format
                else:
                    fmt = header_format
                worksheet.write(0, col, header, fmt)
                worksheet.set_column(col, col, width)
            
            # Write example data (row 1) - 精简列
            example_data = [
                (1, readonly_example_format),                    # 序号
                ('MAT001', example_format),                      # 物料编码*
                ('有图', example_format),                        # 有图/无图
                ('机械类', example_format),                      # 物料类型
                ('(系统自动填充)', readonly_example_format),      # 物料名称
                ('(系统自动填充)', readonly_example_format),      # 规格型号
                ('V1.0', example_format),                        # 版本/品牌
                ('(自动)', readonly_example_format),             # 单位
                (100, example_format),                           # 数量*
                ('2026-01-15', example_format),                  # 需求日期
                ('张三', example_format),                        # 申请人
            ]
            for col, (value, fmt) in enumerate(example_data):
                worksheet.write(1, col, value, fmt)
            
            # Write second example row
            example_data2 = [
                (2, readonly_example_format),                    # 序号
                ('MAT002', example_format),                      # 物料编码*
                ('无图', example_format),                        # 有图/无图
                ('电气类', example_format),                      # 物料类型
                ('(系统自动填充)', readonly_example_format),      # 物料名称
                ('(系统自动填充)', readonly_example_format),      # 规格型号
                ('V2.0', example_format),                        # 版本/品牌
                ('(自动)', readonly_example_format),             # 单位
                (50, example_format),                            # 数量*
                ('2026-01-20', example_format),                  # 需求日期
                ('李四', example_format),                        # 申请人
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
                ('BOM导入模板填写说明（非标自动化行业版）', title_format),
                ('', None),
                ('【列说明】', section_format),
                ('', None),
                ('红色表头 = 必填字段（导入时必须填写）', bold_format),
                ('  • 物料编码*：必须与系统中物料管理的SKU完全一致', None),
                ('  • 计划数量*：正数，表示该物料在项目中的计划使用数量', None),
                ('', None),
                ('黄色表头 = 价格字段（可选填）', bold_format),
                ('  • 预估单价：物料的预估采购单价，不填则使用物料的标准成本', None),
                ('', None),
                ('蓝色表头 = 选填字段（可以为空）', bold_format),
                ('  • 版本/品牌：物料的版本号或品牌信息', None),
                ('  • 物料属性：标准件/外购件/外协件/自制件/易耗品/虚拟件/组件', None),
                ('  • BOM状态：草稿/已确认/已下发/已完成/已取消', None),
                ('  • 优先级：低/普通/高/紧急', None),
                ('  • 关键件/长周期件：填写"是"或"否"', None),
                ('  • 图纸号/图纸版本：图纸编号和版本信息', None),
                ('  • 材质规格/表面处理：物料的材质和表面处理工艺', None),
                ('  • 工作中心/工序：装配工位和工序名称（需系统中已存在）', None),
                ('  • 装配顺序：数字，表示装配顺序', None),
                ('  • 功能模块：物料所属的功能模块名称', None),
                ('  • 目标成本：目标采购单价', None),
                ('  • 损耗率%：物料损耗百分比，如5表示5%', None),
                ('  • 有图/无图：填写"有图"、"无图"或"待定"', None),
                ('  • 需求日期/最晚下单：日期格式YYYY-MM-DD，如2026-01-15', None),
                ('  • 申请人：填写申请人姓名（系统会自动匹配）', None),
                ('  • 备注/说明：备注和详细说明信息', None),
                ('', None),
                ('绿色表头 = 自动计算字段', bold_format),
                ('  • 预估成本：= 计划数量 × 预估单价，系统自动计算', None),
                ('', None),
                ('灰色表头 = 系统自动填充（导入时忽略，无需填写）', bold_format),
                ('  • 序号、物料名称、规格型号、单位、物料类型：根据物料编码自动获取', None),
                ('  • 已领用、剩余需求：系统自动计算', None),
                ('', None),
                ('【导入步骤】', section_format),
                ('', None),
                ('1. 删除示例数据行（黄色背景的行）', None),
                ('2. 必填字段：物料编码、计划数量', None),
                ('3. 非标行业选填：物料属性、优先级、关键件、图纸号、工作中心、功能模块等', None),
                ('4. 其他选填：版本/品牌、预估单价、有图/无图、需求日期、申请人、备注、说明', None),
                ('5. 灰色列可以留空或删除，系统会自动忽略', None),
                ('6. 保存文件并在系统中导入', None),
                ('', None),
                ('【常见错误】', section_format),
                ('', None),
                ('• 物料编码不存在：请先在"物料管理"中创建该物料', None),
                ('• 数量格式错误：请输入正数', None),
                ('• 日期格式错误：请使用YYYY-MM-DD格式', None),
                ('• 物料已存在：勾选"更新已存在的物料"可覆盖', None),
                ('• 工作中心/工序不存在：请先在生产管理中创建', None),
                ('• 物料属性/优先级/状态：必须使用规定的值，详见示例', None),
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
        auto_create_items = request.data.get('auto_create_items', 'false').lower() == 'true'
        
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
        
        # Find optional columns with helper function
        def find_column(df, keywords):
            for col in df.columns:
                for keyword in keywords:
                    if keyword in col:
                        return col
            return None
        
        # 原有字段
        price_column = find_column(df, ['预估单价', '单价'])
        notes_column = find_column(df, ['备注'])
        description_column = find_column(df, ['说明'])
        version_brand_column = find_column(df, ['版本/品牌', '版本', '品牌'])
        has_drawing_column = find_column(df, ['有图/无图', '有图', '无图'])
        required_date_column = find_column(df, ['需求日期', '日期'])
        requester_column = find_column(df, ['申请人'])
        unit_column = find_column(df, ['单位'])
        
        # 物料基本信息（用于自动创建物料）
        item_name_column = find_column(df, ['物料名称', '名称', '描述'])
        spec_column = find_column(df, ['规格型号', '规格', '型号'])
        item_type_column = find_column(df, ['物料类型', '类型'])
        brand_column = find_column(df, ['品牌', '厂家', '生产厂家'])
        
        # 新增字段（非标自动化行业专用）
        item_property_column = find_column(df, ['物料属性'])
        status_column = find_column(df, ['BOM状态', '状态'])
        priority_column = find_column(df, ['优先级'])
        is_critical_column = find_column(df, ['关键件'])
        is_long_lead_column = find_column(df, ['长周期件'])
        drawing_no_column = find_column(df, ['图纸号'])
        drawing_version_column = find_column(df, ['图纸版本'])
        material_spec_column = find_column(df, ['材质规格', '材质'])
        surface_treatment_column = find_column(df, ['表面处理'])
        work_center_column = find_column(df, ['工作中心', '工位'])
        process_column = find_column(df, ['工序'])
        assembly_sequence_column = find_column(df, ['装配顺序'])
        function_module_column = find_column(df, ['功能模块', '模块'])
        target_cost_column = find_column(df, ['目标成本'])
        scrap_rate_column = find_column(df, ['损耗率'])
        latest_order_date_column = find_column(df, ['最晚下单'])
        
        # Import User model for requester lookup
        from apps.accounts.models import User
        from datetime import datetime
        
        created_count = 0
        updated_count = 0
        skip_count = 0
        items_created_count = 0  # 自动创建的物料数量
        error_rows = []
        
        # 先校验所有关键字段，若有任一行缺失/无效则拒绝全部导入
        processed_skus = set()
        prechecked_rows = []
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row number (1-based, plus header)
            sku = str(row[sku_column]).strip() if pd.notna(row[sku_column]) else ''
            if not sku:
                error_rows.append({'row': row_num, 'error': '物料编码为空'})
                continue
            if sku.startswith('MAT00') or sku.startswith('(') or '示例' in sku or '自动' in sku:
                continue
            if sku in processed_skus:
                skip_count += 1
                continue
            processed_skus.add(sku)
            try:
                item = Item.objects.get(sku=sku)
            except Item.DoesNotExist:
                if auto_create_items:
                    # 自动创建物料
                    item_name = str(row[item_name_column]).strip() if item_name_column and pd.notna(row.get(item_name_column)) else f'物料-{sku}'
                    spec = str(row[spec_column]).strip() if spec_column and pd.notna(row.get(spec_column)) else ''
                    unit_val = str(row[unit_column]).strip() if unit_column and pd.notna(row.get(unit_column)) else '个'
                    item_type_val = str(row[item_type_column]).strip() if item_type_column and pd.notna(row.get(item_type_column)) else ''
                    brand_val = str(row[brand_column]).strip() if brand_column and pd.notna(row.get(brand_column)) else ''
                    
                    # 推断物料属性
                    item_property = 'PURCHASED'  # 默认外购
                    if item_property_column and pd.notna(row.get(item_property_column)):
                        prop_val = str(row[item_property_column]).strip()
                        if '自制' in prop_val: item_property = 'SELF_MADE'
                        elif '外协' in prop_val: item_property = 'OUTSOURCED'
                        elif '标准' in prop_val: item_property = 'STANDARD'
                    
                    item = Item.objects.create(
                        sku=sku,
                        name=item_name,
                        specification=spec,
                        unit=unit_val,
                        item_type=item_type_val,
                        item_property=item_property,
                        manufacturer=brand_val,
                        is_active=True,
                        created_by=request.user,
                        updated_by=request.user
                    )
                    items_created_count += 1
                else:
                    error_rows.append({'row': row_num, 'error': f'物料编码 {sku} 不存在于物料主数据'})
                    continue
            # 数量校验（保持原逻辑）
            try:
                planned_qty = float(row[qty_column]) if pd.notna(row[qty_column]) else 0
            except (ValueError, TypeError):
                error_rows.append({'row': row_num, 'error': '计划数量格式错误'})
                continue
            if planned_qty <= 0:
                error_rows.append({'row': row_num, 'error': '计划数量必须大于0'})
                continue
            # 单位必填
            if not unit_column:
                error_rows.append({'row': row_num, 'error': 'Excel文件必须包含“单位”列'})
                continue
            unit_val = str(row[unit_column]).strip() if pd.notna(row.get(unit_column)) else ''
            if not unit_val:
                error_rows.append({'row': row_num, 'error': '单位为空'})
                continue

            # 需求日期必填
            if not required_date_column:
                error_rows.append({'row': row_num, 'error': 'Excel文件必须包含“需求日期”列'})
                continue
            required_date = None
            if pd.notna(row.get(required_date_column)):
                try:
                    date_val = row[required_date_column]
                    if isinstance(date_val, str):
                        # 尝试多种字符串格式
                        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%Y年%m月%d日']:
                            try:
                                required_date = datetime.strptime(date_val, fmt).date()
                                break
                            except ValueError:
                                continue
                        if not required_date:
                            required_date = pd.to_datetime(date_val).date()
                    elif isinstance(date_val, (int, float)):
                        # Excel日期数值格式转换 (Excel epoch: 1899-12-30)
                        from datetime import timedelta
                        excel_epoch = datetime(1899, 12, 30)
                        required_date = (excel_epoch + timedelta(days=int(date_val))).date()
                    else:
                        required_date = pd.to_datetime(date_val).date()
                except (ValueError, TypeError) as e:
                    error_rows.append({'row': row_num, 'error': f'需求日期格式错误: {date_val}'})
                    continue
            if not required_date:
                error_rows.append({'row': row_num, 'error': '需求日期为空'})
                continue

            # 申请人必填但不再强制匹配系统用户
            if not requester_column:
                error_rows.append({'row': row_num, 'error': 'Excel文件必须包含“申请人”列'})
                continue
            requester_name = str(row[requester_column]).strip() if pd.notna(row.get(requester_column)) else ''
            if not requester_name:
                error_rows.append({'row': row_num, 'error': '申请人为空'})
                continue
            requester = User.objects.filter(
                Q(username=requester_name) |
                Q(first_name__icontains=requester_name) |
                Q(last_name__icontains=requester_name)
            ).first() or None

            prechecked_rows.append((row_num, row, sku, item, planned_qty, required_date, requester))
        
        # 若有错误，拒绝全部导入
        if error_rows:
            # 拼接前若干条错误，便于前端直接展示
            preview = '; '.join([f"行{e['row']}: {e['error']}" for e in error_rows[:5]])
            return Response(
                {
                    'error': f'校验失败，未导入任何数据。问题示例：{preview}',
                    'errors': error_rows,
                    'required_columns': ['物料编码', '有图/无图', '物料类型', '物料名称', '规格型号', '版本/品牌', '单位', '数量', '需求日期', '申请人']
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 通过校验后再处理写入
        processed_skus = set()
        with transaction.atomic():
            for row_num, row, sku, item, planned_qty, required_date, requester in prechecked_rows:
                if sku in processed_skus:
                    skip_count += 1
                    continue
                processed_skus.add(sku)
            
                # Get price (optional)
                unit_price = item.standard_cost
                if price_column and pd.notna(row.get(price_column)):
                    try:
                        unit_price = float(row[price_column])
                    except (ValueError, TypeError):
                        pass  # Use item's standard cost
            
                # Get notes (optional)
                notes = ''
                if notes_column and pd.notna(row.get(notes_column)):
                    notes = str(row[notes_column])
            
                # Get description (optional)
                description = ''
                if description_column and pd.notna(row.get(description_column)):
                    description = str(row[description_column])
            
                # 版本/品牌：始终以物料主数据为准，忽略文件中的差异
                brand = item.brand or ''
                model = getattr(item, 'model', '') or ''
                version_brand = f"{brand}/{model}".strip('/ ')
            
                # Get has_drawing (optional)
                has_drawing = 'PENDING'
                if has_drawing_column and pd.notna(row.get(has_drawing_column)):
                    drawing_val = str(row[has_drawing_column]).strip()
                    if '有图' in drawing_val:
                        has_drawing = 'YES'
                    elif '无图' in drawing_val:
                        has_drawing = 'NO'
            
                    # required_date / requester 已在预校验阶段解析
            
                # ===== 新增字段处理 =====
                # 物料属性
                item_property = ''
                if item_property_column and pd.notna(row.get(item_property_column)):
                    prop_map = {
                        '标准件': 'STANDARD', '外购件': 'PURCHASED', '外协件': 'OUTSOURCED',
                        '自制件': 'SELF_MADE', '易耗品': 'CONSUMABLE', '虚拟件': 'VIRTUAL', '组件': 'ASSEMBLY'
                    }
                    prop_val = str(row[item_property_column]).strip()
                    item_property = prop_map.get(prop_val, '')
            
                # BOM状态
                bom_status = 'DRAFT'
                if status_column and pd.notna(row.get(status_column)):
                    status_map = {
                        '草稿': 'DRAFT', '已确认': 'CONFIRMED', '已下发': 'RELEASED',
                        '已完成': 'COMPLETED', '已取消': 'CANCELLED'
                    }
                    status_val = str(row[status_column]).strip()
                    bom_status = status_map.get(status_val, 'DRAFT')
            
                # 优先级
                priority = 'NORMAL'
                if priority_column and pd.notna(row.get(priority_column)):
                    priority_map = {'低': 'LOW', '普通': 'NORMAL', '高': 'HIGH', '紧急': 'URGENT'}
                    priority_val = str(row[priority_column]).strip()
                    priority = priority_map.get(priority_val, 'NORMAL')
            
                # 关键件
                is_critical = False
                if is_critical_column and pd.notna(row.get(is_critical_column)):
                    val = str(row[is_critical_column]).strip()
                    is_critical = val in ['是', 'Y', 'Yes', 'TRUE', 'True', '1']
            
                # 长周期件
                is_long_lead = False
                if is_long_lead_column and pd.notna(row.get(is_long_lead_column)):
                    val = str(row[is_long_lead_column]).strip()
                    is_long_lead = val in ['是', 'Y', 'Yes', 'TRUE', 'True', '1']
            
                # 简单字符串字段
                drawing_no = str(row[drawing_no_column]).strip() if drawing_no_column and pd.notna(row.get(drawing_no_column)) else ''
                drawing_version = str(row[drawing_version_column]).strip() if drawing_version_column and pd.notna(row.get(drawing_version_column)) else ''
                material_spec = str(row[material_spec_column]).strip() if material_spec_column and pd.notna(row.get(material_spec_column)) else ''
                surface_treatment = str(row[surface_treatment_column]).strip() if surface_treatment_column and pd.notna(row.get(surface_treatment_column)) else ''
                function_module = str(row[function_module_column]).strip() if function_module_column and pd.notna(row.get(function_module_column)) else ''
            
                # 工作中心和工序（查找对象）
                work_center = None
                if work_center_column and pd.notna(row.get(work_center_column)):
                    from apps.production.scheduling import WorkCenter as WC
                    wc_name = str(row[work_center_column]).strip()
                    work_center = WC.objects.filter(name=wc_name).first()
            
                process = None
                if process_column and pd.notna(row.get(process_column)):
                    from apps.production.models import ProductionProcess as PP
                    process_name = str(row[process_column]).strip()
                    process = PP.objects.filter(name=process_name, project=project).first()
            
                # 数值字段
                assembly_sequence = 0
                if assembly_sequence_column and pd.notna(row.get(assembly_sequence_column)):
                    try:
                        assembly_sequence = int(row[assembly_sequence_column])
                    except (ValueError, TypeError):
                        pass
            
                target_cost = None
                if target_cost_column and pd.notna(row.get(target_cost_column)):
                    try:
                        target_cost = float(row[target_cost_column])
                    except (ValueError, TypeError):
                        pass
            
                scrap_rate = 0
                if scrap_rate_column and pd.notna(row.get(scrap_rate_column)):
                    try:
                        scrap_rate = float(row[scrap_rate_column])
                    except (ValueError, TypeError):
                        pass
            
                # 最晚下单日期
                latest_order_date = None
                if latest_order_date_column and pd.notna(row.get(latest_order_date_column)):
                    try:
                        date_val = row[latest_order_date_column]
                        if isinstance(date_val, str):
                            latest_order_date = datetime.strptime(date_val, '%Y-%m-%d').date()
                        else:
                            latest_order_date = pd.to_datetime(date_val).date()
                    except (ValueError, TypeError):
                        pass
                # ===== 新增字段处理结束 =====
            
                # Check if BOM item exists
                existing_bom = ProjectBOM.objects.filter(
                    project=project,
                    item=item,
                    is_deleted=False
                ).first()
            
                if existing_bom:
                    if update_existing:
                        existing_bom.planned_qty = planned_qty
                        existing_bom.estimated_cost = unit_price
                        if notes:
                            existing_bom.notes = notes
                        if description:
                            existing_bom.description = description
                        if version_brand:
                            existing_bom.version_brand = version_brand
                        existing_bom.has_drawing = has_drawing
                        if required_date:
                            existing_bom.required_date = required_date
                        if requester:
                            existing_bom.requester = requester
                    
                        # 更新新增字段
                        if item_property:
                            existing_bom.item_property = item_property
                        existing_bom.status = bom_status
                        existing_bom.priority = priority
                        existing_bom.is_critical = is_critical
                        existing_bom.is_long_lead = is_long_lead
                        if drawing_no:
                            existing_bom.drawing_no = drawing_no
                        if drawing_version:
                            existing_bom.drawing_version = drawing_version
                        if material_spec:
                            existing_bom.material_spec = material_spec
                        if surface_treatment:
                            existing_bom.surface_treatment = surface_treatment
                        if work_center:
                            existing_bom.work_center = work_center
                        if process:
                            existing_bom.process = process
                        existing_bom.assembly_sequence = assembly_sequence
                        if function_module:
                            existing_bom.function_module = function_module
                        if target_cost is not None:
                            existing_bom.target_cost = target_cost
                        existing_bom.scrap_rate = scrap_rate
                        if latest_order_date:
                            existing_bom.latest_order_date = latest_order_date
                    
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
                        estimated_cost=unit_price,
                        notes=notes,
                        description=description,
                        version_brand=version_brand,
                        has_drawing=has_drawing,
                        required_date=required_date,
                        requester=requester,
                        # 新增字段
                        item_property=item_property,
                        status=bom_status,
                        priority=priority,
                        is_critical=is_critical,
                        is_long_lead=is_long_lead,
                        drawing_no=drawing_no,
                        drawing_version=drawing_version,
                        material_spec=material_spec,
                        surface_treatment=surface_treatment,
                        work_center=work_center,
                        process=process,
                        assembly_sequence=assembly_sequence,
                        function_module=function_module,
                        target_cost=target_cost,
                        scrap_rate=scrap_rate,
                        latest_order_date=latest_order_date,
                        created_by=request.user
                    )
                    created_count += 1
        
        msg_parts = [f'新增 {created_count} 条', f'更新 {updated_count} 条']
        if skip_count > 0:
            msg_parts.append(f'跳过重复 {skip_count} 条')
        if items_created_count > 0:
            msg_parts.append(f'自动创建物料 {items_created_count} 个')
        
        return Response({
            'message': f'导入完成: {", ".join(msg_parts)}',
            'created': created_count,
            'updated': updated_count,
            'skip_count': skip_count,
            'items_created': items_created_count,
            'errors': error_rows
        })
    
    @action(detail=False, methods=['post'])
    def export_for_quote(self, request):
        """
        导出物料需求清单（用于线下询价）
        包含历史采购价格和供应商参考
        """
        project_id = request.data.get('project')
        bom_ids = request.data.get('bom_ids', [])
        
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
        
        # 获取BOM物料
        if bom_ids:
            bom_items = self.get_queryset().filter(
                id__in=bom_ids,
                project_id=project_id,
                is_deleted=False
            ).select_related('item')
        else:
            bom_items = self.get_queryset().filter(
                project_id=project_id,
                is_deleted=False
            ).select_related('item')
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            worksheet = workbook.add_worksheet('物料需求清单')
            
            # Define formats
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'left',
                'valign': 'vcenter'
            })
            readonly_header = workbook.add_format({
                'bold': True,
                'bg_color': '#808080',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            ref_header = workbook.add_format({
                'bold': True,
                'bg_color': '#92D050',  # 绿色 - 参考信息
                'font_color': 'black',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            input_header = workbook.add_format({
                'bold': True,
                'bg_color': '#FFC000',  # 橙色 - 需要填写
                'font_color': 'black',
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
                'num_format': '#,##0.00'
            })
            
            # Headers
            from datetime import datetime
            headers = [
                ('序号', 6, 'readonly'),
                ('项目号', 12, 'readonly'),
                ('物料编码', 15, 'readonly'),
                ('有图/无图', 10, 'readonly'),
                ('物料类型', 10, 'readonly'),
                ('物料名称', 25, 'readonly'),
                ('规格型号', 20, 'readonly'),
                ('版本/品牌', 15, 'readonly'),
                ('单位', 8, 'readonly'),
                ('数量', 10, 'readonly'),
                ('历史单价(参考)', 14, 'ref'),
                ('历史供应商(参考)', 18, 'ref'),
                ('供应商', 18, 'input'),
                ('单价', 12, 'input'),
                ('付款方式', 12, 'input'),
                ('账期', 12, 'input'),
                ('备注', 20, 'input'),
            ]
            
            # Write title
            last_col = len(headers) - 1
            worksheet.merge_range(0, 0, 0, last_col, f'物料需求清单 - {project.name} ({project.code})', title_format)
            worksheet.write(1, 0, f'导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
            worksheet.write(2, 0, '说明: 灰色=只读, 绿色=历史参考, 橙色=需要填写', data_format)
            
            # Write headers
            format_map = {
                'readonly': readonly_header,
                'ref': ref_header,
                'input': input_header
            }
            for col, (header, width, htype) in enumerate(headers):
                fmt = format_map[htype]
                worksheet.write(4, col, header, fmt)
                worksheet.set_column(col, col, width)
            
            # Write data
            row = 5
            for idx, bom in enumerate(bom_items, 1):
                # 查找历史采购记录（最近一次）
                from apps.purchase.models import PurchaseOrderLine
                last_po_line = PurchaseOrderLine.objects.filter(
                    item=bom.item,
                    po__status__in=['CONFIRMED', 'COMPLETED', 'PARTIAL']
                ).select_related('po__supplier').order_by('-po__order_date').first()
                
                history_price = ''
                history_supplier = ''
                if last_po_line:
                    history_price = float(last_po_line.unit_price)
                    history_supplier = last_po_line.po.supplier.name if last_po_line.po.supplier else ''
                
                # 有图/无图显示
                has_drawing_display = bom.get_has_drawing_display() if hasattr(bom, 'get_has_drawing_display') else ''
                
                # 物料类型
                item_type_display = bom.item.get_item_type_display() if bom.item else ''
                
                # 版本/品牌
                brand = bom.item.brand or '' if bom.item else ''
                model = bom.item.model or '' if bom.item else ''
                version_brand = f"{brand}/{model}" if brand or model else ''
                version_brand = version_brand.strip('/')
                
                col = 0
                worksheet.write(row, col, idx, data_format); col += 1
                worksheet.write(row, col, project.code, data_format); col += 1
                worksheet.write(row, col, bom.item.sku if bom.item else '', data_format); col += 1
                worksheet.write(row, col, has_drawing_display, data_format); col += 1
                worksheet.write(row, col, item_type_display, data_format); col += 1
                worksheet.write(row, col, bom.item.name if bom.item else '', data_format); col += 1
                worksheet.write(row, col, bom.item.specification if bom.item else '', data_format); col += 1
                worksheet.write(row, col, version_brand, data_format); col += 1
                worksheet.write(row, col, bom.item.get_unit_display() if bom.item else '', data_format); col += 1
                worksheet.write(row, col, float(bom.planned_qty), number_format); col += 1
                worksheet.write(row, col, history_price, number_format); col += 1
                worksheet.write(row, col, history_supplier, data_format); col += 1
                # 以下是需要填写的列，留空
                worksheet.write(row, col, '', data_format); col += 1  # 供应商
                worksheet.write(row, col, '', number_format); col += 1  # 单价
                worksheet.write(row, col, '', data_format); col += 1  # 付款方式
                worksheet.write(row, col, '', data_format); col += 1  # 账期
                worksheet.write(row, col, '', data_format)  # 备注
                
                row += 1
            
            worksheet.set_row(0, 25)
            worksheet.freeze_panes(5, 3)  # 冻结前5行和前3列
        
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=Material_Request_{project.code}.xlsx'
        return response
    
    @action(detail=False, methods=['get'])
    def export_quote_bom(self, request):
        """
        导出询价BOM清单（只导出未报价的物料）
        包含：物料编号、有图/无图、物料类型、物料名称、规格型号、版本/品牌、单位、数量、
              供应商名称、含税单价、未税单价、税率、交期
        """
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
        
        # 只获取未报价的物料（quote_status = 'NOT_QUOTED'）
        bom_items = self.get_queryset().filter(
            project_id=project_id,
            is_deleted=False,
            quote_status='NOT_QUOTED'
        ).select_related('item', 'quote_supplier')
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            worksheet = workbook.add_worksheet('询价BOM清单')
            
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
            readonly_header = workbook.add_format({
                'bold': True,
                'bg_color': '#808080',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            input_header = workbook.add_format({
                'bold': True,
                'bg_color': '#FFC000',
                'font_color': 'black',
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
                'num_format': '#,##0.00'
            })
            money_format = workbook.add_format({
                'border': 1,
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '#,##0.0000'
            })
            
            # Write title
            from datetime import datetime
            headers = [
                ('序号', 6, 'readonly'),
                ('物料编码', 15, 'readonly'),
                ('有图/无图', 10, 'readonly'),
                ('物料类型', 10, 'readonly'),
                ('物料名称', 25, 'readonly'),
                ('规格型号', 20, 'readonly'),
                ('版本/品牌', 15, 'readonly'),
                ('单位', 8, 'readonly'),
                ('数量', 12, 'readonly'),
                ('供应商名称', 20, 'input'),
                ('含税单价', 12, 'input'),
                ('未税单价', 12, 'input'),
                ('税率(%)', 10, 'input'),
                ('交期(天)', 10, 'input'),
            ]
            
            last_col = len(headers) - 1
            worksheet.merge_range(0, 0, 0, last_col, f'询价BOM清单 - {project.name} ({project.code})', title_format)
            worksheet.write(1, 0, f'导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
            worksheet.write(2, 0, '说明: 灰色列为只读信息，橙色列需要填写报价信息', data_format)
            
            # Write headers (row 4)
            for col, (header, width, htype) in enumerate(headers):
                if htype == 'readonly':
                    fmt = readonly_header
                else:
                    fmt = input_header
                worksheet.write(4, col, header, fmt)
                worksheet.set_column(col, col, width)
            
            # Write data
            row = 5
            for idx, bom in enumerate(bom_items, 1):
                planned = float(bom.planned_qty)
                
                # 物料类型
                item_type_display = bom.item.get_item_type_display()
                # 有图/无图
                has_drawing_display = bom.get_has_drawing_display()
                
                col = 0
                worksheet.write(row, col, idx, data_format); col += 1
                worksheet.write(row, col, bom.item.sku, data_format); col += 1
                worksheet.write(row, col, has_drawing_display, data_format); col += 1
                worksheet.write(row, col, item_type_display, data_format); col += 1
                worksheet.write(row, col, bom.item.name, data_format); col += 1
                worksheet.write(row, col, bom.item.specification or '', data_format); col += 1
                worksheet.write(row, col, bom.version_brand or f"{bom.item.brand or ''}/{bom.item.model or ''}".strip('/'), data_format); col += 1
                worksheet.write(row, col, bom.item.get_unit_display(), data_format); col += 1
                worksheet.write(row, col, planned, number_format); col += 1
                # 以下为待填写的报价信息（留空）
                worksheet.write(row, col, '', data_format); col += 1  # 供应商名称
                worksheet.write(row, col, '', money_format); col += 1  # 含税单价
                worksheet.write(row, col, '', money_format); col += 1  # 未税单价
                worksheet.write(row, col, '', data_format); col += 1  # 税率
                worksheet.write(row, col, '', data_format); col += 1  # 交期
                row += 1
            
            # Set row heights
            worksheet.set_row(0, 25)
            worksheet.set_row(4, 22)
            
            # Freeze panes
            worksheet.freeze_panes(5, 2)
        
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=Quote_BOM_{project.code}.xlsx'
        return response
    
    @action(detail=False, methods=['post'])
    def import_quote_bom(self, request):
        """
        导入已报价BOM
        校验物料编码是否与项目BOM匹配，不匹配则拒绝导入
        导入成功后将物料标记为已询价状态
        """
        import logging
        logger = logging.getLogger(__name__)
        
        file = request.FILES.get('file')
        project_id = request.data.get('project') or request.POST.get('project')
        
        logger.info(f"import_quote_bom called: file={file}, project_id={project_id}")
        logger.info(f"request.data keys: {list(request.data.keys())}")
        logger.info(f"request.FILES keys: {list(request.FILES.keys())}")
        
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
            # 先读取Excel文件，尝试找到正确的列标题行
            # 导出的询价BOM清单有前4行是标题和说明，列标题在第5行（index=4）
            df_raw = pd.read_excel(file, header=None)
            
            # 查找包含"物料编码"的行作为列标题行
            header_row = None
            for idx, row in df_raw.iterrows():
                row_values = [str(v) for v in row.values if pd.notna(v)]
                if any('物料编码' in v for v in row_values):
                    header_row = idx
                    break
            
            if header_row is not None:
                # 重新读取，指定header行
                file.seek(0)  # 重置文件指针
                df = pd.read_excel(file, header=header_row)
            else:
                # 没找到物料编码行，使用默认方式读取
                file.seek(0)
                df = pd.read_excel(file)
                
            logger.info(f"Excel columns: {list(df.columns)}")
        except Exception as e:
            logger.error(f"Excel读取失败: {str(e)}")
            return Response(
                {'error': f'Excel文件读取失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find columns
        def find_column(df, keywords):
            for col in df.columns:
                col_str = str(col)
                for keyword in keywords:
                    if keyword in col_str:
                        return col
            return None
        
        sku_column = find_column(df, ['物料编码', 'SKU', '编码'])
        supplier_column = find_column(df, ['供应商名称', '供应商'])
        price_with_tax_column = find_column(df, ['含税单价', '含税价'])
        price_without_tax_column = find_column(df, ['未税单价', '未税价', '不含税单价'])
        tax_rate_column = find_column(df, ['税率'])
        delivery_days_column = find_column(df, ['交期', '交货天数'])
        
        if not sku_column:
            return Response(
                {'error': 'Excel文件必须包含"物料编码"列'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取项目所有BOM物料编码
        project_bom_skus = set(
            ProjectBOM.objects.filter(
                project=project,
                is_deleted=False
            ).values_list('item__sku', flat=True)
        )
        
        # 第一遍校验：检查所有物料编码是否在项目BOM中
        error_rows = []
        valid_rows = []
        
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row number
            sku = str(row[sku_column]).strip() if pd.notna(row[sku_column]) else ''
            
            if not sku:
                continue  # 跳过空行
            
            # 跳过示例行
            if sku.startswith('(') or '示例' in sku or '自动' in sku:
                continue
            
            # 检查物料编码是否在项目BOM中
            if sku not in project_bom_skus:
                error_rows.append({
                    'row': row_num,
                    'sku': sku,
                    'error': f'物料编码 {sku} 不在该项目的BOM清单中'
                })
                continue
            
            # 检查是否有报价信息（至少要有供应商或价格）
            supplier_name = str(row[supplier_column]).strip() if supplier_column and pd.notna(row.get(supplier_column)) else ''
            price_with_tax = None
            price_without_tax = None
            tax_rate = None
            delivery_days = None
            
            if price_with_tax_column and pd.notna(row.get(price_with_tax_column)):
                try:
                    price_with_tax = float(row[price_with_tax_column])
                except (ValueError, TypeError):
                    pass
            
            if price_without_tax_column and pd.notna(row.get(price_without_tax_column)):
                try:
                    price_without_tax = float(row[price_without_tax_column])
                except (ValueError, TypeError):
                    pass
            
            if tax_rate_column and pd.notna(row.get(tax_rate_column)):
                try:
                    tax_rate = float(row[tax_rate_column])
                except (ValueError, TypeError):
                    pass
            
            if delivery_days_column and pd.notna(row.get(delivery_days_column)):
                try:
                    delivery_days = int(row[delivery_days_column])
                except (ValueError, TypeError):
                    pass
            
            # 必须至少有含税单价或未税单价
            if price_with_tax is None and price_without_tax is None:
                error_rows.append({
                    'row': row_num,
                    'sku': sku,
                    'error': f'物料 {sku} 缺少价格信息（含税单价或未税单价至少填写一项）'
                })
                continue
            
            valid_rows.append({
                'row_num': row_num,
                'sku': sku,
                'supplier_name': supplier_name,
                'price_with_tax': price_with_tax,
                'price_without_tax': price_without_tax,
                'tax_rate': tax_rate,
                'delivery_days': delivery_days
            })
        
        # 如果有错误，拒绝整个导入
        if error_rows:
            preview = '; '.join([f"行{e['row']}: {e['error']}" for e in error_rows[:5]])
            return Response(
                {
                    'error': f'校验失败，未导入任何数据。问题示例：{preview}',
                    'errors': error_rows,
                    'total_errors': len(error_rows)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not valid_rows:
            return Response(
                {'error': '没有找到有效的报价数据'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 校验通过，开始更新BOM
        from apps.masterdata.models import Supplier
        from datetime import date
        
        updated_count = 0
        with transaction.atomic():
            for row_data in valid_rows:
                sku = row_data['sku']
                
                # 查找供应商
                quote_supplier = None
                if row_data['supplier_name']:
                    quote_supplier = Supplier.objects.filter(
                        Q(name__icontains=row_data['supplier_name']) |
                        Q(code__icontains=row_data['supplier_name'])
                    ).first()
                
                # 更新BOM项
                bom_item = ProjectBOM.objects.filter(
                    project=project,
                    item__sku=sku,
                    is_deleted=False
                ).first()
                
                if bom_item:
                    bom_item.quote_status = 'QUOTED'
                    bom_item.quote_supplier = quote_supplier
                    bom_item.price_with_tax = row_data['price_with_tax']
                    bom_item.price_without_tax = row_data['price_without_tax']
                    bom_item.tax_rate = row_data['tax_rate']
                    bom_item.quote_delivery_days = row_data['delivery_days']
                    bom_item.quote_date = date.today()
                    bom_item.save()
                    updated_count += 1
        
        return Response({
            'message': f'询价导入成功: 已更新 {updated_count} 条物料的报价信息',
            'updated': updated_count,
            'total_rows': len(valid_rows)
        })
    
    @action(detail=False, methods=['get'])
    def pending_quote_count(self, request):
        """获取待询价物料数量"""
        project_id = request.query_params.get('project')
        
        queryset = self.get_queryset().filter(
            is_deleted=False,
            quote_status='NOT_QUOTED'
        )
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        return Response({
            'count': queryset.count()
        })
    
    @action(detail=False, methods=['post'])
    def generate_purchase_request(self, request):
        """
        Generate purchase request from BOM items.
        PRD requirement: BOM清单推送到采购模块
        """
        from apps.purchase.models import PurchaseRequest, PurchaseRequestLine
        
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
        
        # Get BOM items to convert - 只获取已询价的物料
        bom_queryset = ProjectBOM.objects.filter(
            project=project,
            is_deleted=False,
            quote_status='QUOTED'  # 只允许已询价的物料
        ).select_related('item', 'quote_supplier')
        
        if item_ids:
            bom_queryset = bom_queryset.filter(item_id__in=item_ids)
        
        # 检查是否有未询价的物料被选中
        if item_ids:
            not_quoted_items = ProjectBOM.objects.filter(
                project=project,
                is_deleted=False,
                item_id__in=item_ids
            ).exclude(quote_status='QUOTED')
            
            if not_quoted_items.exists():
                not_quoted_skus = list(not_quoted_items.values_list('item__sku', flat=True)[:5])
                return Response(
                    {'error': f'以下物料尚未询价，无法生成采购申请: {", ".join(not_quoted_skus)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
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
                {'error': '没有需要采购的物料（计划数量已满足或物料未询价）'},
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
                # 优先使用询价信息中的价格（未税单价 > 含税单价 > 标准成本）
                estimated_price = bom.price_without_tax or bom.price_with_tax or bom.item.standard_cost or 0
                line_amount = needed_qty * float(estimated_price)
                
                # 获取询价供应商
                supplier = bom.quote_supplier or bom.supplier
                
                PurchaseRequestLine.objects.create(
                    pr=pr,
                    item=bom.item,
                    qty=needed_qty,
                    estimated_price=estimated_price,
                    project=project,
                    notes=f'BOM计划: {bom.planned_qty}, 已用: {bom.actual_qty}, 询价交期: {bom.quote_delivery_days or "-"}天',
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
    def purchasable_items(self, request):
        """
        获取可采购物料列表 - 只返回已询价且需要采购的物料
        用于待采购申请列表
        """
        project_id = request.query_params.get('project')
        
        queryset = ProjectBOM.objects.filter(
            is_deleted=False,
            quote_status='QUOTED'  # 只返回已询价的物料
        ).select_related('item', 'project', 'quote_supplier')
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        # 只返回需要采购的物料（计划数量 > 已用数量）
        purchasable_items = []
        for bom in queryset:
            needed_qty = float(bom.planned_qty) - float(bom.actual_qty)
            if needed_qty > 0:
                purchasable_items.append({
                    'id': bom.id,
                    'project_id': bom.project.id,
                    'project_code': bom.project.code,
                    'project_name': bom.project.name,
                    'item_id': bom.item.id,
                    'item_sku': bom.item.sku,
                    'item_name': bom.item.name,
                    'specification': bom.item.specification or '',
                    'version_brand': bom.version_brand or f"{bom.item.brand or ''}/{bom.item.model or ''}".strip('/'),
                    'unit': bom.item.get_unit_display(),
                    'planned_qty': float(bom.planned_qty),
                    'actual_qty': float(bom.actual_qty),
                    'needed_qty': needed_qty,
                    'quote_supplier_id': bom.quote_supplier.id if bom.quote_supplier else None,
                    'quote_supplier_name': bom.quote_supplier.name if bom.quote_supplier else '',
                    'price_with_tax': float(bom.price_with_tax) if bom.price_with_tax else None,
                    'price_without_tax': float(bom.price_without_tax) if bom.price_without_tax else None,
                    'tax_rate': float(bom.tax_rate) if bom.tax_rate else None,
                    'quote_delivery_days': bom.quote_delivery_days,
                    'quote_date': bom.quote_date.strftime('%Y-%m-%d') if bom.quote_date else None,
                    'required_date': bom.required_date.strftime('%Y-%m-%d') if bom.required_date else None,
                })
        
        return Response({
            'count': len(purchasable_items),
            'items': purchasable_items
        })
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """批量删除BOM物料"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请选择要删除的物料'}, status=status.HTTP_400_BAD_REQUEST)
        
        from django.utils import timezone as tz
        boms = ProjectBOM.objects.filter(id__in=ids, is_deleted=False)
        deleted_count = boms.count()
        boms.update(is_deleted=True, deleted_at=tz.now(), updated_by=request.user)
        return Response({
            'message': f'成功删除 {deleted_count} 条物料',
            'deleted_count': deleted_count
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

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """
        获取项目BOM的树形结构
        """
        project_id = request.query_params.get('project')
        if not project_id:
            return Response({'error': '请提供project参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取所有BOM项
        boms = self.get_queryset().filter(
            project_id=project_id,
            is_deleted=False
        ).select_related('item', 'parent').order_by('level', 'sort_order', 'id')
        
        def build_tree(parent_id=None, level=0):
            result = []
            items = [b for b in boms if b.parent_id == parent_id]
            for bom in items:
                node = ProjectBOMSerializer(bom, context={'request': request}).data
                node['level'] = level
                node['children'] = build_tree(bom.id, level + 1)
                result.append(node)
            return result
        
        tree_data = build_tree()
        return Response(tree_data)

    @action(detail=False, methods=['get'])
    def material_check(self, request):
        """
        物料齐套检查 - 检查BOM物料的库存是否满足需求
        返回齐套率和缺料明细
        """
        project_id = request.query_params.get('project')
        if not project_id:
            return Response({'error': '请提供project参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        from apps.inventory.models import Stock
        from django.db.models import Sum, F
        from decimal import Decimal
        
        boms = self.get_queryset().filter(
            project_id=project_id,
            is_deleted=False
        ).select_related('item')
        
        results = []
        total_items = 0
        complete_items = 0
        total_value = Decimal('0')
        shortage_value = Decimal('0')
        
        for bom in boms:
            # 获取该物料的库存总量
            stock_qty = Stock.objects.filter(
                item=bom.item,
                is_deleted=False
            ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            
            # 计算净需求 = 计划数量 - 已出库数量
            net_demand = bom.planned_qty - bom.issued_qty
            
            # 计算缺料数量
            shortage = max(Decimal('0'), net_demand - stock_qty)
            
            # 齐套状态
            if net_demand <= 0:
                check_status = 'COMPLETE'  # 已完成
            elif stock_qty >= net_demand:
                check_status = 'READY'  # 库存充足
            elif stock_qty > 0:
                check_status = 'PARTIAL'  # 部分满足
            else:
                check_status = 'SHORTAGE'  # 完全缺料
            
            # 计算金额
            unit_price = bom.estimated_cost or bom.item.standard_cost or Decimal('0')
            item_value = net_demand * unit_price
            shortage_item_value = shortage * unit_price
            
            total_items += 1
            if check_status in ['COMPLETE', 'READY']:
                complete_items += 1
            
            total_value += item_value
            shortage_value += shortage_item_value
            
            results.append({
                'id': bom.id,
                'item_id': bom.item_id,
                'item_sku': bom.item.sku,
                'item_name': bom.item.name,
                'specification': bom.item.specification or '',
                'unit': bom.item.get_unit_display(),
                'planned_qty': float(bom.planned_qty),
                'issued_qty': float(bom.issued_qty),
                'net_demand': float(net_demand),
                'stock_qty': float(stock_qty),
                'shortage': float(shortage),
                'unit_price': float(unit_price),
                'shortage_value': float(shortage_item_value),
                'status': check_status,
                'status_display': {
                    'COMPLETE': '已完成',
                    'READY': '库存充足',
                    'PARTIAL': '部分满足',
                    'SHORTAGE': '完全缺料'
                }.get(check_status, '未知')
            })
        
        # 计算齐套率
        completion_rate = round((complete_items / total_items * 100), 2) if total_items > 0 else 0
        
        return Response({
            'summary': {
                'total_items': total_items,
                'complete_items': complete_items,
                'shortage_items': total_items - complete_items,
                'completion_rate': completion_rate,
                'total_value': float(total_value),
                'shortage_value': float(shortage_value)
            },
            'details': results
        })

    @action(detail=True, methods=['post'])
    def add_child(self, request, pk=None):
        """
        为BOM项添加子物料
        """
        parent = self.get_object()
        
        item_id = request.data.get('item')
        if not item_id:
            return Response({'error': '请提供物料ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查是否已存在相同的子物料
        if ProjectBOM.objects.filter(
            project=parent.project,
            parent=parent,
            item_id=item_id,
            is_deleted=False
        ).exists():
            return Response({'error': '该子物料已存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        child = ProjectBOM.objects.create(
            project=parent.project,
            parent=parent,
            item_id=item_id,
            level=parent.level + 1,
            planned_qty=request.data.get('planned_qty', 1),
            unit_qty=request.data.get('unit_qty', 1),
            estimated_cost=request.data.get('estimated_cost', 0),
            notes=request.data.get('notes', ''),
            created_by=request.user
        )
        
        return Response(ProjectBOMSerializer(child, context={'request': request}).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def batch_update_level(self, request):
        """
        批量更新BOM物料的层级和排序
        """
        items = request.data.get('items', [])
        if not items:
            return Response({'error': '请提供要更新的物料列表'}, status=status.HTTP_400_BAD_REQUEST)
        
        updated_count = 0
        for item_data in items:
            bom_id = item_data.get('id')
            if bom_id:
                ProjectBOM.objects.filter(id=bom_id).update(
                    parent_id=item_data.get('parent'),
                    level=item_data.get('level', 0),
                    sort_order=item_data.get('sort_order', 0)
                )
                updated_count += 1
        
        return Response({
            'message': f'成功更新 {updated_count} 条记录',
            'updated_count': updated_count
        })


class TimeLogViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for TimeLog management.
    """
    permission_module = 'projects'
    permission_resource = 'time_log'

    queryset = TimeLog.objects.all()
    serializer_class = TimeLogSerializer
    filterset_fields = ['project', 'task', 'user', 'status', 'is_deleted']
    search_fields = ['description']
    ordering_fields = ['date', 'created_at']
    
    def get_queryset(self):
        """Filter by current user unless admin."""
        queryset = super().get_queryset()
        user = self.request.user

        scope_type, custom_dept_ids = resolve_data_scope(user, 'projects')
        if scope_type == 'self':
            queryset = queryset.filter(user=user)
        elif scope_type == 'dept':
            if user.department:
                queryset = queryset.filter(user__department=user.department)
            else:
                queryset = queryset.filter(user=user)
        elif scope_type == 'dept_tree':
            if user.department:
                queryset = queryset.filter(user__department_id__in=get_department_tree_ids(user.department.id))
            else:
                queryset = queryset.filter(user=user)
        elif scope_type == 'custom':
            if custom_dept_ids:
                queryset = queryset.filter(user__department_id__in=custom_dept_ids)
            else:
                queryset = queryset.none()
        
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
    
    def _update_task_actual_hours(self, task):
        """重新计算任务的实际工时（从所有已审批工时记录汇总）"""
        if not task:
            return
        # 汇总该任务下所有已审批的工时记录
        total_hours = TimeLog.objects.filter(
            task=task,
            status='APPROVED',
            is_deleted=False
        ).aggregate(total=Sum('hours'))['total'] or 0
        
        task.actual_hours = total_hours
        task.save(update_fields=['actual_hours'])
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a time log."""
        time_log = self.get_object()
        time_log.status = 'APPROVED'
        time_log.save()
        
        # 重新计算任务实际工时
        self._update_task_actual_hours(time_log.task)
        
        return Response(TimeLogSerializer(time_log).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a time log."""
        time_log = self.get_object()
        old_status = time_log.status
        time_log.status = 'REJECTED'
        time_log.save()
        
        # 如果之前是已审批状态，需要重新计算任务工时
        if old_status == 'APPROVED':
            self._update_task_actual_hours(time_log.task)
        
        return Response(TimeLogSerializer(time_log).data)


class ECNViewSet(SoftDeleteMixin, UserTrackingMixin, PermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for ECN (Engineering Change Notice) management.
    """
    permission_module = 'projects'
    permission_resource = 'ecn'

    queryset = ECN.objects.all()
    filterset_fields = ['project', 'change_type', 'priority', 'status', 'requested_by', 'is_deleted']
    search_fields = ['ecn_no', 'title', 'description']
    ordering_fields = ['ecn_no', 'requested_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ECNWriteSerializer
        return ECNSerializer
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit ECN for review via workflow."""
        ecn = self.get_object()
        
        if ecn.status != 'DRAFT':
            return Response(
                {'error': '只有草稿状态的ECN可以提交评审'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 计算成本影响金额作为审批阈值判断依据
        amount = abs(ecn.cost_impact) if ecn.cost_impact else 0
        
        # 尝试启动工作流
        from apps.core.workflow.services import WorkflowService
        instance, error = WorkflowService.start_workflow(
            business_type='ECN',
            business_id=ecn.id,
            business_no=ecn.ecn_no,
            submitter=request.user,
            amount=amount
        )

        if instance:
            # 有配置的工作流，使用工作流审批
            ecn.status = 'PENDING'
            ecn.save()
            
            # Create approval record
            ECNApproval.objects.create(
                ecn=ecn,
                approver=request.user,
                action='SUBMIT',
                comment=request.data.get('comment', '已提交工作流审批'),
                created_by=request.user
            )
            
            return Response({
                **ECNSerializer(ecn, context={'request': request}).data,
                'workflow_instance_id': instance.id,
                'message': '已提交审批流程'
            })
        else:
            # 没有配置工作流，使用原有逻辑
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
        from django.db import transaction

        with transaction.atomic():
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
                # 物理删除BOM项
                item.bom_item.delete()
            elif item.change_type == 'MODIFY' and item.bom_item:
                # Update BOM item quantity
                if item.new_qty is not None:
                    item.bom_item.planned_qty = item.new_qty
                    item.bom_item.notes = f'{item.bom_item.notes}\n通过ECN {ecn.ecn_no} 修改数量'
                    item.bom_item.save()
            elif item.change_type == 'REPLACE' and item.bom_item and item.new_item:
                # 替换BOM项：先创建新项，再删除旧项
                old_qty = item.bom_item.planned_qty
                old_sku = item.bom_item.item.sku
                
                # Create new BOM item
                ProjectBOM.objects.create(
                    project=ecn.project,
                    item=item.new_item,
                    planned_qty=item.new_qty or old_qty,
                    notes=f'通过ECN {ecn.ecn_no} 替换自 {old_sku}',
                    created_by=ecn.implemented_by
                )
                
                # 物理删除旧的BOM项
                item.bom_item.delete()
    
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


class ECNItemViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for ECN Item management.
    """
    permission_module = 'projects'
    permission_resource = 'ecn_item'

    queryset = ECNItem.objects.all()
    serializer_class = ECNItemSerializer
    filterset_fields = ['ecn', 'change_type', 'item']
    search_fields = ['notes']
    ordering_fields = ['created_at']


# ==================== 售后管理视图 ====================

class AfterSalesOrderViewSet(SoftDeleteMixin, UserTrackingMixin, PermissionMixin, viewsets.ModelViewSet):
    """
    售后工单管理视图
    """
    permission_module = 'projects'
    permission_resource = 'aftersales'

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


class ServiceRecordViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    服务记录管理视图
    """
    permission_module = 'projects'
    permission_resource = 'service_record'

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


class SparePartUsageViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    备件使用记录管理视图
    """
    permission_module = 'projects'
    permission_resource = 'spare_part_usage'

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


class DrawingViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    图纸管理视图
    """
    permission_module = 'projects'
    permission_resource = 'drawing'

    queryset = Drawing.objects.all()
    serializer_class = DrawingSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ['project', 'item', 'bom_item', 'file_type', 'status', 'designer']
    search_fields = ['drawing_no', 'name', 'notes']
    ordering_fields = ['drawing_no', 'version', 'revision', 'created_at']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            designer=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def submit_review(self, request, pk=None):
        """提交审核"""
        drawing = self.get_object()
        if drawing.status != 'DRAFT':
            return Response(
                {'error': '只能提交草稿状态的图纸'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        drawing.status = 'REVIEWING'
        drawing.save()
        return Response(DrawingSerializer(drawing).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批图纸"""
        drawing = self.get_object()
        if drawing.status != 'REVIEWING':
            return Response(
                {'error': '只能审批审核中的图纸'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        
        drawing.status = 'APPROVED'
        drawing.approver = request.user
        drawing.approved_at = timezone.now()
        drawing.save()
        return Response(DrawingSerializer(drawing).data)
    
    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """发布图纸"""
        drawing = self.get_object()
        if drawing.status != 'APPROVED':
            return Response(
                {'error': '只能发布已批准的图纸'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        
        drawing.status = 'RELEASED'
        drawing.released_at = timezone.now()
        drawing.save()
        
        # 创建变更通知
        notice = DrawingChangeNotice.objects.create(
            drawing=drawing,
            change_type='NEW' if drawing.revision == 1 else 'REVISION',
            new_version=f'{drawing.version}.{drawing.revision}',
            change_description=drawing.change_description or '图纸发布',
            created_by=request.user
        )
        
        # 发送邮件通知（异步任务）
        self._send_change_notification(notice)
        
        return Response({
            **DrawingSerializer(drawing).data,
            'notice_id': notice.id
        })
    
    @action(detail=True, methods=['post'])
    def new_revision(self, request, pk=None):
        """创建新版本"""
        drawing = self.get_object()
        if drawing.status not in ['RELEASED', 'APPROVED']:
            return Response(
                {'error': '只能为已发布或已批准的图纸创建新版本'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 创建新版本
        new_drawing = Drawing.objects.create(
            drawing_no=drawing.drawing_no,
            name=drawing.name,
            version=drawing.version,
            revision=drawing.revision + 1,
            project=drawing.project,
            item=drawing.item,
            bom_item=drawing.bom_item,
            file_type=drawing.file_type,
            file_path='',
            status='DRAFT',
            designer=request.user,
            change_description=request.data.get('change_description', ''),
            created_by=request.user
        )
        
        # 标记旧版本为废弃
        drawing.status = 'OBSOLETE'
        drawing.save()
        
        return Response(DrawingSerializer(new_drawing).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def export_template(self, request):
        """导出图纸导入模板"""
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            worksheet = workbook.add_worksheet('图纸导入模板')
            
            # 定义格式
            header_format = workbook.add_format({
                'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
                'border': 1, 'align': 'center', 'valign': 'vcenter'
            })
            required_format = workbook.add_format({
                'bold': True, 'bg_color': '#FF6B6B', 'font_color': 'white',
                'border': 1, 'align': 'center', 'valign': 'vcenter'
            })
            
            # 表头
            headers = [
                ('图纸号*', True), ('图纸名称*', True), ('版本', False),
                ('文件类型*', True), ('关联物料编码', False), ('公共盘路径', False),
                ('变更说明', False), ('备注', False)
            ]
            
            for col, (header, required) in enumerate(headers):
                fmt = required_format if required else header_format
                worksheet.write(0, col, header, fmt)
            
            # 列宽
            widths = [15, 25, 10, 12, 15, 40, 25, 25]
            for col, width in enumerate(widths):
                worksheet.set_column(col, col, width)
            
            # 示例数据
            examples = [
                ('DWG-001', '主轴装配图', 'A0', 'PDF', 'MAT001', r'\\192.168.1.100\drawings\项目A\DWG-001.pdf', '初版发布', ''),
                ('DWG-002', '底座加工图', 'A0', 'STEP', '', r'\\192.168.1.100\drawings\项目A\DWG-002.stp', '', '3D模型'),
            ]
            for row, example in enumerate(examples, 1):
                for col, val in enumerate(example):
                    worksheet.write(row, col, val)
            
            # 添加说明sheet
            help_sheet = workbook.add_worksheet('填写说明')
            help_sheet.write(0, 0, '字段说明', header_format)
            help_sheet.write(0, 1, '可选值/格式', header_format)
            helps = [
                ('图纸号*', '必填，图纸唯一标识'),
                ('图纸名称*', '必填，图纸描述'),
                ('版本', '默认A0，如：A0, A1, B0等'),
                ('文件类型*', 'PDF, STEP, STP, DWG, DXF, SOLIDWORKS, OTHER'),
                ('关联物料编码', '物料SKU，需已存在于系统'),
                ('公共盘路径', '网络共享路径'),
            ]
            for row, (field, desc) in enumerate(helps, 1):
                help_sheet.write(row, 0, field)
                help_sheet.write(row, 1, desc)
            help_sheet.set_column(0, 0, 20)
            help_sheet.set_column(1, 1, 50)
        
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=drawing_import_template.xlsx'
        return response
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """导出图纸列表"""
        project_id = request.query_params.get('project')
        
        queryset = self.get_queryset().filter(is_deleted=False)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        queryset = queryset.select_related('project', 'item', 'designer')
        
        data = []
        for d in queryset:
            data.append({
                '图纸号': d.drawing_no,
                '图纸名称': d.name,
                '版本': f'{d.version}.{d.revision}',
                '文件类型': d.get_file_type_display() if hasattr(d, 'get_file_type_display') else d.file_type,
                '状态': d.get_status_display() if hasattr(d, 'get_status_display') else d.status,
                '项目': d.project.name if d.project else '',
                '关联物料编码': d.item.sku if d.item else '',
                '关联物料名称': d.item.name if d.item else '',
                '公共盘路径': d.public_share_path or '',
                '设计者': d.designer.get_full_name() if d.designer else '',
                '变更说明': d.change_description or '',
                '备注': d.notes or '',
                '创建时间': d.created_at.strftime('%Y-%m-%d %H:%M') if d.created_at else '',
            })
        
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='图纸列表', index=False)
            
            workbook = writer.book
            worksheet = writer.sheets['图纸列表']
            header_format = workbook.add_format({
                'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
                'border': 1, 'align': 'center'
            })
            for col, header in enumerate(df.columns):
                worksheet.write(0, col, header, header_format)
            
            # 自动列宽
            for col, column in enumerate(df.columns):
                max_len = max(df[column].astype(str).apply(len).max(), len(column)) + 2
                worksheet.set_column(col, col, min(max_len, 50))
        
        output.seek(0)
        project_name = ''
        if project_id:
            try:
                project_name = Project.objects.get(id=project_id).code + '_'
            except Project.DoesNotExist:
                pass
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=drawings_{project_name}{pd.Timestamp.now().strftime("%Y%m%d")}.xlsx'
        return response
    
    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """批量导入图纸"""
        file = request.FILES.get('file')
        project_id = request.data.get('project')
        update_existing = request.data.get('update_existing', 'false').lower() == 'true'
        
        if not file:
            return Response({'error': '请上传Excel文件'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not project_id:
            return Response({'error': '请选择项目'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            df = pd.read_excel(file)
        except Exception as e:
            return Response({'error': f'Excel读取失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 查找列
        def find_column(keywords):
            for col in df.columns:
                for kw in keywords:
                    if kw in col:
                        return col
            return None
        
        drawing_no_col = find_column(['图纸号'])
        name_col = find_column(['图纸名称', '名称'])
        version_col = find_column(['版本'])
        file_type_col = find_column(['文件类型', '类型'])
        item_col = find_column(['物料编码', '关联物料'])
        path_col = find_column(['公共盘路径', '路径'])
        desc_col = find_column(['变更说明', '说明'])
        notes_col = find_column(['备注'])
        
        if not drawing_no_col or not name_col:
            return Response({
                'error': '缺少必需列',
                'required_columns': ['图纸号*', '图纸名称*']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 文件类型映射
        file_type_map = {
            'PDF': 'PDF', 'DWG': 'DWG', 'DXF': 'DXF',
            'STEP': 'STEP', 'STP': 'STP', 'IGES': 'IGES',
            'STL': 'STL', 'SOLIDWORKS': 'SOLIDWORKS', '其他': 'OTHER'
        }
        
        created_count = 0
        updated_count = 0
        error_rows = []
        
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            drawing_no = str(row[drawing_no_col]).strip() if pd.notna(row[drawing_no_col]) else ''
            if not drawing_no or drawing_no.startswith('DWG-00') or '示例' in drawing_no:
                continue
            
            name = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else ''
            if not name:
                error_rows.append({'row': row_num, 'error': '图纸名称为空'})
                continue
            
            # 文件类型
            file_type = 'PDF'
            if file_type_col and pd.notna(row.get(file_type_col)):
                ft = str(row[file_type_col]).strip().upper()
                file_type = file_type_map.get(ft, 'OTHER')
            
            # 版本
            version = 'A0'
            if version_col and pd.notna(row.get(version_col)):
                version = str(row[version_col]).strip()
            
            # 关联物料
            item = None
            if item_col and pd.notna(row.get(item_col)):
                item_sku = str(row[item_col]).strip()
                if item_sku:
                    try:
                        item = Item.objects.get(sku=item_sku)
                    except Item.DoesNotExist:
                        pass  # 物料不存在不报错，只是不关联
            
            # 路径
            public_share_path = ''
            if path_col and pd.notna(row.get(path_col)):
                public_share_path = str(row[path_col]).strip()
            
            # 变更说明
            change_description = ''
            if desc_col and pd.notna(row.get(desc_col)):
                change_description = str(row[desc_col]).strip()
            
            # 备注
            notes = ''
            if notes_col and pd.notna(row.get(notes_col)):
                notes = str(row[notes_col]).strip()
            
            # 检查是否已存在
            existing = Drawing.objects.filter(
                project=project,
                drawing_no=drawing_no,
                file_type=file_type,
                is_deleted=False
            ).first()
            
            try:
                if existing:
                    if update_existing:
                        existing.name = name
                        existing.version = version
                        existing.item = item
                        existing.public_share_path = public_share_path
                        existing.change_description = change_description
                        existing.notes = notes
                        existing.updated_by = request.user
                        existing.save()
                        updated_count += 1
                else:
                    Drawing.objects.create(
                        project=project,
                        drawing_no=drawing_no,
                        name=name,
                        version=version,
                        file_type=file_type,
                        item=item,
                        public_share_path=public_share_path,
                        change_description=change_description,
                        notes=notes,
                        status='DRAFT',
                        designer=request.user,
                        created_by=request.user
                    )
                    created_count += 1
            except Exception as e:
                error_rows.append({'row': row_num, 'error': str(e)})
        
        return Response({
            'message': f'导入完成：新增{created_count}条，更新{updated_count}条',
            'created': created_count,
            'updated': updated_count,
            'errors': error_rows
        })
    
    def _send_change_notification(self, notice):
        """发送变更通知邮件"""
        try:
            from apps.core.tasks import send_drawing_change_notification
            send_drawing_change_notification.delay(notice.id)
        except Exception:
            pass  # 邮件发送失败不影响主流程


class DrawingChangeNoticeViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    图纸变更通知视图
    """
    permission_module = 'projects'
    permission_resource = 'drawing_change_notice'

    queryset = DrawingChangeNotice.objects.all()
    serializer_class = DrawingChangeNoticeSerializer
    filterset_fields = ['drawing', 'change_type', 'email_sent']
    search_fields = ['change_description']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def resend_email(self, request, pk=None):
        """重新发送邮件通知"""
        notice = self.get_object()
        
        try:
            from apps.core.tasks import send_drawing_change_notification
            send_drawing_change_notification.delay(notice.id)
            return Response({'message': '邮件已加入发送队列'})
        except Exception as e:
            return Response(
                {'error': f'发送失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

