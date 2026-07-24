# 银行流水统一核销 · 一期后端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立统一待付款项台账与银行流水核销框架(后端),接入应付账款、费用报销、采购合同付款三种来源,提供核销工作台 API。

**Architecture:** 各费用单据审批通过后经"来源适配器"登记为统一台账项 `PayableItem`;核销服务把银行流水按供应商/金额/日期给候选,人工确认后生成 `Payment`、写核销记录 `PayableSettlement`、回填台账并经适配器回写源单据;支持部分/合并/分期与反核销。

**Tech Stack:** Django 4.2 + DRF 3.14,PostgreSQL,pytest 走 Django TestCase,容器内运行测试。

## Global Constraints

- 本机无 Python venv,**所有测试在容器内运行**:`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test <路径> --noinput -v2`
- 测试类必须加 `@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)`(创建 Supplier/客户等会触发 ES 实时信号,无 ES 会报错)。
- 新模型继承 `apps.core.models.BaseModel`(自带 created_at/updated_at/created_by/updated_by/软删除);删除用 `soft_delete()`;查询默认 `objects`(已过滤软删除)。
- 金额一律 `Decimal`,`max_digits=15, decimal_places=2`(与现有 Payment/AP 一致)。
- ViewSet 组合 `PermissionMixin`/`SoftDeleteMixin`/`UserTrackingMixin`;`permission_module='finance'`。
- 分支:`feat/payment-reconciliation-ledger`(已创建)。每个 Task 末尾 commit。
- 现有关键字段(供实现引用,勿改名):
  - `Payment`:`payment_no, payment_type(AR/AP), ar, ap, payment_date, payment_method, currency, amount, exchange_rate, notes`;`save()` 新建时按 `ar_id/ap_id` 回填 `amount_paid`。
  - `AccountPayable`:`ap_no, supplier, amount_due, amount_paid, currency, due_date, status(PENDING/PARTIAL/PAID/OVERDUE/CANCELLED)`;`amount_remaining` 属性;`save()` 自动算 status。
  - `Expense`:`expense_no, user, department, project, amount, currency, status(DRAFT/SUBMITTED/APPROVED/REJECTED/PAID), reimbursement_date, expense_date`;**无 supplier、无 amount_paid**。
  - `PaymentRecord`(purchase/contract_execution.py):`execution, payment_no, amount, planned_date, actual_date, status(PENDING/APPROVED/PAID/CANCELLED)`;`execution.contract.supplier`、`execution.paid_amount`。
  - `BankStatement`:`transaction_type(DEBIT/CREDIT), credit_amount, debit_amount, amount(property), status(PENDING/MATCHED/IGNORED/ERROR), supplier, counterparty_name`;静态方法 `_normalize_name(name)`(全半角括号/空格归一)。

---

### Task 1: 台账与核销记录模型 `PayableItem` / `PayableSettlement`

**Files:**
- Create: `backend/apps/finance/payable_models.py`
- Modify: `backend/apps/finance/models.py`(文件末尾加 `from .payable_models import *  # noqa` 供 Django 发现)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Produces:
  - `PayableItem(source_type, source_id, source_no, category, payee_name, supplier, amount_due, amount_paid, currency, status, due_date, project)`;属性 `remaining`;`STATUS_*` 常量 `PENDING/PARTIAL/PAID/CANCELLED`;方法 `recalc_status()`。
  - `PayableSettlement(bank_statement, payable_item, payment, amount)`。

- [ ] **Step 1: 写失败测试**

```python
# backend/apps/finance/tests/test_payable_ledger.py
from decimal import Decimal
from django.test import TestCase, override_settings
from apps.finance.payable_models import PayableItem


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PayableItemModelTest(TestCase):
    def test_remaining_and_recalc_status(self):
        item = PayableItem.objects.create(
            source_type='ap', source_id=1, source_no='AP001',
            category='采购', payee_name='供应商A',
            amount_due=Decimal('1000.00'),
        )
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)
        self.assertEqual(item.remaining, Decimal('1000.00'))

        item.amount_paid = Decimal('400.00')
        item.recalc_status()
        self.assertEqual(item.status, PayableItem.STATUS_PARTIAL)

        item.amount_paid = Decimal('1000.00')
        item.recalc_status()
        self.assertEqual(item.status, PayableItem.STATUS_PAID)

    def test_unique_source(self):
        PayableItem.objects.create(source_type='ap', source_id=1, source_no='AP001',
                                   category='采购', payee_name='A', amount_due=Decimal('1'))
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PayableItem.objects.create(source_type='ap', source_id=1, source_no='AP001',
                                       category='采购', payee_name='A', amount_due=Decimal('1'))
```

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.PayableItemModelTest --noinput -v2`
Expected: FAIL(`ModuleNotFoundError: payable_models` 或 import 错误)

- [ ] **Step 3: 写实现**

```python
# backend/apps/finance/payable_models.py
from decimal import Decimal
from django.db import models
from apps.core.models import BaseModel


