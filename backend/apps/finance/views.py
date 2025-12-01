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
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin, DataScopeMixin
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


class ExpenseViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
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


class AccountReceivableViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
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


class AccountPayableViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
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
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
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

