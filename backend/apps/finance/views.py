"""
Views for finance app.
"""
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum, F, Count
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.data_permission import DataPermissionMixin
from apps.projects.models import Project
from .models import (
    Currency, ExchangeRateHistory, Expense, Invoice,
    AccountReceivable, AccountPayable, Payment,
    SharedExpense, SharedExpenseAllocation
)
from .serializers import (
    CurrencySerializer, ExchangeRateHistorySerializer,
    ExpenseSerializer, InvoiceSerializer, AccountReceivableSerializer,
    AccountPayableSerializer, PaymentSerializer,
    SharedExpenseSerializer, SharedExpenseAllocationSerializer
)


class CurrencyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Currency management.
    """
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    filterset_fields = ['is_active', 'is_base_currency']
    search_fields = ['code', 'name']
    
    @action(detail=True, methods=['post'])
    def update_rate(self, request, pk=None):
        """Update exchange rate and record history."""
        currency = self.get_object()
        new_rate = request.data.get('exchange_rate')
        effective_date = request.data.get('effective_date', timezone.now().date())
        
        if not new_rate:
            return Response(
                {'error': '请提供汇率'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Record history
        ExchangeRateHistory.objects.create(
            currency=currency,
            exchange_rate=new_rate,
            effective_date=effective_date
        )
        
        # Update current rate
        currency.exchange_rate = new_rate
        currency.save()
        
        return Response(CurrencySerializer(currency).data)
    
    @action(detail=False, methods=['get'])
    def rate_history(self, request):
        """Get exchange rate history."""
        currency_code = request.query_params.get('currency')
        days = int(request.query_params.get('days', 30))
        
        from datetime import timedelta
        start_date = timezone.now().date() - timedelta(days=days)
        
        history = ExchangeRateHistory.objects.filter(
            effective_date__gte=start_date
        )
        
        if currency_code:
            history = history.filter(currency__code=currency_code)
        
        serializer = ExchangeRateHistorySerializer(history, many=True)
        return Response(serializer.data)


class PaymentViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for Payment management.
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filterset_fields = ['payment_type', 'payment_method', 'ar', 'ap']
    search_fields = ['payment_no']
    ordering_fields = ['payment_date', 'amount', 'created_at']


class ExpenseViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for Expense management.
    """
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    filterset_fields = ['project', 'department', 'user', 'category', 'status', 'is_deleted']
    search_fields = ['expense_no', 'description']
    ordering_fields = ['expense_date', 'amount', 'created_at']
    data_scope_field = 'user'
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit expense for approval with workflow."""
        expense = self.get_object()
        if expense.status != 'DRAFT':
            return Response(
                {'error': '只能提交草稿状态的报销单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to start workflow
        try:
            from apps.core.workflow.services import WorkflowService
            
            instance, error = WorkflowService.start_workflow(
                business_type='EXPENSE',
                business_id=expense.id,
                business_no=expense.expense_no,
                submitter=request.user,
                amount=expense.amount
            )
            
            if instance:
                expense.status = 'SUBMITTED'
                expense.save()
                return Response({
                    **ExpenseSerializer(expense).data,
                    'workflow_started': True,
                    'workflow_id': instance.id
                })
            else:
                # No workflow configured, just submit
                expense.status = 'SUBMITTED'
                expense.save()
                return Response({
                    **ExpenseSerializer(expense).data,
                    'workflow_started': False,
                    'message': error or '未配置审批流程，已直接提交'
                })
                
        except Exception as e:
            # Workflow module not available, fallback to simple submit
            expense.status = 'SUBMITTED'
            expense.save()
            return Response(ExpenseSerializer(expense).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve expense."""
        expense = self.get_object()
        if expense.status != 'SUBMITTED':
            return Response(
                {'error': '只能批准已提交的报销单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        expense.status = 'APPROVED'
        expense.save()
        return Response(ExpenseSerializer(expense).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject expense."""
        expense = self.get_object()
        if expense.status != 'SUBMITTED':
            return Response(
                {'error': '只能拒绝已提交的报销单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        expense.status = 'REJECTED'
        expense.save()
        return Response(ExpenseSerializer(expense).data)
    
    @action(detail=True, methods=['post'])
    def reimburse(self, request, pk=None):
        """Mark expense as reimbursed."""
        expense = self.get_object()
        if expense.status != 'APPROVED':
            return Response(
                {'error': '只能报销已批准的费用'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        expense.status = 'REIMBURSED'
        expense.reimbursement_date = timezone.now().date()
        expense.save()
        return Response(ExpenseSerializer(expense).data)


class AccountReceivableViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for AccountReceivable management.
    """
    queryset = AccountReceivable.objects.all()
    serializer_class = AccountReceivableSerializer
    filterset_fields = ['customer', 'project', 'status', 'is_deleted']
    search_fields = ['ar_no', 'invoice_no']
    ordering_fields = ['invoice_date', 'due_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        """Record a payment."""
        ar = self.get_object()
        payment_amount = request.data.get('amount')
        
        if not payment_amount or payment_amount <= 0:
            return Response(
                {'error': '请提供有效的付款金额'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_amount = float(payment_amount)
        
        if ar.amount_paid + payment_amount > ar.amount_due:
            return Response(
                {'error': '付款金额超过应收金额'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ar.amount_paid += payment_amount
        
        # Update status
        if ar.amount_paid >= ar.amount_due:
            ar.status = 'PAID'
        elif ar.amount_paid > 0:
            ar.status = 'PARTIAL'
        
        ar.save()
        return Response(AccountReceivableSerializer(ar).data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue receivables."""
        today = timezone.now().date()
        overdue_ars = self.get_queryset().filter(
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL']
        )
        serializer = self.get_serializer(overdue_ars, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def aging(self, request):
        """Get AR aging report."""
        today = timezone.now().date()
        ars = self.get_queryset().filter(status__in=['PENDING', 'PARTIAL'])
        
        aging_data = {
            'current': 0,
            '1-30_days': 0,
            '31-60_days': 0,
            '61-90_days': 0,
            'over_90_days': 0,
        }
        
        for ar in ars:
            days_overdue = (today - ar.due_date).days
            amount = float(ar.amount_remaining)
            
            if days_overdue <= 0:
                aging_data['current'] += amount
            elif days_overdue <= 30:
                aging_data['1-30_days'] += amount
            elif days_overdue <= 60:
                aging_data['31-60_days'] += amount
            elif days_overdue <= 90:
                aging_data['61-90_days'] += amount
            else:
                aging_data['over_90_days'] += amount
        
        return Response(aging_data)


class AccountPayableViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for AccountPayable management.
    """
    queryset = AccountPayable.objects.all()
    serializer_class = AccountPayableSerializer
    filterset_fields = ['supplier', 'status', 'is_deleted']
    search_fields = ['ap_no', 'invoice_no']
    ordering_fields = ['invoice_date', 'due_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        """Record a payment."""
        ap = self.get_object()
        payment_amount = request.data.get('amount')
        
        if not payment_amount or payment_amount <= 0:
            return Response(
                {'error': '请提供有效的付款金额'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_amount = float(payment_amount)
        
        if ap.amount_paid + payment_amount > ap.amount_due:
            return Response(
                {'error': '付款金额超过应付金额'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ap.amount_paid += payment_amount
        
        # Update status
        if ap.amount_paid >= ap.amount_due:
            ap.status = 'PAID'
        elif ap.amount_paid > 0:
            ap.status = 'PARTIAL'
        
        ap.save()
        return Response(AccountPayableSerializer(ap).data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue payables."""
        today = timezone.now().date()
        overdue_aps = self.get_queryset().filter(
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL']
        )
        serializer = self.get_serializer(overdue_aps, many=True)
        return Response(serializer.data)


class InvoiceViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for Invoice management.
    """
    from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
    
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ['invoice_type', 'status', 'reference_type', 'is_deleted']
    search_fields = ['invoice_no', 'party_name']
    ordering_fields = ['invoice_date', 'total_amount', 'created_at']
    
    @action(detail=True, methods=['post'])
    def certify(self, request, pk=None):
        """Certify input invoice."""
        invoice = self.get_object()
        
        if invoice.invoice_type != 'INPUT':
            return Response(
                {'error': '只有进项发票需要认证'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if invoice.status == 'CERTIFIED':
            return Response(
                {'error': '发票已认证'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if invoice.status == 'VOID':
            return Response(
                {'error': '已作废的发票无法认证'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        invoice.status = 'CERTIFIED'
        invoice.save()
        return Response(InvoiceSerializer(invoice).data)
    
    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        """Void invoice."""
        invoice = self.get_object()
        
        if invoice.status == 'VOID':
            return Response(
                {'error': '发票已作废'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        invoice.status = 'VOID'
        invoice.save()
        return Response(InvoiceSerializer(invoice).data)
    
    @action(detail=False, methods=['get'])
    def download_template(self, request):
        """Download invoice import template Excel file."""
        import io
        import openpyxl
        from openpyxl.utils import get_column_letter
        from openpyxl.styles import Font, PatternFill, Alignment
        from django.http import HttpResponse
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '发票导入模板'
        
        headers = [
            '发票类型', '发票号码', '数电发票号码', '开票日期',
            '销方识别号', '销方名称', '购方识别号', '购买方名称',
            '金额', '税额', '价税合计', '发票来源', '发票票种', '发票状态', '备注'
        ]
        
        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        
        example = [
            '销项发票', 'INV-2025-001', '25952000000022399509', '2025-01-15',
            '91440300MA5GR95713', '深圳市示例公司', '911310267954776025', '客户公司名称',
            '100000', '13000', '113000', '电子发票服务平台', '数电发票（增值税专用发票）', '正常', ''
        ]
        for col, val in enumerate(example, 1):
            ws.cell(row=2, column=col, value=val)
        
        widths = [10, 15, 25, 12, 22, 30, 22, 30, 12, 12, 12, 20, 30, 10, 20]
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width
        
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="invoice_import_template.xlsx"'
        return response
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """Export invoices to Excel."""
        import io
        import openpyxl
        from openpyxl.utils import get_column_letter
        from django.http import HttpResponse
        from django.utils import timezone
        
        queryset = self.get_queryset().filter(is_deleted=False)
        
        invoice_type = request.query_params.get('invoice_type')
        status_filter = request.query_params.get('status')
        if invoice_type:
            queryset = queryset.filter(invoice_type=invoice_type)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '发票列表'
        
        headers = [
            '序号', '发票类型', '发票号码', '数电发票号码', '开票日期',
            '销方识别号', '销方名称', '购方识别号', '购买方名称',
            '金额', '税额', '价税合计', '发票来源', '发票票种', '状态', '备注'
        ]
        
        for col, header in enumerate(headers, 1):
            ws.cell(row=1, column=col, value=header)
        
        for row, inv in enumerate(queryset, 2):
            ws.cell(row=row, column=1, value=row-1)
            ws.cell(row=row, column=2, value=inv.get_invoice_type_display())
            ws.cell(row=row, column=3, value=inv.invoice_no)
            ws.cell(row=row, column=4, value=inv.digital_invoice_no)
            ws.cell(row=row, column=5, value=inv.invoice_date.strftime('%Y-%m-%d %H:%M:%S') if inv.invoice_date else '')
            ws.cell(row=row, column=6, value=inv.seller_tax_no)
            ws.cell(row=row, column=7, value=inv.seller_name)
            ws.cell(row=row, column=8, value=inv.buyer_tax_no)
            ws.cell(row=row, column=9, value=inv.buyer_name)
            ws.cell(row=row, column=10, value=float(inv.amount_before_tax))
            ws.cell(row=row, column=11, value=float(inv.tax_amount))
            ws.cell(row=row, column=12, value=float(inv.total_amount))
            ws.cell(row=row, column=13, value=inv.invoice_source)
            ws.cell(row=row, column=14, value=inv.get_invoice_category_display() if inv.invoice_category else '')
            ws.cell(row=row, column=15, value=inv.get_status_display())
            ws.cell(row=row, column=16, value=inv.notes)
        
        widths = [6, 10, 15, 25, 20, 22, 30, 22, 30, 15, 15, 15, 20, 30, 10, 20]
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width
        
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="invoices_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        return response
    
    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """Import invoices from Excel file (supports 2025年开票明细.xlsx format)."""
        import io
        import openpyxl
        from django.db import transaction
        from decimal import Decimal, InvalidOperation
        from datetime import datetime
        from .models import InvoiceItem
        
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not file.name.endswith(('.xlsx', '.xls')):
            return Response({'error': '只支持Excel文件格式(.xlsx, .xls)'}, status=status.HTTP_400_BAD_REQUEST)
        
        def parse_decimal(value, default=Decimal('0')):
            """Safely parse decimal value."""
            if value is None:
                return default
            try:
                return Decimal(str(value).replace(',', ''))
            except (InvalidOperation, ValueError):
                return default
        
        def parse_datetime(value):
            """Parse datetime from various formats."""
            if value is None:
                return datetime.now()
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d']:
                    try:
                        return datetime.strptime(value.strip(), fmt)
                    except ValueError:
                        continue
            return datetime.now()
        
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file.read()))
            
            success_count = 0
            update_count = 0
            item_count = 0
            errors = []
            
            # ========== Step 1: Import invoice headers from "发票基础信息" ==========
            if '发票基础信息' in wb.sheetnames:
                sheet = wb['发票基础信息']
            else:
                sheet = wb.active
            
            headers = [str(cell.value).strip() if cell.value else '' for cell in sheet[1]]
            
            # Map headers to fields based on the Excel format
            col_map = {
                '发票类型': 'invoice_type_str',
                '发票代码': 'invoice_code',
                '发票号码': 'invoice_no',
                '数电发票号码': 'digital_invoice_no',
                '销方识别号': 'seller_tax_no',
                '销方名称': 'seller_name',
                '购方识别号': 'buyer_tax_no',
                '购买方名称': 'buyer_name',
                '开票日期': 'invoice_date',
                '金额': 'amount_before_tax',
                '税额': 'tax_amount',
                '价税合计': 'total_amount',
                '发票来源': 'invoice_source',
                '发票票种': 'invoice_category_str',
                '发票状态': 'status_str',
                '状态': 'status_str',
                '备注': 'notes',
            }
            
            header_to_field = {}
            for idx, header in enumerate(headers):
                if header in col_map:
                    header_to_field[idx] = col_map[header]
            
            # Store created/updated invoices for line item import
            invoice_map = {}  # invoice_no -> Invoice object
            
            with transaction.atomic():
                for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
                    try:
                        data = {}
                        for col_idx, cell in enumerate(row):
                            if col_idx in header_to_field:
                                field = header_to_field[col_idx]
                                value = cell.value
                                if value is not None:
                                    data[field] = value
                        
                        # Skip empty rows
                        if not data:
                            continue
                        
                        # Determine invoice number
                        invoice_no = data.get('digital_invoice_no') or data.get('invoice_no')
                        if not invoice_no:
                            continue
                        invoice_no = str(invoice_no).strip()
                        
                        # Parse invoice date
                        invoice_date = parse_datetime(data.get('invoice_date'))
                        
                        # Parse amounts
                        amount_before_tax = parse_decimal(data.get('amount_before_tax'))
                        tax_amount = parse_decimal(data.get('tax_amount'))
                        total_amount = parse_decimal(data.get('total_amount'))
                        if not total_amount:
                            total_amount = amount_before_tax + tax_amount
                        
                        # Parse status
                        status_map = {'正常': 'NORMAL', '已登记': 'REGISTERED', '已认证': 'CERTIFIED', '已作废': 'VOID', '红冲': 'RED'}
                        status_str = str(data.get('status_str', '')).strip()
                        inv_status = status_map.get(status_str, 'REGISTERED')
                        
                        # Parse invoice category
                        category_map = {
                            '数电发票（增值税专用发票）': 'SPECIAL',
                            '数电发票（普通发票）': 'NORMAL',
                        }
                        category_str = str(data.get('invoice_category_str', '')).strip()
                        invoice_category = category_map.get(category_str, '')
                        
                        # Determine invoice type (INPUT/OUTPUT) based on seller
                        seller_name = str(data.get('seller_name', '')).strip()
                        invoice_type = 'OUTPUT'
                        
                        # Determine party_name (the other party)
                        buyer_name = str(data.get('buyer_name', '')).strip()
                        party_name = buyer_name or seller_name
                        
                        # Check if invoice exists (including soft-deleted)
                        existing = Invoice.objects.filter(invoice_no=invoice_no).first()
                        if existing:
                            # Restore if was deleted
                            if existing.is_deleted:
                                existing.is_deleted = False
                                existing.deleted_at = None
                            existing.digital_invoice_no = str(data.get('digital_invoice_no', '')).strip()
                            existing.invoice_date = invoice_date
                            existing.seller_tax_no = str(data.get('seller_tax_no', '')).strip()
                            existing.seller_name = seller_name
                            existing.buyer_tax_no = str(data.get('buyer_tax_no', '')).strip()
                            existing.buyer_name = buyer_name
                            existing.party_name = party_name
                            existing.amount_before_tax = amount_before_tax
                            existing.tax_amount = tax_amount
                            existing.total_amount = total_amount
                            existing.invoice_source = str(data.get('invoice_source', '')).strip()
                            existing.invoice_category = invoice_category
                            existing.status = inv_status
                            existing.save()
                            # Delete existing items for reimport
                            existing.items.all().delete()
                            invoice_map[invoice_no] = existing
                            update_count += 1
                        else:
                            inv = Invoice.objects.create(
                                invoice_type=invoice_type,
                                invoice_no=invoice_no,
                                invoice_code=str(data.get('invoice_code', '')).strip(),
                                digital_invoice_no=str(data.get('digital_invoice_no', '')).strip(),
                                invoice_date=invoice_date,
                                seller_tax_no=str(data.get('seller_tax_no', '')).strip(),
                                seller_name=seller_name,
                                buyer_tax_no=str(data.get('buyer_tax_no', '')).strip(),
                                buyer_name=buyer_name,
                                party_name=party_name,
                                amount_before_tax=amount_before_tax,
                                tax_amount=tax_amount,
                                total_amount=total_amount,
                                invoice_source=str(data.get('invoice_source', '')).strip(),
                                invoice_category=invoice_category,
                                status=inv_status,
                            )
                            invoice_map[invoice_no] = inv
                            success_count += 1
                    
                    except Exception as e:
                        errors.append({'row': row_idx, 'sheet': '发票基础信息', 'error': str(e)})
                
                # ========== Step 2: Import line items from "信息汇总表" ==========
                if '信息汇总表' in wb.sheetnames:
                    detail_sheet = wb['信息汇总表']
                    detail_headers = [str(cell.value).strip() if cell.value else '' for cell in detail_sheet[1]]
                    
                    # Map detail sheet columns
                    detail_col_map = {
                        '数电发票号码': 'invoice_no',
                        '税收分类编码': 'tax_category_code',
                        '特定业务类型': 'business_type',
                        '货物或应税劳务名称': 'item_name',
                        '规格型号': 'specification',
                        '单位': 'unit',
                        '数量': 'quantity',
                        '单价': 'unit_price',
                        '金额': 'amount',
                        '税率': 'tax_rate',
                        '税额': 'tax_amount',
                    }
                    
                    detail_header_to_field = {}
                    for idx, header in enumerate(detail_headers):
                        if header in detail_col_map:
                            detail_header_to_field[idx] = detail_col_map[header]
                    
                    # Track line numbers per invoice
                    invoice_line_counts = {}
                    
                    for row_idx, row in enumerate(detail_sheet.iter_rows(min_row=2), start=2):
                        try:
                            data = {}
                            for col_idx, cell in enumerate(row):
                                if col_idx in detail_header_to_field:
                                    field = detail_header_to_field[col_idx]
                                    value = cell.value
                                    if value is not None:
                                        data[field] = value
                            
                            if not data:
                                continue
                            
                            invoice_no = str(data.get('invoice_no', '')).strip()
                            if not invoice_no:
                                continue
                            
                            # Find the invoice (from map or database)
                            invoice = invoice_map.get(invoice_no)
                            if not invoice:
                                invoice = Invoice.objects.filter(
                                    Q(invoice_no=invoice_no) | Q(digital_invoice_no=invoice_no)
                                ).first()
                            
                            if not invoice:
                                continue
                            
                            # Increment line number
                            if invoice_no not in invoice_line_counts:
                                invoice_line_counts[invoice_no] = 0
                            invoice_line_counts[invoice_no] += 1
                            line_no = invoice_line_counts[invoice_no]
                            
                            # Create line item
                            item_name = str(data.get('item_name', '')).strip()
                            if not item_name:
                                continue
                            
                            InvoiceItem.objects.create(
                                invoice=invoice,
                                line_no=line_no,
                                tax_category_code=str(data.get('tax_category_code', '')).strip(),
                                business_type=str(data.get('business_type', '')).strip(),
                                item_name=item_name,
                                specification=str(data.get('specification', '')).strip() if data.get('specification') else '',
                                unit=str(data.get('unit', '')).strip() if data.get('unit') else '',
                                quantity=parse_decimal(data.get('quantity'), None),
                                unit_price=parse_decimal(data.get('unit_price'), None),
                                amount=parse_decimal(data.get('amount')),
                                tax_rate=parse_decimal(data.get('tax_rate'), None),
                                tax_amount=parse_decimal(data.get('tax_amount'), None),
                            )
                            item_count += 1
                        
                        except Exception as e:
                            errors.append({'row': row_idx, 'sheet': '信息汇总表', 'error': str(e)})
            
            return Response({
                'success_count': success_count,
                'update_count': update_count,
                'item_count': item_count,
                'error_count': len(errors),
                'errors': errors[:10]
            })
        
        except Exception as e:
            return Response({'error': f'导入失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def perform_destroy(self, instance):
        """删除发票时同时删除关联的附件"""
        from apps.core.models import Attachment
        
        # 删除关联的附件文件
        attachments = Attachment.objects.filter(related_model='Invoice', related_id=instance.id)
        for attachment in attachments:
            # 删除物理文件
            if attachment.file:
                attachment.file.delete(save=False)
            attachment.delete()
        
        # 删除发票（物理删除）
        instance.delete()
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk delete invoices."""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请选择要删除的发票'}, status=status.HTTP_400_BAD_REQUEST)
        
        from apps.core.models import Attachment
        from .models import InvoiceItem
        
        # 删除关联的附件文件
        attachments = Attachment.objects.filter(related_model='Invoice', related_id__in=ids)
        for attachment in attachments:
            if attachment.file:
                attachment.file.delete(save=False)
            attachment.delete()
        
        # 删除发票明细
        InvoiceItem.objects.filter(invoice_id__in=ids).delete()
        
        # 删除发票
        deleted_count = Invoice.objects.filter(id__in=ids).delete()[0]
        
        return Response({
            'success': True,
            'deleted_count': deleted_count
        })
    
    @action(detail=False, methods=['post'])
    def import_pdf(self, request):
        """
        批量导入发票PDF文件。
        PDF文件名应包含数电发票号码，系统将自动匹配并关联到对应发票。
        支持的文件名格式:
        - 25952000000272801788.pdf
        - 发票_25952000000272801788.pdf
        - 任何包含20位数电发票号码的文件名
        """
        import re
        import os
        from apps.core.models import Attachment
        
        # 支持多文件上传(files)和单文件上传(file)
        files = request.FILES.getlist('files')
        if not files:
            # el-upload 的 multiple 模式会逐个发送文件，字段名为 'file'
            single_file = request.FILES.get('file')
            if single_file:
                files = [single_file]
        
        if not files:
            return Response({'error': '请选择要上传的PDF文件'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 数电发票号码通常是20位数字
        invoice_no_pattern = re.compile(r'(\d{20})')
        
        results = {
            'total': len(files),
            'matched': 0,
            'unmatched': 0,
            'matched_files': [],
            'unmatched_files': []
        }
        
        for file in files:
            filename = file.name
            file_ext = os.path.splitext(filename)[1].lower()
            
            # 只接受PDF文件
            if file_ext != '.pdf':
                results['unmatched'] += 1
                results['unmatched_files'].append({
                    'filename': filename,
                    'reason': '不是PDF文件'
                })
                continue
            
            # 从文件名中提取数电发票号码
            match = invoice_no_pattern.search(filename)
            if not match:
                results['unmatched'] += 1
                results['unmatched_files'].append({
                    'filename': filename,
                    'reason': '文件名中未找到20位数电发票号码'
                })
                continue
            
            invoice_no = match.group(1)
            
            # 查找对应的发票
            invoice = Invoice.objects.filter(
                Q(digital_invoice_no=invoice_no) | Q(invoice_no=invoice_no),
                is_deleted=False
            ).first()
            
            if not invoice:
                results['unmatched'] += 1
                results['unmatched_files'].append({
                    'filename': filename,
                    'reason': f'未找到发票号码 {invoice_no}'
                })
                continue
            
            # 检查是否已存在相同的附件
            existing = Attachment.objects.filter(
                related_model='Invoice',
                related_id=invoice.id,
                original_name=filename
            ).exists()
            
            if existing:
                results['unmatched'] += 1
                results['unmatched_files'].append({
                    'filename': filename,
                    'reason': '该附件已存在'
                })
                continue
            
            # 创建附件记录
            attachment = Attachment.objects.create(
                file=file,
                original_name=filename,
                file_size=file.size,
                file_type='application/pdf',
                category='INVOICE',
                related_model='Invoice',
                related_id=invoice.id,
                description=f'发票PDF - {invoice_no}',
                uploaded_by=request.user
            )
            
            results['matched'] += 1
            results['matched_files'].append({
                'filename': filename,
                'invoice_no': invoice_no,
                'invoice_id': invoice.id,
                'attachment_id': attachment.id
            })
        
        return Response(results)
    
    @action(detail=True, methods=['get'])
    def attachments(self, request, pk=None):
        """获取发票的附件列表"""
        from apps.core.models import Attachment
        from apps.core.serializers import AttachmentSerializer
        
        invoice = self.get_object()
        attachments = Attachment.objects.filter(
            related_model='Invoice',
            related_id=invoice.id
        )
        
        serializer = AttachmentSerializer(attachments, many=True, context={'request': request})
        return Response(serializer.data)


class SharedExpenseViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for SharedExpense management.
    """
    queryset = SharedExpense.objects.all()
    serializer_class = SharedExpenseSerializer
    filterset_fields = ['category', 'status', 'allocation_method', 'is_deleted']
    search_fields = ['expense_no', 'name']
    ordering_fields = ['expense_date', 'amount', 'created_at']
    
    @action(detail=True, methods=['post'])
    def calculate_allocation(self, request, pk=None):
        """
        Calculate allocation ratios based on allocation method.
        Returns preview without saving.
        """
        shared_expense = self.get_object()
        project_ids = request.data.get('project_ids', [])
        custom_ratios = request.data.get('custom_ratios', {})
        
        if not project_ids:
            return Response(
                {'error': '请选择至少一个项目'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        projects = Project.objects.filter(id__in=project_ids, is_deleted=False)
        
        if not projects.exists():
            return Response(
                {'error': '未找到有效项目'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        allocations = self._calculate_allocations(
            shared_expense, 
            projects, 
            custom_ratios
        )
        
        return Response({
            'expense_id': shared_expense.id,
            'expense_no': shared_expense.expense_no,
            'total_amount': float(shared_expense.amount),
            'allocation_method': shared_expense.allocation_method,
            'allocations': allocations
        })
    
    @action(detail=True, methods=['post'])
    def allocate(self, request, pk=None):
        """
        Perform the actual allocation to projects.
        """
        shared_expense = self.get_object()
        
        if shared_expense.status == 'ALLOCATED':
            return Response(
                {'error': '该费用已分摊'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        project_ids = request.data.get('project_ids', [])
        custom_ratios = request.data.get('custom_ratios', {})
        
        if not project_ids:
            return Response(
                {'error': '请选择至少一个项目'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        projects = Project.objects.filter(id__in=project_ids, is_deleted=False)
        
        if not projects.exists():
            return Response(
                {'error': '未找到有效项目'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        allocations_data = self._calculate_allocations(
            shared_expense, 
            projects, 
            custom_ratios
        )
        
        with transaction.atomic():
            # Delete existing allocations
            shared_expense.allocations.all().delete()
            
            # Create new allocations
            for alloc_data in allocations_data:
                SharedExpenseAllocation.objects.create(
                    shared_expense=shared_expense,
                    project_id=alloc_data['project_id'],
                    allocation_ratio=Decimal(str(alloc_data['ratio'])),
                    allocated_amount=Decimal(str(alloc_data['amount'])),
                    created_by=request.user
                )
            
            # Update status
            shared_expense.status = 'ALLOCATED'
            shared_expense.allocated_at = timezone.now()
            shared_expense.allocated_by = request.user
            shared_expense.save()
        
        return Response(SharedExpenseSerializer(shared_expense).data)
    
    @action(detail=True, methods=['post'])
    def cancel_allocation(self, request, pk=None):
        """Cancel allocation and reset to pending status."""
        shared_expense = self.get_object()
        
        if shared_expense.status != 'ALLOCATED':
            return Response(
                {'error': '只能取消已分摊的费用'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Delete allocations
            shared_expense.allocations.all().delete()
            
            # Reset status
            shared_expense.status = 'PENDING'
            shared_expense.allocated_at = None
            shared_expense.allocated_by = None
            shared_expense.save()
        
        return Response(SharedExpenseSerializer(shared_expense).data)
    
    @action(detail=False, methods=['get'])
    def allocation_methods(self, request):
        """Get available allocation methods."""
        return Response([
            {'value': 'EQUAL', 'label': '平均分摊'},
            {'value': 'REVENUE', 'label': '按收入比例'},
            {'value': 'HEADCOUNT', 'label': '按人员数量'},
            {'value': 'LABOR_HOURS', 'label': '按工时比例'},
            {'value': 'BUDGET', 'label': '按预算比例'},
            {'value': 'CUSTOM', 'label': '自定义比例'},
        ])
    
    @action(detail=False, methods=['get'])
    def project_allocation_summary(self, request):
        """Get total allocated expenses for each project."""
        project_id = request.query_params.get('project_id')
        
        queryset = SharedExpenseAllocation.objects.filter(
            shared_expense__status='ALLOCATED',
            shared_expense__is_deleted=False
        )
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        summary = queryset.values(
            'project__id', 'project__code', 'project__name'
        ).annotate(
            total_allocated=Sum('allocated_amount'),
            allocation_count=Count('id')
        ).order_by('-total_allocated')
        
        return Response(list(summary))
    
    def _calculate_allocations(self, shared_expense, projects, custom_ratios=None):
        """Calculate allocation based on method."""
        method = shared_expense.allocation_method
        total_amount = shared_expense.amount
        project_list = list(projects)
        n = len(project_list)
        
        if method == 'EQUAL':
            # Equal split
            ratio = Decimal('1') / n
            return [
                {
                    'project_id': p.id,
                    'project_code': p.code,
                    'project_name': p.name,
                    'ratio': float(ratio),
                    'amount': float(total_amount / n)
                }
                for p in project_list
            ]
        
        elif method == 'REVENUE':
            # By revenue ratio
            from apps.sales.models import SalesOrder
            revenues = {}
            for p in project_list:
                total = SalesOrder.objects.filter(
                    project=p,
                    status__in=['CONFIRMED', 'SHIPPED', 'COMPLETED'],
                    is_deleted=False
                ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
                revenues[p.id] = total
            
            total_revenue = sum(revenues.values()) or Decimal('1')
            
            return [
                {
                    'project_id': p.id,
                    'project_code': p.code,
                    'project_name': p.name,
                    'ratio': float(revenues[p.id] / total_revenue),
                    'amount': float(total_amount * revenues[p.id] / total_revenue)
                }
                for p in project_list
            ]
        
        elif method == 'HEADCOUNT':
            # By headcount
            from apps.projects.models import ProjectMember
            headcounts = {}
            for p in project_list:
                count = ProjectMember.objects.filter(
                    project=p,
                    is_deleted=False
                ).count() or 1
                headcounts[p.id] = count
            
            total_headcount = sum(headcounts.values()) or 1
            
            return [
                {
                    'project_id': p.id,
                    'project_code': p.code,
                    'project_name': p.name,
                    'ratio': float(headcounts[p.id] / total_headcount),
                    'amount': float(total_amount * headcounts[p.id] / total_headcount)
                }
                for p in project_list
            ]
        
        elif method == 'LABOR_HOURS':
            # By labor hours
            from apps.projects.models import ProjectMember
            hours = {}
            for p in project_list:
                total = ProjectMember.objects.filter(
                    project=p,
                    is_deleted=False
                ).aggregate(total=Sum('actual_hours'))['total'] or Decimal('1')
                hours[p.id] = total
            
            total_hours = sum(hours.values()) or Decimal('1')
            
            return [
                {
                    'project_id': p.id,
                    'project_code': p.code,
                    'project_name': p.name,
                    'ratio': float(hours[p.id] / total_hours),
                    'amount': float(total_amount * hours[p.id] / total_hours)
                }
                for p in project_list
            ]
        
        elif method == 'BUDGET':
            # By budget ratio
            budgets = {}
            for p in project_list:
                budgets[p.id] = p.budget_total or Decimal('0')
            
            total_budget = sum(budgets.values()) or Decimal('1')
            
            return [
                {
                    'project_id': p.id,
                    'project_code': p.code,
                    'project_name': p.name,
                    'ratio': float(budgets[p.id] / total_budget),
                    'amount': float(total_amount * budgets[p.id] / total_budget)
                }
                for p in project_list
            ]
        
        elif method == 'CUSTOM' and custom_ratios:
            # Custom ratios provided
            total_ratio = sum(Decimal(str(v)) for v in custom_ratios.values()) or Decimal('1')
            
            return [
                {
                    'project_id': p.id,
                    'project_code': p.code,
                    'project_name': p.name,
                    'ratio': float(Decimal(str(custom_ratios.get(str(p.id), 0))) / total_ratio),
                    'amount': float(total_amount * Decimal(str(custom_ratios.get(str(p.id), 0))) / total_ratio)
                }
                for p in project_list
            ]
        
        # Default to equal
        ratio = Decimal('1') / n
        return [
            {
                'project_id': p.id,
                'project_code': p.code,
                'project_name': p.name,
                'ratio': float(ratio),
                'amount': float(total_amount / n)
            }
            for p in project_list
        ]


class SharedExpenseAllocationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for SharedExpenseAllocation (read-only).
    """
    queryset = SharedExpenseAllocation.objects.all()
    serializer_class = SharedExpenseAllocationSerializer
    filterset_fields = ['shared_expense', 'project']
    
    @action(detail=False, methods=['get'])
    def by_project(self, request):
        """Get all allocations for a specific project."""
        project_id = request.query_params.get('project_id')
        
        if not project_id:
            return Response(
                {'error': '请提供项目ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        allocations = self.get_queryset().filter(
            project_id=project_id,
            shared_expense__status='ALLOCATED'
        ).select_related('shared_expense')
        
        data = []
        for alloc in allocations:
            data.append({
                'id': alloc.id,
                'expense_no': alloc.shared_expense.expense_no,
                'expense_name': alloc.shared_expense.name,
                'category': alloc.shared_expense.category,
                'expense_date': alloc.shared_expense.expense_date,
                'total_amount': float(alloc.shared_expense.amount),
                'allocation_ratio': float(alloc.allocation_ratio),
                'allocated_amount': float(alloc.allocated_amount),
            })
        
        return Response(data)