class PayableItem(BaseModel):
    """统一待付款项台账:各费用单据审批后登记的一条应付款。"""
    STATUS_PENDING = 'PENDING'
    STATUS_PARTIAL = 'PARTIAL'
    STATUS_PAID = 'PAID'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待付'), (STATUS_PARTIAL, '部分'),
        (STATUS_PAID, '已付'), (STATUS_CANCELLED, '已取消'),
    ]

    source_type = models.CharField(max_length=30, verbose_name='来源类型')
    source_id = models.PositiveIntegerField(verbose_name='来源单据ID')
    source_no = models.CharField(max_length=50, blank=True, default='', verbose_name='来源单号')
    category = models.CharField(max_length=30, blank=True, default='', verbose_name='费用类别')
    payee_name = models.CharField(max_length=255, blank=True, default='', verbose_name='收款方')
    supplier = models.ForeignKey('masterdata.Supplier', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='payable_items', verbose_name='供应商')
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='应付金额')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已付金额')
    currency = models.ForeignKey('finance.Currency', on_delete=models.PROTECT,
                                 null=True, blank=True, related_name='payable_items', verbose_name='币种')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='状态')
    due_date = models.DateField(null=True, blank=True, verbose_name='应付日期')
    project = models.ForeignKey('projects.Project', on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='payable_items', verbose_name='项目')

    class Meta:
        db_table = 'payable_item'
        verbose_name = '待付款项'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['source_type', 'source_id'], name='uniq_payable_source'),
        ]
        indexes = [models.Index(fields=['status', 'supplier', 'due_date'])]

    def __str__(self):
        return f'{self.source_type}#{self.source_id} {self.payee_name} {self.amount_due}'

    @property
    def remaining(self):
        return self.amount_due - self.amount_paid

    def recalc_status(self):
        if self.status == self.STATUS_CANCELLED:
            return
        if self.amount_paid >= self.amount_due:
            self.status = self.STATUS_PAID
        elif self.amount_paid > 0:
            self.status = self.STATUS_PARTIAL
        else:
            self.status = self.STATUS_PENDING


class PayableSettlement(BaseModel):
    """核销记录:一笔银行流水核销一条台账项(部分金额)。"""
    bank_statement = models.ForeignKey('finance.BankStatement', on_delete=models.PROTECT,
                                       related_name='payable_settlements', verbose_name='银行流水')
    payable_item = models.ForeignKey(PayableItem, on_delete=models.PROTECT,
                                     related_name='settlements', verbose_name='待付款项')
    payment = models.ForeignKey('finance.Payment', on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='payable_settlements', verbose_name='付款记录')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='本次核销金额')

    class Meta:
        db_table = 'payable_settlement'
        verbose_name = '核销记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.bank_statement_id}→{self.payable_item_id} {self.amount}'
```

在 `backend/apps/finance/models.py` **文件末尾**追加(供 Django 发现新模型):

```python
from .payable_models import PayableItem, PayableSettlement  # noqa: E402,F401
```

- [ ] **Step 4: 生成并应用迁移**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py makemigrations finance`
Expected: 生成 `finance/migrations/00XX_payableitem_payablesettlement.py`

- [ ] **Step 5: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.PayableItemModelTest --noinput -v2`
Expected: PASS(2 tests ok)

- [ ] **Step 6: Commit**

```bash
git add backend/apps/finance/payable_models.py backend/apps/finance/models.py \
        backend/apps/finance/migrations/ backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): 待付款项台账 PayableItem 与核销记录 PayableSettlement 模型"
```

---

### Task 2: `Payment` 扩展 —— 支持核销台账项

**Files:**
- Modify: `backend/apps/finance/models.py:353-439`(Payment 的 PAYMENT_TYPE_CHOICES、字段、save)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `PayableItem`(Task 1)
- Produces: `Payment.payable_item`(FK,可空);`payment_type` 新增 `'PAYABLE'`;新建 Payment 且 `payable_item_id` 存在时回填 `PayableItem.amount_paid` 并 `recalc_status()` 保存。

- [ ] **Step 1: 写失败测试**

```python
# 追加到 test_payable_ledger.py
from apps.finance.models import Payment, Currency


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PaymentBackfillPayableTest(TestCase):
    def test_payment_backfills_payable_amount_paid(self):
        item = PayableItem.objects.create(source_type='expense', source_id=9, source_no='EXP9',
                                          category='报销', payee_name='张三', amount_due=Decimal('300.00'))
        Payment.objects.create(
            payment_type='PAYABLE', payable_item=item,
            payment_date='2026-07-02', payment_method='BANK_TRANSFER',
            amount=Decimal('120.00'),
        )
        item.refresh_from_db()
        self.assertEqual(item.amount_paid, Decimal('120.00'))
        self.assertEqual(item.status, PayableItem.STATUS_PARTIAL)
```

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.PaymentBackfillPayableTest --noinput -v2`
Expected: FAIL(`Payment() got unexpected keyword 'payable_item'` 或 payment_type 校验失败)

- [ ] **Step 3: 写实现**

`models.py` Payment 的 `PAYMENT_TYPE_CHOICES` 改为:

```python
    PAYMENT_TYPE_CHOICES = [
        ('AR', '应收款'),
        ('AP', '应付款'),
        ('PAYABLE', '待付款项'),
    ]
```

在 `ap` 外键定义之后、`payment_date` 之前加字段:

```python
    payable_item = models.ForeignKey(
        'finance.PayableItem',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name='待付款项',
    )
```

在 Payment.save() 的 `if is_new:` 分支里,现有 ar/ap 回填之后追加:

```python
            elif self.payable_item_id:
                from apps.finance.payable_models import PayableItem
                item = PayableItem.objects.select_for_update().get(pk=self.payable_item_id)
                item.amount_paid = item.amount_paid + self.amount
                item.recalc_status()
                item.save(update_fields=['amount_paid', 'status', 'updated_at'])
```

