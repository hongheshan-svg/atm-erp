from django.contrib import admin

from .models import AccountPayable, AccountReceivable, Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['expense_no', 'user', 'project', 'department', 'category', 'amount', 'status', 'expense_date']
    list_filter = ['status', 'category', 'expense_date']
    search_fields = ['expense_no', 'user__username']
    ordering = ['-created_at']


@admin.register(AccountReceivable)
class AccountReceivableAdmin(admin.ModelAdmin):
    list_display = ['ar_no', 'customer', 'project', 'amount_due', 'amount_paid', 'due_date', 'status']
    list_filter = ['status', 'due_date']
    search_fields = ['ar_no', 'customer__name', 'invoice_no']
    ordering = ['-created_at']


@admin.register(AccountPayable)
class AccountPayableAdmin(admin.ModelAdmin):
    list_display = ['ap_no', 'supplier', 'amount_due', 'amount_paid', 'due_date', 'status']
    list_filter = ['status', 'due_date']
    search_fields = ['ap_no', 'supplier__name', 'invoice_no']
    ordering = ['-created_at']
