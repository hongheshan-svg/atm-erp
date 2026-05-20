"""
Serializers for bank statement.
"""
from rest_framework import serializers

from .bank_statement_models import BankStatement, BankStatementImportLog


class BankStatementSerializer(serializers.ModelSerializer):
    """BankStatement serializer."""
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    match_type_display = serializers.CharField(source='get_match_type_display', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    related_ap_no = serializers.CharField(source='related_ap.ap_no', read_only=True)
    related_ar_no = serializers.CharField(source='related_ar.ar_no', read_only=True)
    related_payment_no = serializers.CharField(source='related_payment.payment_no', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = BankStatement
        fields = [
            'id', 'import_batch', 'import_date', 'source_file',
            'voucher_no', 'counterparty_account', 'transaction_time',
            'transaction_type', 'transaction_type_display',
            'counterparty_name', 'counterparty_bank',
            'purpose', 'summary', 'postscript', 'receipt_info',
            'credit_amount', 'debit_amount', 'balance', 'amount',
            'payment_voucher_type',
            'status', 'status_display', 'match_type', 'match_type_display',
            'supplier', 'supplier_name', 'customer', 'customer_name',
            'related_ap', 'related_ap_no', 'related_ar', 'related_ar_no',
            'related_payment', 'related_payment_no',
            'project', 'project_code', 'project_name',
            'match_confidence', 'match_notes',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['import_batch', 'import_date', 'created_at', 'updated_at']

    def get_amount(self, obj):
        return float(obj.amount)


class BankStatementImportLogSerializer(serializers.ModelSerializer):
    """BankStatementImportLog serializer."""

    class Meta:
        model = BankStatementImportLog
        fields = [
            'id', 'batch_no', 'file_name', 'import_time',
            'total_count', 'success_count', 'error_count', 'matched_count',
            'debit_total', 'credit_total',
            'notes', 'error_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['batch_no', 'import_time', 'created_at', 'updated_at']


class BankStatementMatchSerializer(serializers.Serializer):
    """Serializer for manually matching bank statement to AP/AR."""
    match_type = serializers.ChoiceField(choices=['AP', 'AR', 'EXPENSE', 'OTHER'])
    supplier_id = serializers.IntegerField(required=False, allow_null=True)
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    ap_id = serializers.IntegerField(required=False, allow_null=True)
    ar_id = serializers.IntegerField(required=False, allow_null=True)
    project_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