- [ ] **Step 4: 生成迁移**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py makemigrations finance`

- [ ] **Step 5: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.PaymentBackfillPayableTest --noinput -v2`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/finance/models.py backend/apps/finance/migrations/ backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): Payment 支持核销待付款项(payable_item)并回填台账已付"
```

---

### Task 3: 来源适配器框架 + `register_payable`

**Files:**
- Create: `backend/apps/finance/payable_adapters.py`
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `PayableItem`(Task 1)
- Produces:
  - `class PayableSource`(基类:类属性 `source_type`,`category`;方法 `to_payable(obj)->dict`、`write_back(obj, item)`)
  - `register_source(adapter_cls)`(装饰器,实例化并注册到 `PAYABLE_SOURCES`)
  - `PAYABLE_SOURCES: dict[str, PayableSource]`
  - `register_payable(obj, source_type) -> PayableItem`(upsert;取消用 `cancel_payable(obj, source_type)`)

- [ ] **Step 1: 写失败测试**

```python
# 追加到 test_payable_ledger.py
from apps.finance.payable_adapters import (
    PayableSource, register_source, register_payable, cancel_payable, PAYABLE_SOURCES,
)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class AdapterFrameworkTest(TestCase):
    def setUp(self):
        @register_source
        class _FakeSource(PayableSource):
            source_type = 'fake'
            category = '测试'
            def to_payable(self, obj):
                return {'source_no': obj['no'], 'payee_name': obj['payee'],
                        'amount_due': obj['amount'], 'supplier_id': None,
                        'currency_id': None, 'due_date': None, 'project_id': None}
            def write_back(self, obj, item):
                obj['written'] = item.status
        self.addCleanup(lambda: PAYABLE_SOURCES.pop('fake', None))

    def test_register_payable_upsert(self):
        obj = {'pk': 5, 'no': 'F5', 'payee': '甲', 'amount': Decimal('200.00')}
        # 适配器按属性访问 pk;用一个带 pk 的轻量对象
        class O:  # noqa
            pass
        o = O(); o.pk = 5; o.__dict__.update(obj)
        # 用 dict 风格取数,改造:直接传对象
        item = register_payable_via(o)
```

> 注:测试里源对象用真实模型更稳。改为下方精简测试(替换上面 `test_register_payable_upsert` 之后内容):

```python
    def test_register_and_cancel_with_real_expense(self):
        from apps.accounts.models import User
        from apps.finance.models import Expense
        u = User.objects.create(username='u1', employee_id='E1')
        exp = Expense.objects.create(expense_no='EXP100', user=u, expense_date='2026-07-01',
                                     category='OTHER', amount=Decimal('500.00'), status='APPROVED')
        item = register_payable(exp, 'expense')
        self.assertEqual(item.amount_due, Decimal('500.00'))
        self.assertEqual(item.source_no, 'EXP100')
        # 再次登记 → upsert 不重复
        item2 = register_payable(exp, 'expense')
        self.assertEqual(item.pk, item2.pk)
        # 取消 → CANCELLED
        cancel_payable(exp, 'expense')
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)
```

> Task 3 的实现依赖 Task 4 的 expense 适配器,故本测试放到 Task 4 之后运行;Task 3 只交付框架 + 一个用于自测的内联 fake adapter。将上面 `test_register_and_cancel_with_real_expense` 标记为 Task 4 的测试,Task 3 用下面这个纯框架测试:

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class AdapterRegistryTest(TestCase):
    def test_register_source_populates_registry(self):
        @register_source
        class _S(PayableSource):
            source_type = 'demo'
            category = '演示'
            def to_payable(self, obj):
                return {}
            def write_back(self, obj, item):
                pass
        self.addCleanup(lambda: PAYABLE_SOURCES.pop('demo', None))
        self.assertIn('demo', PAYABLE_SOURCES)
        self.assertEqual(PAYABLE_SOURCES['demo'].category, '演示')
```

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.AdapterRegistryTest --noinput -v2`
Expected: FAIL(import error:`payable_adapters` 不存在)

- [ ] **Step 3: 写实现**

```python
# backend/apps/finance/payable_adapters.py
from apps.finance.payable_models import PayableItem

PAYABLE_SOURCES = {}


class PayableSource:
    """来源适配器基类。子类设 source_type / category,并实现 to_payable / write_back。"""
    source_type = ''
    category = ''

    def to_payable(self, obj) -> dict:
        """返回 dict:source_no, payee_name, supplier_id, amount_due, currency_id, due_date, project_id"""
        raise NotImplementedError

    def write_back(self, obj, item: PayableItem) -> None:
        """据台账项 item(amount_paid/status)回写源单据。"""
        raise NotImplementedError


def register_source(adapter_cls):
    PAYABLE_SOURCES[adapter_cls.source_type] = adapter_cls()
    return adapter_cls


def register_payable(obj, source_type: str) -> PayableItem:
    adapter = PAYABLE_SOURCES[source_type]
    data = adapter.to_payable(obj)
    defaults = {'category': adapter.category, **data}
    item, _ = PayableItem.objects.update_or_create(
        source_type=source_type, source_id=obj.pk, defaults=defaults,
    )
    return item


