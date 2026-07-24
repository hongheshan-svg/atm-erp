"""银行流水自动匹配的名称规范化测试。

对方单位名与主数据里客户/供应商名常因全角/半角括号（）()、空格差异而无法精确匹配，
导致本应命中的记录退化为「未匹配」甚至被旧逻辑错配。精确匹配阶段应先做括号/空格
规范化，使「考泰斯（长春）」能命中「考泰斯(长春)」。
"""
from django.test import TestCase, override_settings

from apps.finance.bank_statement_models import BankStatement
from apps.masterdata.models import Customer, Supplier


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class AutoMatchBracketNormalizeTest(TestCase):
    def test_customer_fullwidth_bracket_matches_halfwidth_customer(self):
        # 客户主数据用半角括号
        customer = Customer.objects.create(code='C-KTS-CC', name='考泰斯(长春)塑料技术有限公司')
        # 银行流水对方单位用全角括号（银行导出常见）
        statement = BankStatement(
            counterparty_name='考泰斯（长春）塑料技术有限公司',
            transaction_type='CREDIT',
        )
        matched, confidence = statement.auto_match_customer()
        self.assertEqual(matched, customer)
        self.assertEqual(confidence, 100.0)

    def test_supplier_fullwidth_bracket_matches_halfwidth_supplier(self):
        supplier = Supplier.objects.create(code='S-XX-BJ', name='鑫鑫(北京)机电设备有限公司')
        statement = BankStatement(
            counterparty_name='鑫鑫（北京）机电设备有限公司',
            transaction_type='DEBIT',
        )
        matched, confidence = statement.auto_match_supplier()
        self.assertEqual(matched, supplier)
        self.assertEqual(confidence, 100.0)

    def test_customer_exact_same_name_still_matches(self):
        # 回归:完全相同的名字仍应精确命中 100%
        customer = Customer.objects.create(code='C-SW', name='上海商纬科技有限公司')
        statement = BankStatement(
            counterparty_name='上海商纬科技有限公司',
            transaction_type='CREDIT',
        )
        matched, confidence = statement.auto_match_customer()
        self.assertEqual(matched, customer)
        self.assertEqual(confidence, 100.0)

    def test_unrelated_company_does_not_falsematch(self):
        # 回归:无关公司不应被错配(旧 bug 曾把上海商纬配成考泰斯)
        Customer.objects.create(code='C-KTS-CQ', name='考泰斯(重庆)塑料技术有限公司')
        statement = BankStatement(
            counterparty_name='上海商纬科技有限公司',
            transaction_type='CREDIT',
        )
        matched, _confidence = statement.auto_match_customer()
        self.assertIsNone(matched)
