"""
Views for purchase app.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin
from apps.core.workflow.mixins import WorkflowEnforcementMixin
from apps.core.workflow.services import WorkflowService
from apps.projects.models import Project
from apps.inventory.cost_methods import CostingMethodFactory, FIFOCostingService
from .models import (
    PurchaseRequest, PurchaseRequestLine,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine,
    PurchaseContract
)
from .serializers import (
    PurchaseRequestSerializer, PurchaseRequestLineSerializer,
    PurchaseOrderSerializer, PurchaseOrderLineSerializer,
    GoodsReceiptSerializer, GoodsReceiptLineSerializer,
    PurchaseContractSerializer
)
from .services import BudgetValidationService
from .evaluation_models import SupplierBlacklist

logger = logging.getLogger(__name__)


class PurchaseRequestViewSet(PermissionMixin, WorkflowEnforcementMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseRequest management.
    """
    queryset = PurchaseRequest.objects.all()
    serializer_class = PurchaseRequestSerializer
    filterset_fields = ['project', 'requestor', 'status', 'is_deleted']
    search_fields = ['request_no']
    ordering_fields = ['request_date', 'created_at']

    # Permission configuration
    permission_module = 'purchase'
    permission_resource = 'request'

    # Workflow configuration
    workflow_business_type = 'PURCHASE_REQUEST'
    workflow_amount_field = 'total_amount'
    workflow_no_field = 'request_no'
    
    def update(self, request, *args, **kwargs):
        """只允许草稿或已拒绝状态的采购申请修改明细（与采购订单一致，防止绕过审批改金额）"""
        instance = self.get_object()
        if instance.status not in ['DRAFT', 'REJECTED']:
            return Response(
                {'error': '只有草稿或已拒绝的采购申请可以修改'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Auto-set requestor to current user and update BOM status."""
        with transaction.atomic():
            instance = serializer.save(
            created_by=self.request.user,
            requestor=self.request.user
        )
            
            # 更新BOM状态：NOT_ORDERED -> PR_PENDING
            if instance.project:
                from apps.projects.models import ProjectBOM
                # 获取采购申请行
                for pr_line in instance.lines.filter(is_deleted=False):
                    bom_items = ProjectBOM.objects.filter(
                        project=instance.project,
                        item=pr_line.item,
                        is_deleted=False,
                        order_status='NOT_ORDERED'  # 只更新未下单的
                    )
                    for bom in bom_items:
                        bom.order_status = 'PR_PENDING'
                        bom.purchase_request = instance
                        bom.pr_qty = (bom.pr_qty or 0) + pr_line.qty
                        bom.save(update_fields=['order_status', 'purchase_request', 'pr_qty'])
    
    def perform_destroy(self, instance):
        """删除采购申请时回退BOM状态（仅允许草稿/已拒绝状态删除）"""
        from rest_framework.exceptions import ValidationError as DRFValidationError
        from apps.projects.models import ProjectBOM

        if instance.status not in ('DRAFT', 'REJECTED'):
            raise DRFValidationError({'error': '只能删除草稿或已拒绝状态的采购申请'})

        # 回退关联BOM的状态：PR_PENDING/PR_APPROVED -> NOT_ORDERED
        with transaction.atomic():
            # 获取采购申请行中的物料
            pr_lines = instance.lines.filter(is_deleted=False)
            
            for pr_line in pr_lines:
                # 找到关联的BOM并回退状态
                if instance.project:
                    bom_items = ProjectBOM.objects.filter(
                        project=instance.project,
                        item=pr_line.item,
                        purchase_request=instance,
                        is_deleted=False,
                        order_status__in=['PR_PENDING', 'PR_APPROVED']
                    )
                    for bom in bom_items:
                        # 回退数量
                        bom.pr_qty = max(0, (bom.pr_qty or 0) - pr_line.qty)
                        # 如果没有其他采购申请，回退状态
                        if bom.pr_qty <= 0:
                            bom.order_status = 'NOT_ORDERED'
                            bom.purchase_request = None
                            bom.pr_qty = 0
                        bom.save(update_fields=['order_status', 'purchase_request', 'pr_qty'])
            
            # 调用父类的软删除
            super().perform_destroy(instance)
    
    @action(detail=False, methods=['get'])
    def check_budget(self, request):
        """
        Check budget for a project before creating purchase request.
        Query params: project_id, amount
        """
        project_id = request.query_params.get('project_id')
        amount = request.query_params.get('amount', 0)
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            amount = 0
        
        if not project_id:
            return Response({
                'valid': True,
                'message': '未选择项目，无需预算校验'
            })
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {'error': '项目不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = BudgetValidationService.validate_purchase_request(project, amount)
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def project_budget_summary(self, request):
        """Get budget summary for a project."""
        project_id = request.query_params.get('project_id')
        
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
        
        summary = BudgetValidationService.get_project_budget_summary(project)
        return Response(summary)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit PR for approval with budget validation and workflow."""
        pr = self.get_object()
        if pr.status != 'DRAFT':
            return Response(
                {'error': '只能提交草稿状态的申请'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Budget validation
        budget_warning = None
        if pr.project:
            budget_result = BudgetValidationService.validate_purchase_request(
                pr.project, pr.total_amount
            )
            if not budget_result['valid']:
                budget_warning = budget_result['message']
        
        # Try to start workflow
        try:
            from apps.core.workflow.services import WorkflowService
            
            instance, error = WorkflowService.start_workflow(
                business_type='PURCHASE_REQUEST',
                business_id=pr.id,
                business_no=pr.request_no,
                submitter=request.user,
                amount=pr.total_amount
            )
            
            if instance:
                pr.status = 'SUBMITTED'
                pr.save()
                response_data = {
                    **PurchaseRequestSerializer(pr).data,
                    'workflow_started': True,
                    'workflow_id': instance.id
                }
                if budget_warning:
                    response_data['budget_warning'] = budget_warning
                    response_data['over_budget'] = True
                return Response(response_data)
            else:
                # No workflow configured, auto-approve
                pr.status = 'APPROVED'
                pr.save()
                logger.info(f'采购申请 {pr.request_no} 自动批准（未配置审批流程）')
                
                # 更新BOM状态
                from apps.projects.models import ProjectBOM
                ProjectBOM.objects.filter(
                    purchase_request=pr,
                    is_deleted=False,
                    order_status='PR_PENDING'
                ).update(order_status='PR_APPROVED')
                
                response_data = {
                    **PurchaseRequestSerializer(pr).data,
                    'workflow_started': False,
                    'auto_approved': True,
                    'message': error or '未配置审批流程，已自动批准'
                }
                if budget_warning:
                    response_data['budget_warning'] = budget_warning
                return Response(response_data)
                
        except Exception as e:
            # 工作流服务异常不应自动批准，避免绕过审批；返回错误让用户重试
            logger.error(f'工作流服务异常，采购申请 {pr.request_no} 提交失败: {e}')
            return Response(
                {'error': f'工作流服务异常，提交失败，请稍后重试: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve PR - 如有活跃工作流则自动通过工作流审批."""
        pr = self.get_object()
        if pr.status != 'SUBMITTED':
            return Response(
                {'error': '只能批准已提交的申请'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 如果有活跃工作流，自动通过工作流任务审批
        has_wf, wf_instance = self.has_active_workflow(pr)
        if has_wf and wf_instance:
            pending_task = wf_instance.tasks.filter(
                status='PENDING', is_deleted=False
            ).order_by('step__step_order').first()
            if pending_task:
                success, msg = WorkflowService.approve_task(
                    pending_task, request.user, request.data.get('comment', ''),
                    skip_assignee_check=True
                )
                if success:
                    pr.refresh_from_db()
                    return Response(PurchaseRequestSerializer(pr).data)
                else:
                    return Response(
                        {'error': msg},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        with transaction.atomic():
            pr.status = 'APPROVED'
            pr.save()
            
            # 更新BOM状态：PR_PENDING -> PR_APPROVED
            from apps.projects.models import ProjectBOM
            ProjectBOM.objects.filter(
                purchase_request=pr,
                is_deleted=False,
                order_status='PR_PENDING'
            ).update(order_status='PR_APPROVED')
        
        return Response(PurchaseRequestSerializer(pr).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject PR - 如有活跃工作流则自动通过工作流拒绝."""
        pr = self.get_object()
        if pr.status != 'SUBMITTED':
            return Response(
                {'error': '只能拒绝已提交的申请'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 如果有活跃工作流，自动通过工作流任务拒绝
        has_wf, wf_instance = self.has_active_workflow(pr)
        if has_wf and wf_instance:
            pending_task = wf_instance.tasks.filter(
                status='PENDING', is_deleted=False
            ).order_by('step__step_order').first()
            if pending_task:
                comment = request.data.get('comment', '管理员拒绝')
                success, msg = WorkflowService.reject_task(
                    pending_task, request.user, comment,
                    skip_assignee_check=True
                )
                if success:
                    pr.refresh_from_db()
                    return Response(PurchaseRequestSerializer(pr).data)
                else:
                    return Response(
                        {'error': msg},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        pr.status = 'REJECTED'
        pr.save()
        return Response(PurchaseRequestSerializer(pr).data)
    
    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """Withdraw/Revoke submitted PR - 反审/撤回采购申请."""
        pr = self.get_object()
        if pr.status not in ['SUBMITTED', 'APPROVED']:
            return Response(
                {'error': '只能撤回已提交或已批准的申请'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            pr.status = 'DRAFT'
            pr.save()
            
            # 回退BOM状态：PR_APPROVED -> PR_PENDING
            from apps.projects.models import ProjectBOM
            ProjectBOM.objects.filter(
                purchase_request=pr,
                is_deleted=False,
                order_status='PR_APPROVED'
            ).update(order_status='PR_PENDING')
        
        # 尝试取消工作流
        try:
            from apps.core.workflow.services import WorkflowService
            WorkflowService.cancel_workflow(
                business_type='PURCHASE_REQUEST',
                business_id=pr.id
            )
        except Exception:
            pass
        
        return Response({
            **PurchaseRequestSerializer(pr).data,
            'message': '采购申请已撤回'
        })
    
    @action(detail=True, methods=['post'])
    def convert_to_po(self, request, pk=None):
        """Convert PR to PO."""
        supplier_id = request.data.get('supplier')
        if not supplier_id:
            return Response(
                {'error': '请选择供应商'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if SupplierBlacklist.is_blacklisted(supplier_id):
            return Response(
                {'error': '该供应商已被列入黑名单，不能转换为采购订单'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # 锁定 PR 并原子地校验状态，避免并发双击生成两个 PO
            pr = PurchaseRequest.objects.select_for_update().get(pk=self.get_object().pk)
            if pr.status != 'APPROVED':
                return Response(
                    {'error': '只能转换已批准的申请'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            po = PurchaseOrder.objects.create(
                supplier_id=supplier_id,
                project=pr.project,
                delivery_date=pr.required_date,
                tax_rate=pr.tax_rate,  # 继承申请税率，避免含税总额口径变化
                created_by=request.user
            )

            for pr_line in pr.lines.filter(is_deleted=False):
                PurchaseOrderLine.objects.create(
                    po=po,
                    item=pr_line.item,
                    qty=pr_line.qty,
                    unit_price=pr_line.estimated_price,
                    # 继承 BOM/关键件/长周期/功能模块/交期/备注
                    bom_item=pr_line.bom_item,
                    is_critical=pr_line.is_critical,
                    is_long_lead=pr_line.is_long_lead,
                    function_module=pr_line.function_module,
                    notes=pr_line.notes,
                    created_by=request.user
                )

            # 关联BOM到采购订单（但状态保持PR_APPROVED，等订单确认时再变为ORDERED）
            if pr.project:
                from apps.projects.models import ProjectBOM
                for pr_line in pr.lines.filter(is_deleted=False):
                    bom_items = ProjectBOM.objects.filter(
                        project=pr.project,
                        item=pr_line.item,
                        is_deleted=False,
                        order_status__in=['PR_PENDING', 'PR_APPROVED']
                    )
                    for bom in bom_items:
                        bom.purchase_order = po  # 先关联订单，但状态不变
                        bom.save(update_fields=['purchase_order'])

            # Update total amount and tax
            total = po.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            po.total_amount = total
            po.tax_amount = total * po.tax_rate / 100
            po.total_with_tax = total + po.tax_amount
            po.save()

            pr.status = 'CONVERTED'
            pr.save()

        return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """
        导入采购申请（从物料需求清单导入，直接生成采购申请）
        支持按供应商自动拆分成多个采购申请
        增加项目校验：检查Excel中的项目号是否与用户选择的项目一致
        """
        import pandas as pd
        from io import BytesIO
        from apps.masterdata.models import Item, Supplier
        from django.db.models import Q
        
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': '请上传Excel文件'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取用户选择的项目ID（可选，但建议选择）
        selected_project_id = request.data.get('project')
        selected_project = None
        if selected_project_id:
            try:
                selected_project = Project.objects.get(id=selected_project_id, is_deleted=False)
            except Project.DoesNotExist:
                return Response(
                    {'error': '选择的项目不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            # 读取Excel，智能识别列标题行
            df_raw = pd.read_excel(file, header=None)
            
            # 查找包含"物料编码"的行作为列标题行
            header_row = None
            for idx, row in df_raw.iterrows():
                row_values = [str(v) for v in row.values if pd.notna(v)]
                if any('物料编码' in v for v in row_values):
                    header_row = idx
                    break
            
            if header_row is not None:
                file.seek(0)
                df = pd.read_excel(file, header=header_row)
            else:
                file.seek(0)
                df = pd.read_excel(file)
        except Exception as e:
            return Response(
                {'error': f'Excel文件读取失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 查找列
        def find_column(df, keywords):
            for col in df.columns:
                col_str = str(col)
                for keyword in keywords:
                    if keyword in col_str:
                        return col
            return None
        
        sku_column = find_column(df, ['物料编码', 'SKU', '编码'])
        qty_column = find_column(df, ['数量'])
        supplier_column = find_column(df, ['供应商'])
        price_column = find_column(df, ['单价'])
        payment_method_column = find_column(df, ['付款方式'])
        payment_terms_column = find_column(df, ['账期'])
        project_column = find_column(df, ['项目号', '项目'])
        notes_column = find_column(df, ['备注'])
        
        if not sku_column:
            return Response(
                {'error': 'Excel文件必须包含"物料编码"列'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not qty_column:
            return Response(
                {'error': 'Excel文件必须包含"数量"列'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 第一遍：校验项目号
        project_mismatch_rows = []
        excel_project_codes = set()  # 收集Excel中的所有项目号
        
        if selected_project and project_column:
            for idx, row in df.iterrows():
                row_num = idx + 2 + (header_row or 0)
                
                sku = str(row[sku_column]).strip() if pd.notna(row[sku_column]) else ''
                if not sku or sku.startswith('(') or '示例' in sku:
                    continue
                
                excel_project_code = str(row[project_column]).strip() if pd.notna(row.get(project_column)) else ''
                if excel_project_code:
                    excel_project_codes.add(excel_project_code)
                    
                    # 检查项目号是否匹配
                    if excel_project_code != selected_project.code and excel_project_code != selected_project.name:
                        project_mismatch_rows.append({
                            'row': row_num,
                            'sku': sku,
                            'excel_project': excel_project_code,
                            'selected_project': f'{selected_project.code} ({selected_project.name})'
                        })
        
        # 如果有项目号不匹配，返回详细错误
        if project_mismatch_rows:
            mismatch_count = len(project_mismatch_rows)
            # 显示前5条不匹配记录
            sample_errors = project_mismatch_rows[:5]
            error_details = [
                f"行{e['row']}: 物料{e['sku']}的项目号是「{e['excel_project']}」，但您选择的是「{e['selected_project']}」"
                for e in sample_errors
            ]
            
            return Response({
                'error': f'项目号不匹配：Excel中有 {mismatch_count} 条记录的项目号与您选择的项目不一致',
                'details': error_details,
                'excel_projects': list(excel_project_codes),
                'selected_project': f'{selected_project.code} ({selected_project.name})' if selected_project else None,
                'suggestion': f'Excel中包含的项目号有：{", ".join(excel_project_codes)}。请确认选择正确的项目后重新导入。'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 按供应商分组数据
        supplier_groups = {}  # {supplier_name: [lines]}
        error_rows = []
        
        for idx, row in df.iterrows():
            row_num = idx + 2 + (header_row or 0)
            
            sku = str(row[sku_column]).strip() if pd.notna(row[sku_column]) else ''
            if not sku:
                continue  # 跳过空行
            
            # 跳过示例行
            if sku.startswith('(') or '示例' in sku:
                continue
            
            # 查找物料
            try:
                item = Item.objects.get(sku=sku, is_deleted=False)
            except Item.DoesNotExist:
                error_rows.append({'row': row_num, 'sku': sku, 'error': f'物料 {sku} 不存在'})
                continue
            
            # 获取数量
            try:
                qty = float(row[qty_column]) if pd.notna(row[qty_column]) else 0
                if qty <= 0:
                    error_rows.append({'row': row_num, 'sku': sku, 'error': '数量必须大于0'})
                    continue
            except (ValueError, TypeError):
                error_rows.append({'row': row_num, 'sku': sku, 'error': '数量格式错误'})
                continue
            
            # 获取供应商
            supplier_name = str(row[supplier_column]).strip() if supplier_column and pd.notna(row.get(supplier_column)) else ''
            if not supplier_name:
                supplier_name = '未指定供应商'
            
            # 获取单价
            try:
                price = float(row[price_column]) if price_column and pd.notna(row.get(price_column)) else 0
            except (ValueError, TypeError):
                price = 0
            
            # 项目：优先使用用户选择的项目，否则从Excel中读取
            project = selected_project
            if not project and project_column:
                project_code = str(row[project_column]).strip() if pd.notna(row.get(project_column)) else ''
                if project_code:
                    project = Project.objects.filter(
                        Q(code=project_code) | Q(name__icontains=project_code),
                        is_deleted=False
                    ).first()
            
            # 获取备注
            notes = str(row[notes_column]).strip() if notes_column and pd.notna(row.get(notes_column)) else ''
            
            # 获取付款方式和账期
            payment_method = str(row[payment_method_column]).strip() if payment_method_column and pd.notna(row.get(payment_method_column)) else ''
            payment_terms = str(row[payment_terms_column]).strip() if payment_terms_column and pd.notna(row.get(payment_terms_column)) else ''
            
            # 加入分组
            if supplier_name not in supplier_groups:
                supplier_groups[supplier_name] = {
                    'supplier_name': supplier_name,
                    'project': project,
                    'payment_method': payment_method,
                    'payment_terms': payment_terms,
                    'lines': []
                }
            
            supplier_groups[supplier_name]['lines'].append({
                'item': item,
                'qty': qty,
                'price': price,
                'notes': notes
            })
        
        if not supplier_groups:
            return Response(
                {'error': '没有可导入的有效数据', 'errors': error_rows},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 创建采购申请
        created_prs = []
        with transaction.atomic():
            from datetime import date, timedelta
            
            for supplier_name, group_data in supplier_groups.items():
                # 查找供应商
                supplier = None
                if supplier_name != '未指定供应商':
                    supplier = Supplier.objects.filter(
                        Q(name__icontains=supplier_name) | Q(code__icontains=supplier_name),
                        is_deleted=False
                    ).first()
                
                # 创建采购申请
                pr = PurchaseRequest.objects.create(
                    project=group_data['project'],
                    supplier=supplier,
                    requestor=request.user,
                    required_date=date.today() + timedelta(days=14),
                    status='DRAFT',
                    notes=f"从Excel导入，供应商: {supplier_name}",
                    created_by=request.user
                )
                
                # 创建采购申请明细
                total_amount = 0
                updated_bom_ids = []
                for line_data in group_data['lines']:
                    line = PurchaseRequestLine.objects.create(
                        pr=pr,
                        item=line_data['item'],
                        qty=line_data['qty'],
                        estimated_price=line_data['price'],
                        project=group_data['project'],
                        notes=line_data['notes'],
                        created_by=request.user
                    )
                    total_amount += line.line_amount
                    
                    # 更新对应BOM的采购状态
                    if group_data['project']:
                        from apps.projects.models import ProjectBOM
                        bom_items = ProjectBOM.objects.filter(
                            project=group_data['project'],
                            item=line_data['item'],
                            is_deleted=False,
                            order_status='NOT_ORDERED'  # 只更新未下单的
                        )
                        for bom in bom_items:
                            bom.order_status = 'PR_PENDING'
                            bom.purchase_request = pr
                            bom.pr_qty = (bom.pr_qty or 0) + line_data['qty']
                            bom.save(update_fields=['order_status', 'purchase_request', 'pr_qty'])
                            updated_bom_ids.append(bom.id)
                
                # 更新采购申请总金额
                pr.total_amount = total_amount
                pr.tax_amount = total_amount * pr.tax_rate / 100
                pr.total_with_tax = total_amount + pr.tax_amount
                pr.save()
                
                created_prs.append({
                    'id': pr.id,
                    'request_no': pr.request_no,
                    'supplier_name': supplier_name,
                    'project_name': group_data['project'].name if group_data['project'] else '无项目',
                    'lines_count': len(group_data['lines']),
                    'total_amount': float(pr.total_with_tax),
                    'updated_bom_count': len(updated_bom_ids)
                })
        
        return Response({
            'message': f'导入成功，共创建 {len(created_prs)} 个采购申请',
            'created_count': len(created_prs),
            'purchase_requests': created_prs,
            'errors': error_rows,
            'project': selected_project.name if selected_project else None
        })
    
    @action(detail=False, methods=['get'])
    def export_template(self, request):
        """
        导出采购申请导入模板
        """
        import pandas as pd
        from io import BytesIO
        from django.http import HttpResponse
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            worksheet = workbook.add_worksheet('采购申请导入模板')
            
            # Define formats
            required_format = workbook.add_format({
                'bold': True,
                'bg_color': '#C00000',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            optional_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            example_format = workbook.add_format({
                'bg_color': '#FFF2CC',
                'border': 1,
                'italic': True,
                'font_color': '#666666'
            })
            
            headers = [
                ('项目号', 12, 'optional'),
                ('物料编码*', 15, 'required'),
                ('物料名称', 20, 'optional'),
                ('规格型号', 15, 'optional'),
                ('单位', 8, 'optional'),
                ('数量*', 10, 'required'),
                ('供应商', 18, 'optional'),
                ('单价', 12, 'optional'),
                ('付款方式', 12, 'optional'),
                ('账期', 12, 'optional'),
                ('备注', 25, 'optional'),
            ]
            
            format_map = {
                'required': required_format,
                'optional': optional_format
            }
            
            for col, (header, width, htype) in enumerate(headers):
                fmt = format_map[htype]
                worksheet.write(0, col, header, fmt)
                worksheet.set_column(col, col, width)
            
            # 示例数据
            example = [
                'PJ2601', '1126000001', '示例物料', 'ABC-100', 'PCS', 
                10, '示例供应商', 100.00, '电汇', '月结30天', '备注信息'
            ]
            for col, val in enumerate(example):
                worksheet.write(1, col, val, example_format)
            
            worksheet.set_row(0, 25)
            worksheet.freeze_panes(1, 0)
        
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=purchase_request_import_template.xlsx'
        return response


class PurchaseRequestLineViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseRequestLine management.
    """
    queryset = PurchaseRequestLine.objects.all()
    serializer_class = PurchaseRequestLineSerializer
    filterset_fields = ['pr', 'item', 'project', 'is_deleted']

    permission_module = 'purchase'
    permission_resource = 'request_line'
    search_fields = ['item__sku', 'item__name']


class PurchaseOrderViewSet(PermissionMixin, WorkflowEnforcementMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseOrder management.
    """
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    filterset_fields = ['supplier', 'project', 'status', 'is_deleted']
    search_fields = ['order_no']
    ordering_fields = ['order_date', 'created_at']
    
    # Workflow configuration
    workflow_business_type = 'PURCHASE_ORDER'
    workflow_amount_field = 'total_with_tax'  # 优先使用含税金额
    workflow_no_field = 'order_no'
    
    # Permission configuration
    permission_module = 'purchase'
    permission_resource = 'purchase_order'

    def perform_create(self, serializer):
        # 黑名单供应商不允许下采购订单（审计 medium：黑名单原先无任何采购拦截）
        supplier = serializer.validated_data.get('supplier')
        if SupplierBlacklist.is_blacklisted(supplier):
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({'supplier': '该供应商已被列入黑名单，不能创建采购订单'})
        super().perform_create(serializer)

    def perform_destroy(self, instance):
        """删除守卫：只允许草稿/已拒绝/已取消订单删除，且不得有收货/应付账款残留。"""
        from rest_framework.exceptions import ValidationError as DRFValidationError
        if instance.status not in ('DRAFT', 'REJECTED', 'CANCELLED'):
            raise DRFValidationError({'error': '只能删除草稿、已拒绝或已取消状态的采购订单'})
        # 有收货单则禁止删除，避免下游收货单/库存孤儿
        if GoodsReceipt.objects.filter(po=instance, is_deleted=False).exists():
            raise DRFValidationError({'error': '该订单已有收货记录，不能删除'})
        # 有未删除应付账款则禁止删除
        from apps.finance.models import AccountPayable
        if AccountPayable.objects.filter(po=instance, is_deleted=False).exists():
            raise DRFValidationError({'error': '该订单已有应付账款，请先撤销后再删除'})
        super().perform_destroy(instance)

    @action(detail=False, methods=['get'])
    def for_linking(self, request):
        """获取可用于关联的采购订单（不受数据权限限制）"""
        from django.db import models as db_models
        queryset = PurchaseOrder.objects.filter(is_deleted=False).order_by('-created_at')
        
        # 支持搜索
        search = request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(
                db_models.Q(order_no__icontains=search) |
                db_models.Q(supplier__name__icontains=search)
            )
        
        # 简化返回数据
        data = [{
            'id': po.id,
            'order_no': po.order_no,
            'supplier': po.supplier_id,
            'supplier_name': po.supplier.name if po.supplier else '',
            'project': po.project_id,
            'project_name': po.project.name if po.project else '',
            'status': po.status,
            'total_amount': float(po.total_amount or 0),
            'total_with_tax': float(po.total_with_tax or 0),
        } for po in queryset[:100]]  # 限制返回数量
        
        return Response(data)

    def update(self, request, *args, **kwargs):
        """只允许草稿或已拒绝状态的采购订单修改明细"""
        instance = self.get_object()
        if instance.status not in ['DRAFT', 'REJECTED']:
            return Response(
                {'error': '只有草稿或已拒绝的订单可以修改'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交采购订单审批 - 审批步骤由流程配置决定"""
        po = self.get_object()
        if po.status not in ['DRAFT', 'REJECTED']:
            return Response(
                {'error': '只能提交草稿或已拒绝状态的采购订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = po.total_with_tax or po.total_amount or 0
        
        try:
            from apps.core.workflow.services import WorkflowService
            
            instance, error = WorkflowService.start_workflow(
                business_type='PURCHASE_ORDER',
                business_id=po.id,
                business_no=po.order_no,
                submitter=request.user,
                amount=amount
            )
            
            if instance:
                po.status = 'PENDING'
                po.save()
                return Response({
                    **PurchaseOrderSerializer(po).data,
                    'workflow_started': True,
                    'workflow_id': instance.id,
                    'message': '已提交审批，请在审批中心查看审批进度'
                })
            else:
                # 未配置审批流程，直接确认 —— 复用完整确认副作用(创建AP/付款计划/更新BOM)
                schedules = self._apply_confirm_side_effects(po, request.user, request.data)
                return Response({
                    **PurchaseOrderSerializer(po).data,
                    'workflow_started': False,
                    'payment_schedules_count': len(schedules),
                    'message': error or '未配置审批流程，采购订单已直接确认'
                })

        except Exception as e:
            # 审批模块异常不应自动确认，避免跳过 AP 创建导致应付账款永久缺失
            logger.error(f'采购订单 {po.order_no} 提交时工作流服务异常: {e}')
            return Response(
                {'error': f'工作流服务异常，提交失败，请稍后重试: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _apply_confirm_side_effects(self, po, user, data=None):
        """确认采购订单的完整副作用：置 CONFIRMED、更新BOM、创建AP与付款计划。返回付款计划列表。"""
        data = data or {}
        with transaction.atomic():
            po.status = 'CONFIRMED'
            po.save()

            # 更新BOM状态：PR_APPROVED -> ORDERED（订单确认时才真正"已下单"）
            from apps.projects.models import ProjectBOM
            if po.project:
                for po_line in po.lines.filter(is_deleted=False):
                    bom_items = ProjectBOM.objects.filter(
                        project=po.project,
                        item=po_line.item,
                        purchase_order=po,
                        is_deleted=False,
                        order_status__in=['PR_PENDING', 'PR_APPROVED']
                    )
                    for bom in bom_items:
                        bom.order_status = 'ORDERED'
                        bom.ordered_qty = (bom.ordered_qty or 0) + po_line.qty
                        bom.save(update_fields=['order_status', 'ordered_qty'])

            # Auto-create AP - 使用含税金额（避免重复创建）
            from apps.finance.models import AccountPayable, PurchasePaymentSchedule

            # 检查是否已存在该PO的应付账款
            existing_ap = AccountPayable.objects.filter(po=po, is_deleted=False).first()
            if not existing_ap:
                AccountPayable.objects.create(
                    supplier=po.supplier,
                    po=po,
                    project=po.project,
                    invoice_date=po.order_date,
                    amount_due=po.total_with_tax or po.total_amount,  # 优先使用含税金额
                    due_date=data.get('due_date', po.delivery_date),
                    created_by=user
                )

            # 自动生成付款计划（避免重复创建）
            existing_schedules = PurchasePaymentSchedule.objects.filter(purchase_order=po, is_deleted=False).exists()
            if existing_schedules:
                schedules = []
            else:
                schedules = PurchasePaymentSchedule.generate_from_purchase_order(po)
        return schedules

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm PO - 确认采购订单，此时BOM状态才变为已下单."""
        po = self.get_object()
        if po.status not in ['DRAFT', 'APPROVED']:
            return Response(
                {'error': '只能确认草稿或已审批状态的订单'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 检查是否有活跃工作流（PENDING状态时需要通过工作流确认）
        workflow_error = self.check_workflow_allows_direct_action(po, '确认')
        if workflow_error:
            return workflow_error

        schedules = self._apply_confirm_side_effects(po, request.user, request.data)

        response_data = PurchaseOrderSerializer(po).data
        response_data['payment_schedules_count'] = len(schedules)

        return Response(response_data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel PO."""
        po = self.get_object()
        if po.status in ['COMPLETED', 'CANCELLED']:
            return Response(
                {'error': '无法取消已完成或已取消的订单'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 已有确认收货则禁止直接取消（应先退货冲销，避免库存/应付账实分离）
        has_receipts = GoodsReceipt.objects.filter(po=po, status='CONFIRMED', is_deleted=False).exists()
        if has_receipts:
            return Response(
                {'error': '该订单已有确认收货记录，请先退货冲销后再取消'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            po.status = 'CANCELLED'
            po.save()

            # 撤销关联的应付账款与付款计划（与 withdraw 一致），避免取消后财务仍全额挂账
            from apps.finance.models import AccountPayable, PurchasePaymentSchedule
            AccountPayable.objects.filter(po=po, is_deleted=False).update(is_deleted=True)
            PurchasePaymentSchedule.objects.filter(purchase_order=po, is_deleted=False).update(is_deleted=True)

            # 回退BOM状态：ORDERED -> CANCELLED
            from apps.projects.models import ProjectBOM
            ProjectBOM.objects.filter(
                purchase_order=po,
                is_deleted=False,
                order_status='ORDERED'
            ).update(order_status='CANCELLED')

        return Response(PurchaseOrderSerializer(po).data)
    
    @action(detail=True, methods=['post'])
    def mark_shipped(self, request, pk=None):
        """标记为已发货 - 供应商发货通知，更新BOM为在途状态."""
        po = self.get_object()
        if po.status not in ['CONFIRMED', 'PARTIAL']:
            return Response(
                {'error': '只能标记已确认或部分收货状态的订单为已发货'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取发货数量（可选，默认为订单全部数量）
        shipped_items = request.data.get('items', [])
        
        with transaction.atomic():
            from apps.projects.models import ProjectBOM
            
            if shipped_items:
                # 按明细发货
                for item_data in shipped_items:
                    item_id = item_data.get('item')
                    shipped_qty = item_data.get('qty', 0)
                    
                    if po.project and item_id and shipped_qty > 0:
                        bom_items = ProjectBOM.objects.filter(
                            project=po.project,
                            item_id=item_id,
                            purchase_order=po,
                            is_deleted=False,
                            order_status='ORDERED'
                        )
                        for bom in bom_items:
                            bom.order_status = 'IN_TRANSIT'
                            bom.shipped_qty = (bom.shipped_qty or 0) + shipped_qty
                            bom.save(update_fields=['order_status', 'shipped_qty'])
            else:
                # 整单发货
                if po.project:
                    for po_line in po.lines.filter(is_deleted=False):
                        bom_items = ProjectBOM.objects.filter(
                            project=po.project,
                            item=po_line.item,
                            purchase_order=po,
                            is_deleted=False,
                            order_status='ORDERED'
                        )
                        for bom in bom_items:
                            bom.order_status = 'IN_TRANSIT'
                            bom.shipped_qty = (bom.shipped_qty or 0) + po_line.qty
                            bom.save(update_fields=['order_status', 'shipped_qty'])
        
        return Response({
            'message': '已标记为发货',
            **PurchaseOrderSerializer(po).data
        })
    
    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """Withdraw/Revoke confirmed PO - 反审/撤回采购订单."""
        po = self.get_object()
        if po.status not in ['CONFIRMED']:
            return Response(
                {'error': '只能撤回已确认的订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查是否有任何未删除收货单（含草稿）——草稿收货单 PROTECT 引用订单明细，
        # 撤回后编辑会硬删明细触发 ProtectedError 500，故一并拦截
        has_receipts = GoodsReceipt.objects.filter(po=po, is_deleted=False).exists()
        if has_receipts:
            return Response(
                {'error': '该订单已有收货单（含草稿），请先删除收货单后再撤回'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # 删除关联的应付账款
            from apps.finance.models import AccountPayable, PurchasePaymentSchedule
            AccountPayable.objects.filter(po=po, is_deleted=False).update(is_deleted=True)
            
            # 删除付款计划
            PurchasePaymentSchedule.objects.filter(purchase_order=po, is_deleted=False).update(is_deleted=True)
            
            # 回退BOM状态：ORDERED -> PR_APPROVED (有采购申请) 或 NOT_ORDERED (无采购申请)
            from apps.projects.models import ProjectBOM
            bom_items = ProjectBOM.objects.filter(
                purchase_order=po,
                is_deleted=False,
                order_status='ORDERED'
            )
            for bom in bom_items:
                if bom.purchase_request:
                    bom.order_status = 'PR_APPROVED'
                else:
                    bom.order_status = 'NOT_ORDERED'
                bom.purchase_order = None
                bom.ordered_qty = 0
                bom.save(update_fields=['order_status', 'purchase_order', 'ordered_qty'])
            
            po.status = 'DRAFT'
            po.save()
        
        return Response({
            **PurchaseOrderSerializer(po).data,
            'message': '采购订单已撤回至草稿状态'
        })


class PurchaseOrderLineViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseOrderLine management.
    """
    queryset = PurchaseOrderLine.objects.all()
    serializer_class = PurchaseOrderLineSerializer
    filterset_fields = ['po', 'item', 'is_deleted']

    permission_module = 'purchase'
    permission_resource = 'order_line'
    search_fields = ['item__sku', 'item__name']


class GoodsReceiptViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for GoodsReceipt management.
    """
    queryset = GoodsReceipt.objects.all()
    serializer_class = GoodsReceiptSerializer
    filterset_fields = ['po', 'warehouse', 'status', 'is_deleted']
    search_fields = ['receipt_no']
    ordering_fields = ['receipt_date', 'created_at']

    permission_module = 'purchase'
    permission_resource = 'goods_receipt'

    def perform_destroy(self, instance):
        """只允许删除草稿收货单；已确认收货单须先退货冲销，避免账实分离。"""
        if instance.status != 'DRAFT':
            from rest_framework.exceptions import ValidationError as DRFValidationError
            raise DRFValidationError({'error': '只能删除草稿状态的收货单，已确认收货单请先退货冲销'})
        super().perform_destroy(instance)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm goods receipt and create stock moves with FIFO support."""
        receipt = self.get_object()
        if receipt.status != 'DRAFT':
            return Response(
                {'error': '只能确认草稿状态的收货单'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # PO 状态前置校验：只能对已确认/部分收货的订单确认收货（防止把已取消订单顶回 PARTIAL）
        if receipt.po.status not in ('CONFIRMED', 'PARTIAL'):
            return Response(
                {'error': '只能对已确认或部分收货状态的采购订单确认收货'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            from apps.inventory.models import StockMove
            from apps.projects.models import ProjectBOM
            from django.conf import settings

            costing_method = getattr(settings, 'INVENTORY_COSTING_METHOD', 'WEIGHTED_AVG')
            po = receipt.po

            # 服务端二次校验：剩余可收数量（防御绕过 serializer 直接调 confirm 的超收）
            for line in receipt.lines.filter(is_deleted=False):
                if line.quality_status == 'FAILED':
                    continue
                remaining = float(line.po_line.qty) - float(line.po_line.received_qty)
                if float(line.qty) > remaining:
                    return Response(
                        {'error': f'物料 {line.item.sku} 超收：剩余可收 {remaining}，本次 {line.qty}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            for line in receipt.lines.filter(is_deleted=False):
                # 不合格品(FAILED)不入库、不计入已收数量，须走退货/让步流程处理
                if line.quality_status == 'FAILED':
                    continue
                # Create stock move for receipt
                StockMove.objects.create(
                    item=line.item,
                    warehouse_to=receipt.warehouse,
                    qty=line.qty,
                    unit_cost=line.po_line.unit_price,
                    move_type='IN_PURCHASE',
                    reference_type='GoodsReceipt',
                    reference_id=receipt.id,
                    move_date=receipt.receipt_date,
                    status='COMPLETED',
                    created_by=request.user
                )
                
                # If using FIFO, also create inventory lot
                if costing_method == 'FIFO':
                    FIFOCostingService.record_purchase(
                        warehouse=receipt.warehouse,
                        item=line.item,
                        qty=line.qty,
                        unit_cost=line.po_line.unit_price,
                        reference_type='GoodsReceipt',
                        reference_id=receipt.id
                    )
                
                # Update received qty on PO line (F() for concurrency safety)
                from django.db.models import F as DbF
                from apps.purchase.models import PurchaseOrderLine
                PurchaseOrderLine.objects.filter(pk=line.po_line_id).update(
                    received_qty=DbF('received_qty') + line.qty
                )
                line.po_line.refresh_from_db()
                
                # 更新BOM的收货数量和状态
                if po.project:
                    bom_items = ProjectBOM.objects.filter(
                        project=po.project,
                        item=line.item,
                        purchase_order=po,
                        is_deleted=False,
                        order_status__in=['ORDERED', 'IN_TRANSIT', 'PARTIAL_RECEIVED']
                    )
                    for bom in bom_items:
                        bom.received_qty = (bom.received_qty or 0) + line.qty
                        # 根据收货数量更新状态
                        if bom.received_qty >= bom.planned_qty:
                            bom.order_status = 'RECEIVED'
                        else:
                            bom.order_status = 'PARTIAL_RECEIVED'
                        bom.save(update_fields=['received_qty', 'order_status'])
            
            receipt.status = 'CONFIRMED'
            receipt.save()
            
            # Check if PO is fully received
            all_received = all(
                line.received_qty >= line.qty
                for line in po.lines.filter(is_deleted=False)
            )
            if all_received:
                po.status = 'COMPLETED'
            else:
                po.status = 'PARTIAL'
            po.save()
        
        return Response(GoodsReceiptSerializer(receipt).data)
    
    @action(detail=True, methods=['post'])
    def return_goods(self, request, pk=None):
        """退货 - 创建退货记录并更新BOM状态."""
        receipt = self.get_object()
        if receipt.status != 'CONFIRMED':
            return Response(
                {'error': '只能对已确认的收货单进行退货'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取退货明细
        return_items = request.data.get('items', [])
        return_reason = request.data.get('reason', '')
        
        if not return_items:
            return Response(
                {'error': '请提供退货明细'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            from apps.projects.models import ProjectBOM
            from apps.inventory.models import StockMove
            from django.db.models import F as DbF

            po = receipt.po
            returned_count = 0

            # 该收货单本身的合格收货行（按 po_line 归集，退货上限以收货行已收数量为准）
            receipt_lines = {
                rl.po_line_id: rl
                for rl in receipt.lines.filter(is_deleted=False).exclude(quality_status='FAILED')
            }

            for item_data in return_items:
                item_id = item_data.get('item')
                po_line_id = item_data.get('po_line')
                return_qty = float(item_data.get('qty', 0) or 0)

                if not item_id or return_qty <= 0:
                    continue

                # 退货必须对应本收货单的收货行，且数量不得超过该行已收数量
                receipt_line = None
                if po_line_id:
                    receipt_line = receipt_lines.get(po_line_id)
                if receipt_line is None:
                    # 兼容仅传 item 的旧前端：按 item 匹配第一条收货行
                    receipt_line = next(
                        (rl for rl in receipt_lines.values() if rl.item_id == int(item_id)), None
                    )
                if receipt_line is None:
                    return Response(
                        {'error': f'物料 {item_id} 不在该收货单的收货明细中，无法退货'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if return_qty > float(receipt_line.qty):
                    return Response(
                        {'error': f'退货数量超过该收货行收货数量({receipt_line.qty})'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # 退货不得超过 PO 行当前已收数量
                if return_qty > float(receipt_line.po_line.received_qty):
                    return Response(
                        {'error': f'退货数量超过订单已收数量({receipt_line.po_line.received_qty})'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # 创建退货库存移动
                StockMove.objects.create(
                    item_id=item_id,
                    warehouse_from=receipt.warehouse,
                    qty=return_qty,
                    move_type='OUT_RETURN',
                    reference_type='GoodsReceipt',
                    reference_id=receipt.id,
                    move_date=request.data.get('return_date') or receipt.receipt_date,
                    status='COMPLETED',
                    notes=f'退货原因: {return_reason}',
                    created_by=request.user
                )

                # 回退 PO 行已收数量
                PurchaseOrderLine.objects.filter(pk=receipt_line.po_line_id).update(
                    received_qty=DbF('received_qty') - return_qty
                )

                # 更新BOM的退货数量和状态
                if po and po.project:
                    bom_items = ProjectBOM.objects.filter(
                        project=po.project,
                        item_id=item_id,
                        purchase_order=po,
                        is_deleted=False,
                        order_status__in=['RECEIVED', 'PARTIAL_RECEIVED']
                    )
                    for bom in bom_items:
                        bom.returned_qty = (bom.returned_qty or 0) + return_qty
                        bom.received_qty = max(0, (bom.received_qty or 0) - return_qty)
                        # 如果全部退货，状态变为已退货
                        if bom.received_qty <= 0:
                            bom.order_status = 'RETURNED'
                        bom.save(update_fields=['returned_qty', 'received_qty', 'order_status'])

                returned_count += 1

            # 回退 PO 状态：退货后若不再全部收齐则降为 PARTIAL
            po.refresh_from_db()
            po_lines = po.lines.filter(is_deleted=False)
            all_received = all(pl.received_qty >= pl.qty for pl in po_lines)
            any_received = any(pl.received_qty > 0 for pl in po_lines)
            if all_received:
                po.status = 'COMPLETED'
            elif any_received:
                po.status = 'PARTIAL'
            else:
                po.status = 'CONFIRMED'
            po.save(update_fields=['status'])

            # 更新收货单状态
            receipt.notes = f"{receipt.notes}\n退货记录: {return_reason}" if receipt.notes else f"退货记录: {return_reason}"
            receipt.save()

        return Response({
            'message': f'退货成功，共处理 {returned_count} 种物料',
            'returned_count': returned_count
        })


class GoodsReceiptLineViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for GoodsReceiptLine management.
    """
    permission_module = 'purchase'
    permission_resource = 'goods_receipt_line'

    queryset = GoodsReceiptLine.objects.all()
    serializer_class = GoodsReceiptLineSerializer
    filterset_fields = ['receipt', 'item', 'quality_status', 'is_deleted']
    search_fields = ['item__sku', 'item__name']


class PurchaseContractViewSet(PermissionMixin, WorkflowEnforcementMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseContract management.
    """
    queryset = PurchaseContract.objects.all()
    serializer_class = PurchaseContractSerializer
    filterset_fields = ['po', 'supplier', 'project', 'status', 'is_deleted']
    search_fields = ['contract_no', 'title']
    ordering_fields = ['contract_date', 'created_at']

    permission_module = 'purchase'
    permission_resource = 'contract'

    # Workflow configuration
    workflow_business_type = 'PURCHASE_CONTRACT'
    workflow_amount_field = 'total_amount'
    workflow_no_field = 'contract_no'
    
    @action(detail=False, methods=['post'])
    def create_from_po(self, request):
        """从采购订单创建合同."""
        po_id = request.data.get('po_id')
        if not po_id:
            return Response(
                {'error': '请选择采购订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            po = PurchaseOrder.objects.get(id=po_id, is_deleted=False)
        except PurchaseOrder.DoesNotExist:
            return Response(
                {'error': '采购订单不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查是否已有合同
        existing = PurchaseContract.objects.filter(po=po, is_deleted=False).first()
        if existing:
            return Response(
                {'error': f'该采购订单已存在合同: {existing.contract_no}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        
        contract = PurchaseContract.objects.create(
            po=po,
            supplier=po.supplier,
            project=po.project,
            title=f'{po.supplier.name}采购合同',
            contract_date=timezone.now().date(),
            total_amount=po.total_amount,
            tax_rate=po.tax_rate,
            tax_amount=po.tax_amount,
            total_with_tax=po.total_with_tax,
            payment_terms=self._get_payment_terms_text(po),
            delivery_terms=f'交货日期：{po.delivery_date}',
            created_by=request.user
        )
        
        return Response(PurchaseContractSerializer(contract).data, status=status.HTTP_201_CREATED)
    
    def _get_payment_terms_text(self, po):
        """生成付款条款文本."""
        terms_map = {
            'PREPAY': '预付款100%',
            'COD': '货到付款',
            'NET15': '货到后15天内付款',
            'NET30': '货到后30天内付款',
            'NET45': '货到后45天内付款',
            'NET60': '货到后60天内付款',
            'NET90': '货到后90天内付款',
            'NET120': '货到后120天内付款',
            'MILESTONE': '分期付款',
            'OTHER': '其他',
        }
        base_text = terms_map.get(po.payment_terms, '月结30天')
        if po.payment_terms_detail:
            base_text += f'（{po.payment_terms_detail}）'
        return base_text
    
    @action(detail=True, methods=['get'])
    def print_preview(self, request, pk=None):
        """获取合同打印预览数据."""
        contract = self.get_object()
        po = contract.po
        
        # 获取公司信息
        from apps.core.models import SystemConfig
        config = SystemConfig.get_config()
        
        # 获取订单明细
        lines = []
        for line in po.lines.filter(is_deleted=False):
            lines.append({
                'item_sku': line.item.sku,
                'item_name': line.item.name,
                'specification': line.item.specification or '',
                'unit': line.item.get_unit_display(),
                'qty': float(line.qty),
                'unit_price': float(line.unit_price),
                'line_amount': float(line.line_amount),
            })
        
        # 获取采购订单的付款条款
        payment_terms_display = ''
        if hasattr(po, 'payment_terms') and po.payment_terms:
            payment_terms_map = {
                'PREPAY': '预付款',
                'COD': '货到付款',
                'NET15': '月结15天',
                'NET30': '月结30天',
                'NET45': '月结45天',
                'NET60': '月结60天',
                'NET90': '月结90天',
                'NET120': '月结120天',
                'MILESTONE': '分期付款',
                'OTHER': '其他',
            }
            payment_terms_display = payment_terms_map.get(po.payment_terms, po.payment_terms)
        
        # 获取付款方式
        payment_method_display = ''
        if hasattr(po, 'payment_method') and po.payment_method:
            payment_method_map = {
                'WIRE': '电汇',
                'ACCEPTANCE': '承兑汇票',
                'CHECK': '支票',
                'CASH': '现金',
                'LC': '信用证',
                'OTHER': '其他',
            }
            payment_method_display = payment_method_map.get(po.payment_method, po.payment_method)
        
        return Response({
            'contract': PurchaseContractSerializer(contract).data,
            'company': {
                'name': config.company_name or '',
                'address': config.company_address or '',
                'phone': config.company_phone or '',
                'email': config.company_email or '',
                'tax_no': config.company_tax_no or '',
                'bank_name': config.bank_name or '',
                'bank_account': config.bank_account or '',
            },
            'supplier': {
                'name': contract.supplier.name,
                'address': contract.supplier.address or '',
                'contact': contract.supplier.contact_person or '',
                'phone': contract.supplier.phone or '',
                'email': contract.supplier.email or '' if hasattr(contract.supplier, 'email') else '',
                'tax_no': contract.supplier.tax_id or '' if hasattr(contract.supplier, 'tax_id') else '',
                'bank_name': contract.supplier.bank_name or '',
                'bank_account': contract.supplier.bank_account or '',
            },
            'po': {
                'order_no': po.order_no,
                'order_date': po.order_date.isoformat() if po.order_date else '',
                'delivery_date': po.delivery_date.isoformat() if po.delivery_date else '',
                'payment_terms': payment_terms_display,
                'payment_method': payment_method_display,
                'total_amount': float(po.total_amount) if po.total_amount else 0,
                'total_with_tax': float(po.total_with_tax) if po.total_with_tax else 0,
                'buyer_name': po.created_by.get_full_name() if po.created_by else '',
                'buyer_phone': '',
                'project_name': po.project.name if po.project else '',
                'notes': po.notes or '',
            },
            'lines': lines,
        })
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交采购合同审批."""
        contract = self.get_object()
        if contract.status not in ['DRAFT', 'REJECTED']:
            return Response(
                {'error': '只能提交草稿或已拒绝状态的合同'},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = self.start_workflow_or_auto_approve(
            contract, request.user,
            approved_status='APPROVED',
            submitted_status='PENDING'
        )
        contract.status = result['new_status']
        contract.save()
        return Response({
            **PurchaseContractSerializer(contract).data,
            'workflow_started': result['workflow_started'],
            'message': result['message'],
        })

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批合同 - 仅在无活跃工作流时允许直接审批."""
        contract = self.get_object()
        if contract.status not in ['DRAFT', 'PENDING']:
            return Response(
                {'error': '只能审批草稿或待审批状态的合同'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 检查是否有活跃工作流
        workflow_error = self.check_workflow_allows_direct_action(contract, '审批')
        if workflow_error:
            return workflow_error

        contract.status = 'APPROVED'
        contract.save()
        return Response(PurchaseContractSerializer(contract).data)
    
    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        """签署合同."""
        contract = self.get_object()
        if contract.status != 'APPROVED':
            return Response(
                {'error': '只能签署已审批的合同'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        
        contract.buyer_signer = request.data.get('buyer_signer', '')
        contract.seller_signer = request.data.get('seller_signer', '')
        contract.signed_date = timezone.now().date()
        contract.status = 'SIGNED'
        contract.save()
        return Response(PurchaseContractSerializer(contract).data)