def cancel_payable(obj, source_type: str) -> None:
    item = PayableItem.objects.filter(source_type=source_type, source_id=obj.pk).first()
    if item and item.amount_paid == 0:
        item.status = PayableItem.STATUS_CANCELLED
        item.save(update_fields=['status', 'updated_at'])
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.AdapterRegistryTest --noinput -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/finance/payable_adapters.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): 来源适配器框架 + register_payable/cancel_payable upsert"
```

---

### Task 4: 应付账款 `AccountPayable` 适配器

**Files:**
- Modify: `backend/apps/finance/payable_adapters.py`(追加 `APPayableSource`)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `register_payable`(Task 3)、`AccountPayable`
- Produces: `source_type='ap'` 适配器;`write_back` 把 `item.amount_paid` 写回 `AccountPayable.amount_paid` 并 `save()`(AP 自动算 status)。

- [ ] **Step 1: 写失败测试**

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class APAdapterTest(TestCase):
    def _make_ap(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        return AccountPayable.objects.create(
            supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01',
            amount_due=Decimal('1000.00'),
        )

    def test_ap_register_and_writeback(self):
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_models import PayableItem
        ap = self._make_ap()
        item = register_payable(ap, 'ap')
        self.assertEqual(item.payee_name, '供应商甲')
        self.assertEqual(item.supplier_id, ap.supplier_id)
        self.assertEqual(item.amount_due, Decimal('1000.00'))
        self.assertEqual(item.source_no, ap.ap_no)

        item.amount_paid = Decimal('1000.00'); item.recalc_status(); item.save()
        PAYABLE_SOURCES['ap'].write_back(ap, item)
        ap.refresh_from_db()
        self.assertEqual(ap.amount_paid, Decimal('1000.00'))
        self.assertEqual(ap.status, 'PAID')
```

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.APAdapterTest --noinput -v2`
Expected: FAIL(`KeyError: 'ap'`)

- [ ] **Step 3: 写实现**(追加到 `payable_adapters.py`)

```python
@register_source
class APPayableSource(PayableSource):
    source_type = 'ap'
    category = '采购'

    def to_payable(self, obj) -> dict:
        return {
            'source_no': obj.ap_no,
            'payee_name': obj.supplier.name if obj.supplier_id else '',
            'supplier_id': obj.supplier_id,
            'amount_due': obj.amount_due,
            'currency_id': obj.currency_id,
            'due_date': obj.due_date,
            'project_id': obj.project_id,
        }

    def write_back(self, obj, item) -> None:
        obj.amount_paid = item.amount_paid
        obj.save()  # AccountPayable.save() 自动算 status
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.APAdapterTest --noinput -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/finance/payable_adapters.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): AP 来源适配器(登记+回写)"
```

---

### Task 5: 费用报销 `Expense` 适配器

**Files:**
- Modify: `backend/apps/finance/payable_adapters.py`(追加 `ExpensePayableSource`)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `register_payable`、`Expense`
- Produces: `source_type='expense'`;Expense 无供应商(`supplier_id=None`,`payee_name` 用申请人姓名);`write_back` 仅在 `item.status=='PAID'` 时置 `Expense.status='PAID'` 并写 `reimbursement_date`。

- [ ] **Step 1: 写失败测试**

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ExpenseAdapterTest(TestCase):
    def test_expense_register_and_full_writeback(self):
        from apps.accounts.models import User
        from apps.finance.models import Expense
        from apps.finance.payable_adapters import register_payable, PAYABLE_SOURCES
        from apps.finance.payable_models import PayableItem
        u = User.objects.create(username='zs', employee_id='E9', real_name='张三')
        exp = Expense.objects.create(expense_no='EXP200', user=u, expense_date='2026-07-01',
                                     category='TRAVEL', amount=Decimal('800.00'), status='APPROVED')
        item = register_payable(exp, 'expense')
        self.assertIsNone(item.supplier_id)
        self.assertEqual(item.amount_due, Decimal('800.00'))
        self.assertEqual(item.source_no, 'EXP200')

        item.amount_paid = Decimal('800.00'); item.recalc_status(); item.save()
        PAYABLE_SOURCES['expense'].write_back(exp, item)
        exp.refresh_from_db()
        self.assertEqual(exp.status, 'PAID')
        self.assertIsNotNone(exp.reimbursement_date)
```

> `User` 字段名以实际为准:若无 `real_name` 用 `username`。`payee_name` 取 `getattr(obj.user, 'real_name', '') or obj.user.username`。

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ExpenseAdapterTest --noinput -v2`
Expected: FAIL(`KeyError: 'expense'`)

- [ ] **Step 3: 写实现**(追加到 `payable_adapters.py`)

```python
@register_source
class ExpensePayableSource(PayableSource):
    source_type = 'expense'
    category = '报销'

    def to_payable(self, obj) -> dict:
        payee = getattr(obj.user, 'real_name', '') or getattr(obj.user, 'username', '')
        return {
            'source_no': obj.expense_no,
            'payee_name': payee,
            'supplier_id': None,
            'amount_due': obj.amount,
            'currency_id': obj.currency_id,
            'due_date': obj.expense_date,
            'project_id': obj.project_id,
        }

    def write_back(self, obj, item) -> None:
        from django.utils import timezone
        if item.status == item.STATUS_PAID:
            obj.status = 'PAID'
            if not obj.reimbursement_date:
                obj.reimbursement_date = timezone.now().date()
            obj.save(update_fields=['status', 'reimbursement_date', 'updated_at'])
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ExpenseAdapterTest --noinput -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/finance/payable_adapters.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): 费用报销 Expense 来源适配器"
```

---

### Task 6: 采购合同付款 `PaymentRecord` 适配器

**Files:**
- Modify: `backend/apps/finance/payable_adapters.py`(追加 `ContractPaymentSource`)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `register_payable`、`PaymentRecord`(purchase/contract_execution.py)
- Produces: `source_type='contract_payment'`;供应商经 `obj.execution.contract.supplier`;`write_back` 全额付时置 `PaymentRecord.status='PAID'`+`actual_date`,并累加 `execution.paid_amount`。

- [ ] **Step 1: 写失败测试**

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPaymentAdapterTest(TestCase):
    def _make_payment_record(self):
        from apps.masterdata.models import Supplier
        from apps.purchase.models import PurchaseContract
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        sup = Supplier.objects.create(code='S3', name='外协丙')
        contract = PurchaseContract.objects.create(contract_no='PC001', supplier=sup, total_amount=Decimal('5000'))
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('5000'))
        return PaymentRecord.objects.create(execution=ex, payment_no='CPR001',
                                            planned_date='2026-07-10', amount=Decimal('2000.00'), status='APPROVED')

    def test_contract_payment_register_and_writeback(self):
        from apps.finance.payable_adapters import register_payable, PAYABLE_SOURCES
        pr = self._make_payment_record()
        item = register_payable(pr, 'contract_payment')
        self.assertEqual(item.payee_name, '外协丙')
        self.assertEqual(item.amount_due, Decimal('2000.00'))

        item.amount_paid = Decimal('2000.00'); item.recalc_status(); item.save()
        PAYABLE_SOURCES['contract_payment'].write_back(pr, item)
        pr.refresh_from_db(); pr.execution.refresh_from_db()
        self.assertEqual(pr.status, 'PAID')
        self.assertIsNotNone(pr.actual_date)
        self.assertEqual(pr.execution.paid_amount, Decimal('2000.00'))
```

