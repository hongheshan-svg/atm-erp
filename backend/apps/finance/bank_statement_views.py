"""
Views for bank statement import/export.
"""
import io
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.masterdata.models import Supplier, Customer
from .models import AccountPayable, AccountReceivable, Payment
from .bank_statement_models import BankStatement, BankStatementImportLog
from .bank_statement_serializers import (
    BankStatementSerializer,
    BankStatementImportLogSerializer,
    BankStatementMatchSerializer
)


class BankStatementViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for BankStatement management.
    """
    queryset = BankStatement.objects.all()
    serializer_class = BankStatementSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ['status', 'transaction_type', 'match_type', 'supplier', 'customer', 'import_batch']
    search_fields = ['counterparty_name', 'summary', 'purpose', 'postscript']
    ordering_fields = ['transaction_time', 'debit_amount', 'credit_amount', 'created_at']
    
    def _parse_amount(self, value):
        """Parse amount string to Decimal."""
        if not value:
            return Decimal('0')
        # Remove commas and spaces
        value = str(value).replace(',', '').replace(' ', '').strip()
        if not value:
            return Decimal('0')
        try:
            return Decimal(value)
        except InvalidOperation:
            return Decimal('0')
    
    def _parse_datetime(self, value):
        """Parse datetime string."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%Y-%m-%d',
            '%Y/%m/%d',
        ]
        
        value = str(value).strip()
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
    
    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """
        Import bank statement from Excel file.
        Supports the bank format with headers on row 2.
        """
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': '请上传文件'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file_name = file.name
        if not file_name.endswith(('.xlsx', '.xls')):
            return Response(
                {'error': '只支持Excel文件格式(.xlsx, .xls)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            import openpyxl
            
            # Generate batch number
            batch_no = f"BS{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            # Read Excel file
            wb = openpyxl.load_workbook(io.BytesIO(file.read()))
            sheet = wb.active
            
            # Find header row (should be row 2 for this format)
            header_row = 2
            headers = []
            for col in range(1, sheet.max_column + 1):
                cell_value = sheet.cell(row=header_row, column=col).value
                headers.append(str(cell_value) if cell_value else '')
            
            # Map column indices (bank format)
            col_map = {
                '凭证号': None,
                '对方账号': None,
                '交易时间': None,
                '借贷标志': None,
                '对方单位': None,
                '对方行号': None,
                '用途': None,
                '摘要': None,
                '附言': None,
                '回单个性化信息': None,
                '转入金额': None,
                '转出金额': None,
                '支付凭证种类': None,
                '余额': None,
            }
            
            for idx, header in enumerate(headers):
                if header in col_map:
                    col_map[header] = idx + 1  # 1-based index
            
            # Keywords to filter out internal/non-business transactions
            SKIP_KEYWORDS = [
                # 工资相关
                '工资', '薪资', '薪酬', '社保', '公积金', '个税', '代扣', '代缴',
                # 税费相关
                '税款', '税费', '增值税', '附加税', '所得税', '印花税', '税收收缴', '国库',
                # 内部往来
                '内部', '往来', '调拨', '备用金', '借款', '还款',
                # 银行费用
                '利息', '手续费', '银行费', '账户管理费',
                # 公用事业费
                '电费', '水费', '房租', '物业费', '供电局', '自来水', '燃气',
                # 其他
                '退款', '冲账', '更正', '报销费用', '差旅费'
            ]
            
            def is_internal_transaction(name, purpose, summary, postscript):
                """Check if transaction is internal/non-business that should be skipped."""
                all_text = f"{name or ''}{purpose or ''}{summary or ''}{postscript or ''}"
                for keyword in SKIP_KEYWORDS:
                    if keyword in all_text:
                        return True
                return False
            
            # Import records
            records = []
            errors = []
            skipped_count = 0
            duplicate_count = 0
            success_count = 0
            matched_count = 0
            debit_total = Decimal('0')
            credit_total = Decimal('0')
            
            # Track processed transactions within this import to avoid in-file duplicates
            processed_transactions = set()
            
            with transaction.atomic():
                for row in range(header_row + 1, sheet.max_row + 1):
                    try:
                        # Get cell values
                        def get_cell(col_name):
                            col_idx = col_map.get(col_name)
                            if col_idx:
                                return sheet.cell(row=row, column=col_idx).value
                            return None
                        
                        counterparty_name = get_cell('对方单位')
                        transaction_time = get_cell('交易时间')
                        
                        # Skip empty rows
                        if not counterparty_name and not transaction_time:
                            continue
                        
                        purpose = str(get_cell('用途') or '')
                        summary = str(get_cell('摘要') or '')
                        postscript = str(get_cell('附言') or '')
                        
                        # Skip internal/non-business transactions
                        if is_internal_transaction(counterparty_name, purpose, summary, postscript):
                            skipped_count += 1
                            continue
                        
                        voucher_no = str(get_cell('凭证号') or '')
                        
                        # Create a unique key for duplicate detection
                        # Use voucher_no + transaction_time + counterparty_name + amounts
                        credit_amount_raw = self._parse_amount(get_cell('转入金额'))
                        debit_amount_raw = self._parse_amount(get_cell('转出金额'))
                        parsed_time_raw = self._parse_datetime(get_cell('交易时间'))
                        time_str = parsed_time_raw.strftime('%Y-%m-%d %H:%M:%S') if parsed_time_raw else ''
                        
                        duplicate_key = f"{voucher_no}|{time_str}|{counterparty_name}|{credit_amount_raw}|{debit_amount_raw}"
                        
                        # Check for in-file duplicate
                        if duplicate_key in processed_transactions:
                            duplicate_count += 1
                            continue
                        processed_transactions.add(duplicate_key)
                        
                        # Check for existing record in database
                        if voucher_no:
                            existing = BankStatement.objects.filter(
                                voucher_no=voucher_no,
                                is_deleted=False
                            ).first()
                            if existing:
                                duplicate_count += 1
                                continue
                        elif parsed_time_raw and counterparty_name:
                            # Check by time + counterparty + amount for records without voucher_no
                            existing = BankStatement.objects.filter(
                                transaction_time=parsed_time_raw,
                                counterparty_name=str(counterparty_name or ''),
                                credit_amount=credit_amount_raw,
                                debit_amount=debit_amount_raw,
                                is_deleted=False
                            ).first()
                            if existing:
                                duplicate_count += 1
                                continue
                        
                        # Parse transaction type
                        debit_credit = get_cell('借贷标志')
                        transaction_type = 'DEBIT' if debit_credit == '借' else 'CREDIT'
                        
                        # Use already parsed amounts
                        credit_amount = credit_amount_raw
                        debit_amount = debit_amount_raw
                        balance = self._parse_amount(get_cell('余额'))
                        
                        # Use already parsed time
                        parsed_time = parsed_time_raw if parsed_time_raw else timezone.now()
                        
                        # Try to match supplier/customer BEFORE creating record
                        supplier = None
                        customer = None
                        match_confidence = Decimal('0')
                        
                        # Create a temporary object for matching
                        temp_statement = BankStatement(
                            counterparty_name=str(counterparty_name or ''),
                            transaction_type=transaction_type
                        )
                        
                        if transaction_type == 'DEBIT':
                            # Payment to supplier
                            supplier, confidence = temp_statement.auto_match_supplier()
                            if supplier:
                                match_confidence = Decimal(str(confidence))
                        else:
                            # Receipt from customer
                            customer, confidence = temp_statement.auto_match_customer()
                            if customer:
                                match_confidence = Decimal(str(confidence))
                        
                        # Create record (import all records, mark unmatched as PENDING)
                        statement = BankStatement(
                            import_batch=batch_no,
                            source_file=file_name,
                            voucher_no=voucher_no,
                            counterparty_account=str(get_cell('对方账号') or ''),
                            transaction_time=parsed_time,
                            transaction_type=transaction_type,
                            counterparty_name=str(counterparty_name or ''),
                            counterparty_bank=str(get_cell('对方行号') or ''),
                            purpose=purpose,
                            summary=summary,
                            postscript=postscript,
                            receipt_info=str(get_cell('回单个性化信息') or ''),
                            credit_amount=credit_amount,
                            debit_amount=debit_amount,
                            balance=balance,
                            payment_voucher_type=str(get_cell('支付凭证种类') or ''),
                            created_by=request.user,
                            supplier=supplier,
                            customer=customer,
                            match_confidence=match_confidence,
                            match_type='AP' if supplier else ('AR' if customer else None),
                            status='MATCHED' if match_confidence >= 70 else 'PENDING'
                        )
                        
                        if match_confidence >= 70:
                                    matched_count += 1
                        
                        statement.save()
                        records.append(statement)
                        success_count += 1
                        
                        debit_total += debit_amount
                        credit_total += credit_amount
                        
                    except Exception as e:
                        errors.append({
                            'row': row,
                            'error': str(e)
                        })
                
                # Create import log
                import_log = BankStatementImportLog.objects.create(
                    batch_no=batch_no,
                    file_name=file_name,
                    total_count=sheet.max_row - header_row,
                    success_count=success_count,
                    error_count=len(errors),
                    matched_count=matched_count,
                    debit_total=debit_total,
                    credit_total=credit_total,
                    error_details=errors,
                    notes=f'跳过{skipped_count}条非业务流水，{duplicate_count}条重复记录',
                    created_by=request.user
                )
            
            return Response({
                'batch_no': batch_no,
                'success_count': success_count,
                'skipped_count': skipped_count,
                'duplicate_count': duplicate_count,
                'error_count': len(errors),
                'matched_count': matched_count,
                'debit_total': float(debit_total),
                'credit_total': float(credit_total),
                'errors': errors[:10],  # Return first 10 errors
                'import_log_id': import_log.id
            })
            
        except Exception as e:
            return Response(
                {'error': f'导入失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        """
        Export bank statements to Excel.
        """
        try:
            import openpyxl
            from openpyxl.utils import get_column_letter
            
            # Get filters
            status_filter = request.query_params.get('status')
            transaction_type = request.query_params.get('transaction_type')
            supplier_id = request.query_params.get('supplier')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            queryset = self.get_queryset()
            
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            if transaction_type:
                queryset = queryset.filter(transaction_type=transaction_type)
            if supplier_id:
                queryset = queryset.filter(supplier_id=supplier_id)
            if start_date:
                queryset = queryset.filter(transaction_time__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(transaction_time__date__lte=end_date)
            
            # Create workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = '银行流水'
            
            # Headers
            headers = [
                '交易时间', '借贷标志', '对方单位', '用途', '摘要', '附言',
                '转入金额', '转出金额', '余额', '匹配状态', '匹配供应商/客户',
                '关联单号', '导入批次'
            ]
            
            for col, header in enumerate(headers, 1):
                ws.cell(row=1, column=col, value=header)
            
            # Data rows
            for row, statement in enumerate(queryset, 2):
                ws.cell(row=row, column=1, value=statement.transaction_time.strftime('%Y-%m-%d %H:%M:%S'))
                ws.cell(row=row, column=2, value='借' if statement.transaction_type == 'DEBIT' else '贷')
                ws.cell(row=row, column=3, value=statement.counterparty_name)
                ws.cell(row=row, column=4, value=statement.purpose)
                ws.cell(row=row, column=5, value=statement.summary)
                ws.cell(row=row, column=6, value=statement.postscript)
                ws.cell(row=row, column=7, value=float(statement.credit_amount))
                ws.cell(row=row, column=8, value=float(statement.debit_amount))
                ws.cell(row=row, column=9, value=float(statement.balance) if statement.balance else '')
                ws.cell(row=row, column=10, value=statement.get_status_display())
                
                # Matched entity
                if statement.supplier:
                    ws.cell(row=row, column=11, value=f'供应商: {statement.supplier.name}')
                elif statement.customer:
                    ws.cell(row=row, column=11, value=f'客户: {statement.customer.name}')
                else:
                    ws.cell(row=row, column=11, value='')
                
                # Related document
                if statement.related_ap:
                    ws.cell(row=row, column=12, value=statement.related_ap.ap_no)
                elif statement.related_ar:
                    ws.cell(row=row, column=12, value=statement.related_ar.ar_no)
                else:
                    ws.cell(row=row, column=12, value='')
                
                ws.cell(row=row, column=13, value=statement.import_batch)
            
            # Set column widths
            column_widths = [20, 8, 30, 12, 20, 30, 12, 12, 12, 10, 25, 15, 18]
            for col, width in enumerate(column_widths, 1):
                ws.column_dimensions[get_column_letter(col)].width = width
            
            # Create response
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="bank_statements_{timezone.now().strftime("%Y%m%d")}.xlsx"'
            
            return response
            
        except Exception as e:
            return Response(
                {'error': f'导出失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def match(self, request, pk=None):
        """
        Manually match a bank statement to supplier/customer and AP/AR.
        """
        statement = self.get_object()
        serializer = BankStatementMatchSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        match_type = data.get('match_type')
        
        with transaction.atomic():
            statement.match_type = match_type
            statement.match_notes = data.get('notes', '')
            
            if match_type == 'AP':
                supplier_id = data.get('supplier_id')
                if supplier_id:
                    statement.supplier = Supplier.objects.get(id=supplier_id)
                
                ap_id = data.get('ap_id')
                if ap_id:
                    statement.related_ap = AccountPayable.objects.get(id=ap_id)
                
                statement.customer = None
                statement.related_ar = None
                
            elif match_type == 'AR':
                customer_id = data.get('customer_id')
                if customer_id:
                    statement.customer = Customer.objects.get(id=customer_id)
                
                ar_id = data.get('ar_id')
                if ar_id:
                    statement.related_ar = AccountReceivable.objects.get(id=ar_id)
                
                statement.supplier = None
                statement.related_ap = None
            
            # Set project if provided
            project_id = data.get('project_id')
            if project_id:
                from apps.projects.models import Project
                statement.project = Project.objects.get(id=project_id)
            elif not statement.project:
                # Try auto-matching project
                project = statement.auto_match_project()
                if project:
                    statement.project = project
            
            statement.status = 'MATCHED'
            statement.match_confidence = Decimal('100')
            statement.save()
        
        return Response(BankStatementSerializer(statement).data)
    
    @action(detail=True, methods=['post'])
    def ignore(self, request, pk=None):
        """Mark a bank statement as ignored."""
        statement = self.get_object()
        statement.status = 'IGNORED'
        statement.match_notes = request.data.get('notes', '手动忽略')
        statement.save()
        return Response(BankStatementSerializer(statement).data)
    
    @action(detail=False, methods=['post'])
    def auto_match_all(self, request):
        """
        Auto-match all pending bank statements.
        Also attempts to match projects based on customer/supplier.
        """
        batch = request.data.get('import_batch')
        queryset = self.get_queryset().filter(status='PENDING')
        
        if batch:
            queryset = queryset.filter(import_batch=batch)
        
        matched_count = 0
        project_matched_count = 0
        
        with transaction.atomic():
            for statement in queryset:
                matched = False
                
                if statement.transaction_type == 'DEBIT':
                    supplier, confidence = statement.auto_match_supplier()
                    if supplier and confidence >= 70:
                        statement.supplier = supplier
                        statement.match_confidence = Decimal(str(confidence))
                        statement.match_type = 'AP'
                        statement.status = 'MATCHED'
                        matched = True
                else:
                    customer, confidence = statement.auto_match_customer()
                    if customer and confidence >= 70:
                        statement.customer = customer
                        statement.match_confidence = Decimal(str(confidence))
                        statement.match_type = 'AR'
                        statement.status = 'MATCHED'
                        matched = True
                
                # Try to match project based on customer/supplier
                if matched:
                    project = statement.auto_match_project()
                    if project:
                        statement.project = project
                        project_matched_count += 1
                    
                        statement.save()
                        matched_count += 1
                    
                    # 尝试匹配付款计划
                    if statement.transaction_type == 'CREDIT' and statement.customer:
                        # 收款匹配销售付款计划
                        self._try_match_payment_schedule(statement)
                    elif statement.transaction_type == 'DEBIT' and statement.supplier:
                        # 付款匹配采购付款计划
                        self._try_match_purchase_payment_schedule(statement)
        
        return Response({
            'matched_count': matched_count,
            'project_matched_count': project_matched_count,
            'message': f'成功匹配 {matched_count} 条记录，其中 {project_matched_count} 条关联到项目'
        })
    
    def _try_match_payment_schedule(self, statement):
        """
        尝试将银行流水匹配到付款计划。
        根据客户和金额找到最匹配的付款计划。
        """
        from apps.finance.models import PaymentSchedule
        from decimal import Decimal
        
        customer = statement.customer
        amount = statement.credit_amount or Decimal('0')
        
        if not customer or amount <= 0:
            return None
        
        # 查找该客户待收款的付款计划
        # 优先匹配金额完全相等的
        exact_match = PaymentSchedule.objects.filter(
            sales_order__customer=customer,
            status__in=['PENDING', 'PARTIAL'],
            amount_due=amount,
            is_deleted=False
        ).order_by('due_date').first()
        
        if exact_match:
            exact_match.amount_paid += amount
            if exact_match.amount_paid >= exact_match.amount_due:
                exact_match.status = 'PAID'
                exact_match.actual_paid_date = statement.transaction_time.date()
                exact_match.reminder_status = 'COLLECTED'
            else:
                exact_match.status = 'PARTIAL'
            exact_match.save()
            exact_match.bank_statements.add(statement)
            
            # 更新流水的项目关联
            if exact_match.project:
                statement.project = exact_match.project
                statement.save()
            
            return exact_match
        
        # 如果没有完全匹配，查找剩余金额接近的
        pending_schedules = PaymentSchedule.objects.filter(
            sales_order__customer=customer,
            status__in=['PENDING', 'PARTIAL'],
            is_deleted=False
        ).order_by('due_date')
        
        for schedule in pending_schedules:
            remaining = schedule.amount_due - schedule.amount_paid
            # 如果付款金额在剩余金额的10%范围内，认为匹配
            if abs(remaining - amount) <= remaining * Decimal('0.1'):
                schedule.amount_paid += amount
                if schedule.amount_paid >= schedule.amount_due:
                    schedule.status = 'PAID'
                    schedule.actual_paid_date = statement.transaction_time.date()
                    schedule.reminder_status = 'COLLECTED'
                else:
                    schedule.status = 'PARTIAL'
                schedule.save()
                schedule.bank_statements.add(statement)
                
                if schedule.project:
                    statement.project = schedule.project
                    statement.save()
                
                return schedule
        
        return None
    
    def _try_match_purchase_payment_schedule(self, statement):
        """
        尝试将银行流水（付款）匹配到采购付款计划。
        根据供应商和金额找到最匹配的采购付款计划。
        """
        from apps.finance.models import PurchasePaymentSchedule
        from decimal import Decimal
        
        supplier = statement.supplier
        amount = statement.debit_amount or Decimal('0')
        
        if not supplier or amount <= 0:
            return None
        
        # 查找该供应商待付款的付款计划
        # 优先匹配金额完全相等的
        exact_match = PurchasePaymentSchedule.objects.filter(
            purchase_order__supplier=supplier,
            status__in=['PENDING', 'PARTIAL'],
            amount_due=amount,
            is_deleted=False
        ).order_by('due_date').first()
        
        if exact_match:
            exact_match.amount_paid += amount
            if exact_match.amount_paid >= exact_match.amount_due:
                exact_match.status = 'PAID'
                exact_match.actual_paid_date = statement.transaction_time.date()
                exact_match.reminder_status = 'PAID'
            else:
                exact_match.status = 'PARTIAL'
            exact_match.save()
            exact_match.bank_statements.add(statement)
            
            # 更新流水的项目关联
            if exact_match.project:
                statement.project = exact_match.project
                statement.save()
            
            return exact_match
        
        # 如果没有完全匹配，查找剩余金额接近的
        pending_schedules = PurchasePaymentSchedule.objects.filter(
            purchase_order__supplier=supplier,
            status__in=['PENDING', 'PARTIAL'],
            is_deleted=False
        ).order_by('due_date')
        
        for schedule in pending_schedules:
            remaining = schedule.amount_due - schedule.amount_paid
            # 如果付款金额在剩余金额的10%范围内，认为匹配
            if abs(remaining - amount) <= remaining * Decimal('0.1'):
                schedule.amount_paid += amount
                if schedule.amount_paid >= schedule.amount_due:
                    schedule.status = 'PAID'
                    schedule.actual_paid_date = statement.transaction_time.date()
                    schedule.reminder_status = 'PAID'
                else:
                    schedule.status = 'PARTIAL'
                schedule.save()
                schedule.bank_statements.add(statement)
                
                if schedule.project:
                    statement.project = schedule.project
                    statement.save()
                
                return schedule
        
        return None
    
    @action(detail=False, methods=['get'])
    def summary_by_supplier(self, request):
        """
        Get summary of bank statements grouped by supplier.
        """
        from django.db.models import Sum, Count
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset().filter(
            transaction_type='DEBIT',
            supplier__isnull=False
        )
        
        if start_date:
            queryset = queryset.filter(transaction_time__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(transaction_time__date__lte=end_date)
        
        summary = queryset.values(
            'supplier__id', 'supplier__name'
        ).annotate(
            total_amount=Sum('debit_amount'),
            transaction_count=Count('id')
        ).order_by('-total_amount')
        
        return Response(list(summary))
    
    @action(detail=False, methods=['get'])
    def unmatched_payments(self, request):
        """
        Get unmatched payments (debit transactions without AP match).
        """
        supplier_id = request.query_params.get('supplier_id')
        
        queryset = self.get_queryset().filter(
            transaction_type='DEBIT',
            status='PENDING'
        )
        
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        
        serializer = self.get_serializer(queryset[:50], many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def import_logs(self, request):
        """Get import logs."""
        logs = BankStatementImportLog.objects.all()[:20]
        serializer = BankStatementImportLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk delete bank statements."""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请选择要删除的记录'}, status=status.HTTP_400_BAD_REQUEST)
        
        from django.utils import timezone
        
        deleted_count = BankStatement.objects.filter(id__in=ids, is_deleted=False).update(
            is_deleted=True,
            deleted_at=timezone.now()
        )
        
        return Response({
            'success': True,
            'deleted_count': deleted_count
        })
    
    @action(detail=False, methods=['post'])
    def set_project(self, request):
        """
        批量设置银行流水的关联项目。
        用于将银行流水关联到项目进行成本核算。
        """
        statement_ids = request.data.get('statement_ids', [])
        project_id = request.data.get('project_id')
        
        if not statement_ids:
            return Response({'error': '请选择要关联的流水记录'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not project_id:
            return Response({'error': '请选择项目'}, status=status.HTTP_400_BAD_REQUEST)
        
        from apps.projects.models import Project
        
        try:
            project = Project.objects.get(id=project_id, is_deleted=False)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        updated_count = BankStatement.objects.filter(id__in=statement_ids).update(project=project)
        
        return Response({
            'success': True,
            'updated_count': updated_count,
            'project_code': project.code,
            'project_name': project.name
        })


class BankStatementImportLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for BankStatementImportLog (read-only).
    """
    queryset = BankStatementImportLog.objects.all()
    serializer_class = BankStatementImportLogSerializer
    filterset_fields = ['batch_no']
    search_fields = ['file_name', 'batch_no']
    ordering_fields = ['import_time', 'total_count']