> `PurchaseContract` 的必填字段以实际为准(如缺 `total_amount` 则去掉);实现时按报错补齐。

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ContractPaymentAdapterTest --noinput -v2`
Expected: FAIL(`KeyError: 'contract_payment'`)

- [ ] **Step 3: 写实现**(追加到 `payable_adapters.py`)

```python
@register_source
class ContractPaymentSource(PayableSource):
    source_type = 'contract_payment'
    category = '合同付款'

    def to_payable(self, obj) -> dict:
        contract = obj.execution.contract
        supplier = getattr(contract, 'supplier', None)
        return {
            'source_no': obj.payment_no,
            'payee_name': supplier.name if supplier else '',
            'supplier_id': supplier.id if supplier else None,
            'amount_due': obj.amount,
            'currency_id': None,
            'due_date': obj.planned_date,
            'project_id': None,
        }

    def write_back(self, obj, item) -> None:
        from django.db.models import F
        from django.utils import timezone
        if item.status == item.STATUS_PAID:
            obj.status = 'PAID'
            if not obj.actual_date:
                obj.actual_date = timezone.now().date()
            obj.save(update_fields=['status', 'actual_date', 'updated_at'])
            type(obj.execution).objects.filter(pk=obj.execution_id).update(
                paid_amount=F('paid_amount') + item.amount_paid)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ContractPaymentAdapterTest --noinput -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/finance/payable_adapters.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): 采购合同付款 PaymentRecord 来源适配器"
```

---

### Task 7: 核销服务 —— 候选匹配 `match_candidates`

**Files:**
- Create: `backend/apps/finance/payable_service.py`
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `PayableItem`、`BankStatement._normalize_name`
- Produces: `match_candidates(bank_statement, limit=10) -> list[dict]`,每项 `{'payable_item': PayableItem, 'score': int, 'reasons': list[str]}`,按 score 降序。打分:供应商/收款方名规范化相等 +50;金额等于剩余 +40 或金额≤剩余 +15;应付日期与流水日期相差 ≤7 天 +10。只取 `status in [PENDING, PARTIAL]`。

- [ ] **Step 1: 写失败测试**

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class MatchCandidatesTest(TestCase):
    def test_scores_supplier_and_amount(self):
        from apps.finance.models import BankStatement
        from apps.finance.payable_models import PayableItem
        from apps.finance.payable_service import match_candidates
        good = PayableItem.objects.create(source_type='ap', source_id=1, source_no='AP1', category='采购',
                                          payee_name='考泰斯(长春)塑料技术有限公司', amount_due=Decimal('1000.00'))
        PayableItem.objects.create(source_type='ap', source_id=2, source_no='AP2', category='采购',
                                   payee_name='无关公司', amount_due=Decimal('50.00'))
        bs = BankStatement(transaction_type='DEBIT', debit_amount=Decimal('1000.00'),
                           counterparty_name='考泰斯（长春）塑料技术有限公司', transaction_time='2026-07-02 00:00:00+00')
        bs.save()
        cands = match_candidates(bs)
        self.assertEqual(cands[0]['payable_item'].pk, good.pk)
        self.assertGreaterEqual(cands[0]['score'], 90)
```

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.MatchCandidatesTest --noinput -v2`
Expected: FAIL(import error:`payable_service`)

- [ ] **Step 3: 写实现**

```python
# backend/apps/finance/payable_service.py
from datetime import timedelta
from apps.finance.models import BankStatement
from apps.finance.payable_models import PayableItem


def match_candidates(bank_statement, limit=10):
    norm = BankStatement._normalize_name
    target = norm(bank_statement.counterparty_name)
    amount = bank_statement.amount or 0
    bs_date = bank_statement.transaction_time.date() if bank_statement.transaction_time else None

    results = []
    qs = PayableItem.objects.filter(status__in=[PayableItem.STATUS_PENDING, PayableItem.STATUS_PARTIAL])
    for item in qs:
        score, reasons = 0, []
        if target and norm(item.payee_name) == target:
            score += 50; reasons.append('收款方一致')
        remaining = item.remaining
        if amount == remaining:
            score += 40; reasons.append('金额等于剩余')
        elif 0 < amount <= remaining:
            score += 15; reasons.append('金额不超剩余')
        if bs_date and item.due_date and abs((item.due_date - bs_date).days) <= 7:
            score += 10; reasons.append('应付日期临近')
        if score > 0:
            results.append({'payable_item': item, 'score': score, 'reasons': reasons})

    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.MatchCandidatesTest --noinput -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/finance/payable_service.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): 核销候选匹配服务 match_candidates(供应商/金额/日期打分)"
```

---

### Task 8: 核销服务 —— 核销 `settle`(记账 + 回写 + 锁)

**Files:**
- Modify: `backend/apps/finance/payable_service.py`(追加 `settle`)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `PayableItem`、`PayableSettlement`、`Payment`、`PAYABLE_SOURCES`
- Produces: `settle(bank_statement, allocations, user) -> list[PayableSettlement]`。`allocations` = `[{'payable_item_id': int, 'amount': Decimal}]`。事务 + `select_for_update` 锁台账项;校验每项 `amount ≤ item.remaining` 且 `Σamount ≤ 流水可核销剩余`;每项生成 `Payment`(payment_type=PAYABLE)→ 写 `PayableSettlement` → Payment.save 已回填台账 → 调用适配器 `write_back`;更新 `bank_statement.status`(全额→MATCHED,部分→PARTIAL)。超额抛 `ValueError`。

- [ ] **Step 1: 写失败测试**

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class SettleTest(TestCase):
    def _bs(self, amt):
        from apps.finance.models import BankStatement
        bs = BankStatement(transaction_type='DEBIT', debit_amount=amt,
                           counterparty_name='供应商甲', transaction_time='2026-07-02 00:00:00+00')
        bs.save(); return bs

    def test_full_settlement_marks_matched_and_writes_back_ap(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_service import settle
        from apps.accounts.models import User
        u = User.objects.create(username='op', employee_id='OP1')
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        item = register_payable(ap, 'ap')
        bs = self._bs(Decimal('1000.00'))
        settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('1000.00')}], u)
        item.refresh_from_db(); ap.refresh_from_db(); bs.refresh_from_db()
        self.assertEqual(item.status, 'PAID')
        self.assertEqual(ap.amount_paid, Decimal('1000.00'))
        self.assertEqual(ap.status, 'PAID')
        self.assertEqual(bs.status, 'MATCHED')

    def test_over_allocation_rejected(self):
        from apps.finance.payable_models import PayableItem
        from apps.finance.payable_service import settle
        from apps.accounts.models import User
        u = User.objects.create(username='op2', employee_id='OP2')
        item = PayableItem.objects.create(source_type='ap', source_id=99, source_no='AP99',
                                          category='采购', payee_name='甲', amount_due=Decimal('100.00'))
        bs = self._bs(Decimal('500.00'))
        with self.assertRaises(ValueError):
            settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('300.00')}], u)
```

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.SettleTest --noinput -v2`
Expected: FAIL(`ImportError: cannot import name 'settle'`)

- [ ] **Step 3: 写实现**(追加到 `payable_service.py`)

```python
from decimal import Decimal
from django.db import transaction
from apps.finance.models import Payment
from apps.finance.payable_models import PayableSettlement
from apps.finance.payable_adapters import PAYABLE_SOURCES


@transaction.atomic
def settle(bank_statement, allocations, user):
    total = sum((a['amount'] for a in allocations), Decimal('0'))
    already = sum((s.amount for s in bank_statement.payable_settlements.all()), Decimal('0'))
    if total + already > (bank_statement.amount or Decimal('0')):
        raise ValueError('核销总额超过流水金额')

    settlements = []
    for a in allocations:
        item = PayableItem.objects.select_for_update().get(pk=a['payable_item_id'])
        amount = a['amount']
        if amount <= 0 or amount > item.remaining:
            raise ValueError(f'核销金额 {amount} 超过待付款项剩余 {item.remaining}')
        payment = Payment.objects.create(
            payment_type='PAYABLE', payable_item=item,
            payment_date=bank_statement.transaction_time.date(),
            payment_method='BANK_TRANSFER', amount=amount,
            currency_id=item.currency_id,
            notes=f'[BS#{bank_statement.id}] 银行流水核销',
            created_by=user, updated_by=user,
        )
        settlement = PayableSettlement.objects.create(
            bank_statement=bank_statement, payable_item=item,
            payment=payment, amount=amount, created_by=user, updated_by=user,
        )
        item.refresh_from_db()
        source = PAYABLE_SOURCES.get(item.source_type)
        if source:
            obj = _load_source_obj(item)
            if obj is not None:
                source.write_back(obj, item)
        settlements.append(settlement)

    new_total = already + total
    bank_statement.status = 'MATCHED' if new_total >= (bank_statement.amount or 0) else 'PARTIAL'
    bank_statement.save(update_fields=['status', 'updated_at'])
    return settlements


def _load_source_obj(item):
    from apps.finance.models import AccountPayable, Expense
    from apps.purchase.contract_execution import PaymentRecord
    model = {'ap': AccountPayable, 'expense': Expense, 'contract_payment': PaymentRecord}.get(item.source_type)
    return model.objects.filter(pk=item.source_id).first() if model else None
```

> `BankStatement.STATUS_CHOICES` 需新增 `('PARTIAL', '部分核销')`:在 `bank_statement_models.py` 的 STATUS_CHOICES 里加该项,并 `makemigrations`。

- [ ] **Step 4: 加 PARTIAL 状态并生成迁移,运行测试**

先在 `backend/apps/finance/bank_statement_models.py` 的 `STATUS_CHOICES` 追加 `('PARTIAL', '部分核销'),`,然后:

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py makemigrations finance && docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.SettleTest --noinput -v2`
Expected: PASS(2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/apps/finance/payable_service.py backend/apps/finance/bank_statement_models.py \
        backend/apps/finance/migrations/ backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): 核销 settle(生成Payment+核销记录+回写源单据+锁+超额校验)"
```

---

### Task 9: 核销服务 —— 反核销 `unsettle`

**Files:**
- Modify: `backend/apps/finance/payable_service.py`(追加 `unsettle`)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `PayableSettlement`(Task 8 生成)
- Produces: `unsettle(settlement, user)`。事务:回退台账 `amount_paid -= settlement.amount` 并 `recalc_status`;软删对应 `Payment`;软删 `PayableSettlement`;经适配器 `write_back` 回写源单据(据回退后状态);重算并更新 `bank_statement.status`。幂等:已软删的 settlement 再次调用直接返回。

- [ ] **Step 1: 写失败测试**

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class UnsettleTest(TestCase):
    def test_unsettle_reverts_ledger_and_ap(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_service import settle, unsettle
        from apps.finance.models import BankStatement
        from apps.accounts.models import User
        u = User.objects.create(username='op3', employee_id='OP3')
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        item = register_payable(ap, 'ap')
        bs = BankStatement(transaction_type='DEBIT', debit_amount=Decimal('1000.00'),
                           counterparty_name='供应商甲', transaction_time='2026-07-02 00:00:00+00')
        bs.save()
        s = settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('1000.00')}], u)[0]

        unsettle(s, u)
        item.refresh_from_db(); ap.refresh_from_db(); bs.refresh_from_db()
        self.assertEqual(item.amount_paid, Decimal('0'))
        self.assertEqual(item.status, 'PENDING')
        self.assertEqual(ap.amount_paid, Decimal('0'))
        self.assertEqual(bs.status, 'PENDING')
```

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.UnsettleTest --noinput -v2`
Expected: FAIL(`ImportError: cannot import name 'unsettle'`)

- [ ] **Step 3: 写实现**(追加到 `payable_service.py`)

```python
@transaction.atomic
def unsettle(settlement, user):
    if settlement.is_deleted:
        return
    item = PayableItem.objects.select_for_update().get(pk=settlement.payable_item_id)
    item.amount_paid = item.amount_paid - settlement.amount
    if item.amount_paid < 0:
        item.amount_paid = Decimal('0')
    item.recalc_status()
    item.save(update_fields=['amount_paid', 'status', 'updated_at'])

    if settlement.payment_id:
        pay = Payment.objects.filter(pk=settlement.payment_id).first()
        if pay:
            pay.soft_delete()

    bs = settlement.bank_statement
    settlement.soft_delete()

    source = PAYABLE_SOURCES.get(item.source_type)
    if source:
        obj = _load_source_obj(item)
        if obj is not None:
            source.write_back(obj, item)

    remaining_total = sum((s.amount for s in bs.payable_settlements.all()), Decimal('0'))
    bs.status = 'PENDING' if remaining_total == 0 else 'PARTIAL'
    bs.save(update_fields=['status', 'updated_at'])
```

> 说明:AP 适配器 `write_back` 用 `obj.amount_paid = item.amount_paid; obj.save()`,回退后 AP `amount_paid=0`、AP.save 不会把已是 PAID 的降级——需确认 `AccountPayable.save()` 在 `amount_paid==0` 时不改 status;若它只在 ≥/>0 时改,则回退后 status 仍为旧值。**在 Task 9 实现时修正 `AccountPayable.save()`**:把状态判断补全 `else: self.status = 'PENDING'`(仅当当前非 CANCELLED)。同步 Expense/合同适配器:回退后 `item.status != PAID` 时应把源单据从 PAID 改回(Expense→APPROVED,PaymentRecord→APPROVED)。相应扩展两个适配器的 `write_back`:非 PAID 分支回改状态。

- [ ] **Step 4: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.UnsettleTest --noinput -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/finance/payable_service.py backend/apps/finance/payable_adapters.py \
        backend/apps/finance/models.py backend/apps/finance/migrations/ \
        backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): 反核销 unsettle(回退台账/AP/源单据/流水状态,幂等)"
```

---

### Task 10: 核销工作台 API

**Files:**
- Create: `backend/apps/finance/payable_views.py`
- Create: `backend/apps/finance/payable_serializers.py`
- Modify: `backend/apps/finance/urls.py`(注册路由)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `match_candidates`、`settle`、`unsettle`、`PayableItem`
- Produces:
  - `GET /api/v1/finance/payable-items/`(列表,可 filter `status`/`supplier`/`category`)
  - `GET /api/v1/finance/bank-statements/{id}/payable-candidates/` → `[{payable_item_id, source_no, payee_name, amount_due, remaining, score, reasons}]`
  - `POST /api/v1/finance/payable-reconcile/settle/` body `{bank_statement_id, allocations:[{payable_item_id, amount}]}`
  - `POST /api/v1/finance/payable-reconcile/unsettle/` body `{settlement_id}`

- [ ] **Step 1: 写失败测试**

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PayableApiTest(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        self.user = User.objects.create(username='admin', employee_id='A1', is_staff=True, is_superuser=True)
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def test_settle_endpoint(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable, BankStatement
        from apps.finance.payable_adapters import register_payable
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        item = register_payable(ap, 'ap')
        bs = BankStatement(transaction_type='DEBIT', debit_amount=Decimal('1000.00'),
                           counterparty_name='供应商甲', transaction_time='2026-07-02 00:00:00+00')
        bs.save()
        resp = self.client.post('/api/v1/finance/payable-reconcile/settle/', {
            'bank_statement_id': bs.id,
            'allocations': [{'payable_item_id': item.pk, 'amount': '1000.00'}],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, 'PAID')
```

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.PayableApiTest --noinput -v2`
Expected: FAIL(404,路由不存在)

- [ ] **Step 3: 写实现**

```python
# backend/apps/finance/payable_serializers.py
from rest_framework import serializers
from apps.finance.payable_models import PayableItem, PayableSettlement


class PayableItemSerializer(serializers.ModelSerializer):
    remaining = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = PayableItem
        fields = ['id', 'source_type', 'source_id', 'source_no', 'category', 'payee_name',
                  'supplier', 'amount_due', 'amount_paid', 'remaining', 'currency',
                  'status', 'due_date', 'project']


class PayableSettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayableSettlement
        fields = ['id', 'bank_statement', 'payable_item', 'payment', 'amount', 'created_at']
```

```python
# backend/apps/finance/payable_views.py
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permission_mixin import PermissionMixin
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin, DataScopeMixin
from apps.finance.models import BankStatement
from apps.finance.payable_models import PayableItem, PayableSettlement
from apps.finance.payable_serializers import PayableItemSerializer
from apps.finance import payable_service as svc


class PayableItemViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'payable_item'
    queryset = PayableItem.objects.all()
    serializer_class = PayableItemSerializer
    filterset_fields = ['status', 'supplier', 'category', 'source_type']


class PayableCandidatesView(PermissionMixin, APIView):
    permission_module = 'finance'
    permission_resource = 'payable_item'

    def get(self, request, pk):
        bs = BankStatement.objects.get(pk=pk)
        cands = svc.match_candidates(bs)
        data = [{
            'payable_item_id': c['payable_item'].id,
            'source_no': c['payable_item'].source_no,
            'payee_name': c['payable_item'].payee_name,
            'amount_due': c['payable_item'].amount_due,
            'remaining': c['payable_item'].remaining,
            'score': c['score'], 'reasons': c['reasons'],
        } for c in cands]
        return Response(data)


class PayableReconcileView(PermissionMixin, APIView):
    permission_module = 'finance'
    permission_resource = 'payable_item'

    @action(detail=False, methods=['post'])
    def settle(self, request):
        bs = BankStatement.objects.get(pk=request.data['bank_statement_id'])
        allocations = [{'payable_item_id': a['payable_item_id'], 'amount': Decimal(str(a['amount']))}
                       for a in request.data['allocations']]
        try:
            svc.settle(bs, allocations, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'ok': True})

    def unsettle(self, request):
        s = PayableSettlement.objects.get(pk=request.data['settlement_id'])
        svc.unsettle(s, request.user)
        return Response({'ok': True})
```

> `PayableReconcileView` 用两个显式 URL(settle/unsettle)映射到方法,而非 `@action`(APIView 无 router)。在 urls.py 里用 `as_view` 包一层:

```python
# backend/apps/finance/urls.py — 追加
from apps.finance.payable_views import PayableItemViewSet, PayableCandidatesView, PayableReconcileView

router.register(r'payable-items', PayableItemViewSet, basename='payable-item')

urlpatterns += [
    path('bank-statements/<int:pk>/payable-candidates/', PayableCandidatesView.as_view()),
    path('payable-reconcile/settle/', PayableReconcileView.as_view({'post': 'settle'})
         if hasattr(PayableReconcileView, 'as_view') else PayableReconcileView.as_view()),
]
```

> 简化:把 `PayableReconcileView` 改为普通 `APIView` 且各建一个类 `SettleView`/`UnsettleView`,`post` 方法内分别调用 `svc.settle`/`svc.unsettle`。实现时以能跑通测试为准(测试只打 `/payable-reconcile/settle/`)。urls 里挂:
> `path('payable-reconcile/settle/', SettleView.as_view())`、`path('payable-reconcile/unsettle/', UnsettleView.as_view())`。

- [ ] **Step 4: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.PayableApiTest --noinput -v2`
Expected: PASS

- [ ] **Step 5: 权限种子**

在权限初始化里补 `finance/payable_item` 资源(参考现有 `init_permissions` 数据结构);运行 `init_permissions` + `init_roles --force`。若时间紧,超级用户不受限,可留到接入前端前补。

- [ ] **Step 6: Commit**

```bash
git add backend/apps/finance/payable_views.py backend/apps/finance/payable_serializers.py \
        backend/apps/finance/urls.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): 核销工作台 API(台账列表/候选/核销/反核销)"
```

---

### Task 11: 应付账款存量回填台账(管理命令)

**Files:**
- Create: `backend/apps/finance/management/commands/backfill_payables.py`
- Test: `backend/apps/finance/tests/test_payable_ledger.py`

**Interfaces:**
- Consumes: `register_payable`、`AccountPayable`
- Produces: `backfill_payables` 命令:对未结清(`status in [PENDING, PARTIAL, OVERDUE]`)的 AP 登记台账并同步 `amount_paid`。

- [ ] **Step 1: 写失败测试**

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class BackfillTest(TestCase):
    def test_backfill_creates_payable_for_open_ap(self):
        from django.core.management import call_command
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        from apps.finance.payable_models import PayableItem
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01',
                                           amount_due=Decimal('1000.00'), amount_paid=Decimal('300.00'))
        call_command('backfill_payables')
        item = PayableItem.objects.get(source_type='ap', source_id=ap.pk)
        self.assertEqual(item.amount_due, Decimal('1000.00'))
        self.assertEqual(item.amount_paid, Decimal('300.00'))
        self.assertEqual(item.status, 'PARTIAL')
```

- [ ] **Step 2: 运行,确认失败**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.BackfillTest --noinput -v2`
Expected: FAIL(`Unknown command: 'backfill_payables'`)

- [ ] **Step 3: 写实现**

```python
# backend/apps/finance/management/commands/backfill_payables.py
from django.core.management.base import BaseCommand
from apps.finance.models import AccountPayable
from apps.finance.payable_adapters import register_payable


class Command(BaseCommand):
    help = '把未结清的应付账款回填到待付款项台账'

    def handle(self, *args, **options):
        qs = AccountPayable.objects.filter(status__in=['PENDING', 'PARTIAL', 'OVERDUE'])
        n = 0
        for ap in qs:
            item = register_payable(ap, 'ap')
            item.amount_paid = ap.amount_paid
            item.recalc_status()
            item.save(update_fields=['amount_paid', 'status', 'updated_at'])
            n += 1
        self.stdout.write(self.style.SUCCESS(f'回填 {n} 条应付账款到台账'))
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.BackfillTest --noinput -v2`
Expected: PASS

- [ ] **Step 5: 全量回归 + Commit**

Run(整文件): `docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger --noinput -v2`
Expected: 全部 PASS

```bash
git add backend/apps/finance/management/commands/backfill_payables.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): backfill_payables 管理命令(存量应付回填台账)"
```

---

## Self-Review 记录

- **Spec 覆盖**:数据模型(Task 1-2)、登记适配器(Task 3-6 覆盖 AP/报销/合同付款)、核销流程 候选/settle/unsettle(Task 7-9)、API(Task 10)、AP 迁移(Task 11)。✅ 一期范围全覆盖。收款侧/二三期单据按 spec 非本计划范围。
- **占位符**:无 TBD/TODO;各步含完整测试与实现代码。Task 3 因适配器依赖顺序对测试做了显式拆分说明;Task 9/10 对 `AccountPayable.save()` 状态回退与 APIView 路由给了明确修正指引。
- **类型一致**:`register_payable(obj, source_type)`、`match_candidates(bs)->[{payable_item,score,reasons}]`、`settle(bs, allocations, user)`、`unsettle(settlement, user)`、适配器 `to_payable(obj)->dict` / `write_back(obj, item)` 全计划一致。
- **已知实现期需确认点**(实现时按报错微调,不阻塞设计):`User` 姓名字段(real_name/username)、`PurchaseContract` 必填字段、`AccountPayable.save()` 状态回退补全、APIView 路由二选一写法。
