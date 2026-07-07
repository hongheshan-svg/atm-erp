# 合同付款 pay() 收口 · 统一走核销台账 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 退役采购合同付款的 `PaymentRecordViewSet.pay()` 直接标记付款能力,让合同付款审批通过即经信号登记待付款项台账,`PAID` 只能由银行流水核销驱动。

**Architecture:** 用 `PaymentRecord` 的 `post_save` 信号在 `status=='APPROVED'` 时登记台账、`'CANCELLED'` 时作废(覆盖 直接审批 / 自动通过 / 工作流引擎完成 三条到达路径,因它们最终都经 `PaymentRecord.save()` 落状态);`pay()` 改为返回 409 停用;新增管理命令回填存量 APPROVED 合同付款。

**Tech Stack:** Django 4.2 + DRF 3.14,PostgreSQL,Django TestCase,容器内运行测试。

## Global Constraints

- 本机无 Python venv,**所有测试在容器内运行**:`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test <路径> --noinput -v2`
- 跑测试前清理残留:`docker ps -aq --filter "name=erp-app-run" | xargs -r docker rm -f; docker exec erp-postgres psql -U erp_user -d erp_db -c "DROP DATABASE IF EXISTS test_erp_db;"`
- 测试类必须加 `@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)`。
- 金额一律 `Decimal`。
- 分支 `feat/payment-reconciliation-ledger`(已在其上);每个 Task 末尾 commit。
- 复用件(勿改名):`apps.finance.payable_adapters.register_payable(obj, source_type)`、`cancel_payable(obj, source_type)`;合同付款 `source_type='contract_payment'`,其适配器 `ContractPaymentSource` 已实现 `to_payable`/`write_back`。
- 现有关键事实(实现引用):
  - `PaymentRecord`(`apps.purchase.contract_execution`):`execution, payment_no, amount, planned_date, actual_date, approved_at, status(PENDING/APPROVED/PAID/CANCELLED)`;`execution.contract.supplier`、`execution.paid_amount`。
  - `PaymentRecordViewSet` 路由 basename `payment-record`,挂载于 `/api/purchase/`;`pay` action URL = `/api/purchase/payment-records/{pk}/pay/`。
  - `apps/purchase/signals.py` 已存在并在 `PurchaseConfig.ready()` 被 import;沿用其 `@receiver(post_save, sender=...)` 风格追加,无需改 `apps.py`。

## Task 0:前置确认(已完成,无需改动)

工作流审批完成回写 `PAYMENT_RECORD` 状态用 `payment.save()`(`apps/core/workflow/services.py:686-699`),其中 `APPROVED→status='APPROVED'+save()`、`REJECTED→status='CANCELLED'+save()`、`WITHDRAWN→status='PENDING'+save()`;`submit` 自动通过分支与 `approve` action(`contract_execution.py`)同样走 `.save()`。**结论**:`post_save` 信号覆盖全部审批路径,无需在 action 里补显式 `register_payable`。`CANCELLED` 分支对应信号的 `cancel_payable`。

---

### Task 1:post_save 信号登记合同付款到台账

**Files:**
- Modify: `backend/apps/purchase/signals.py`(追加 receiver;顶部 import 加 `PaymentRecord`)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`(文件末尾追加 `ContractPaymentSignalTest`)

**Interfaces:**
- Consumes: `register_payable(obj, 'contract_payment')`、`cancel_payable(obj, 'contract_payment')`(`apps.finance.payable_adapters`)
- Produces: `PaymentRecord` 保存副作用——`status=='APPROVED'` 时台账存在对应 `PayableItem(source_type='contract_payment', source_id=payment.pk)`;`status=='CANCELLED'` 时该台账项(若 `amount_paid==0`)置 `CANCELLED`。

- [ ] **Step 1: 写失败测试**(追加到 `test_payable_ledger.py` 末尾)

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPaymentSignalTest(TestCase):
    def _make_execution(self, name='外协甲', code='SG1', amount='5000'):
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        sup = Supplier.objects.create(code=code, name=name)
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no=f'PC{code}',
                                                   title='c', contract_date='2026-06-01',
                                                   total_amount=Decimal(amount))
        return ContractExecution.objects.create(contract=contract, contract_amount=Decimal(amount))

    def test_signal_registers_on_create_approved(self):
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution()
        pr = PaymentRecord.objects.create(execution=ex, payment_no='SIGP1', planned_date='2026-07-10',
                                          amount=Decimal('2000.00'), status='APPROVED')
        item = PayableItem.objects.get(source_type='contract_payment', source_id=pr.pk)
        self.assertEqual(item.amount_due, Decimal('2000.00'))
        self.assertEqual(item.payee_name, '外协甲')
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

    def test_signal_registers_on_transition_to_approved(self):
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(name='外协乙', code='SG2')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='SIGP2', planned_date='2026-07-10',
                                          amount=Decimal('1500.00'), status='PENDING')
        self.assertFalse(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())
        pr.status = 'APPROVED'
        pr.save()
        self.assertTrue(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())

    def test_signal_cancels_on_cancelled(self):
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(name='外协丙', code='SG3')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='SIGP3', planned_date='2026-07-10',
                                          amount=Decimal('800.00'), status='APPROVED')
        pr.status = 'CANCELLED'
        pr.save()
        item = PayableItem.objects.get(source_type='contract_payment', source_id=pr.pk)
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

    def test_approve_action_registers(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(name='外协丁', code='SG4')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='SIGP4', planned_date='2026-07-10',
                                          amount=Decimal('1200.00'), status='PENDING')
        PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).delete()
        user = User.objects.create(username='pradmin', employee_id='PRA1', is_staff=True, is_superuser=True)
        client = APIClient(); client.force_authenticate(user)
        resp = client.post(f'/api/purchase/payment-records/{pr.pk}/approve/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')
        self.assertTrue(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())
```

- [ ] **Step 2: 运行,确认失败**

清理测试库后运行:
`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ContractPaymentSignalTest --noinput -v2`
Expected: FAIL(`PayableItem.DoesNotExist` —— 尚无信号登记)

- [ ] **Step 3: 写实现**(修改 `backend/apps/purchase/signals.py`)

顶部 import 追加 `PaymentRecord`:

```python
from .contract_execution import PaymentRecord
from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
```

文件末尾追加 receiver:

```python
@receiver(post_save, sender=PaymentRecord)
def register_contract_payment_payable(sender, instance, **kwargs):
    """合同付款审批通过 → 登记待付款项台账;取消 → 台账项作废。

    覆盖三条审批到达路径(直接 approve / submit 自动通过 / 工作流引擎完成),
    因它们最终都经 PaymentRecord.save() 落状态(见 core/workflow/services.py
    的 _on_workflow_complete PAYMENT_RECORD 分支)。register_payable/cancel_payable
    惰性 import,避免 app 加载期与 finance 的循环依赖。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status == 'APPROVED':
        register_payable(instance, 'contract_payment')
    elif instance.status == 'CANCELLED':
        cancel_payable(instance, 'contract_payment')
```

- [ ] **Step 4: 运行测试,确认通过**

`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ContractPaymentSignalTest --noinput -v2`
Expected: PASS(4 tests ok)

- [ ] **Step 5: 回归既有台账测试**(确认信号不破坏 `ContractPaymentAdapterTest`/`ContractUnsettleTest` 等)

`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger --noinput`
Expected: PASS(既有 22 + 新 4 = 26 tests ok)

- [ ] **Step 6: Commit**

```bash
git add backend/apps/purchase/signals.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(purchase): 合同付款审批通过经 post_save 信号登记待付款项台账"
```

---

### Task 2:pay() 退役 —— 停用直接标记付款

**Files:**
- Modify: `backend/apps/purchase/contract_execution.py:664-681`(`PaymentRecordViewSet.pay`)
- Test: `backend/apps/finance/tests/test_payable_ledger.py`(追加 `ContractPayRetiredTest`)

**Interfaces:**
- Consumes: `PaymentRecordViewSet` 路由(`/api/purchase/payment-records/{pk}/pay/`)
- Produces: `pay` action 返回 HTTP 409,不修改 `PaymentRecord.status` 与 `execution.paid_amount`。

- [ ] **Step 1: 写失败测试**(追加到 `test_payable_ledger.py` 末尾)

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPayRetiredTest(TestCase):
    def test_pay_endpoint_retired_returns_409_and_no_side_effect(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        sup = Supplier.objects.create(code='PR1', name='外协戊')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no='PCPR1',
                                                   title='c', contract_date='2026-06-01', total_amount=Decimal('3000'))
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))
        pr = PaymentRecord.objects.create(execution=ex, payment_no='PAYR1', planned_date='2026-07-10',
                                          amount=Decimal('3000.00'), status='APPROVED')
        user = User.objects.create(username='payadmin', employee_id='PAY1', is_staff=True, is_superuser=True)
        client = APIClient(); client.force_authenticate(user)
        resp = client.post(f'/api/purchase/payment-records/{pr.pk}/pay/', {}, format='json')
        self.assertEqual(resp.status_code, 409)
        pr.refresh_from_db(); ex.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')      # 未被标 PAID
        self.assertEqual(ex.paid_amount, Decimal('0'))  # execution.paid_amount 未被改
```

- [ ] **Step 2: 运行,确认失败**

`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ContractPayRetiredTest --noinput -v2`
Expected: FAIL(现 `pay()` 返回 200 且把 pr 标 PAID、ex.paid_amount=3000)

- [ ] **Step 3: 写实现**(替换 `contract_execution.py` 的 `pay` action 整段)

把原 `pay`(约 664-681 行)整体替换为:

```python
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """已停用:合同付款统一由银行流水核销完成(付款核销工作台)。

        历史上 pay() 直接把记录标 PAID 并重算 execution.paid_amount,绕过核销台账,
        与统一核销"两套并存"。收口后合同付款 →PAID 只经 settle→write_back 驱动。
        """
        return Response(
            {'error': '合同付款已统一由银行流水核销完成:请在「付款核销工作台」核销对应银行流水。此接口已停用。'},
            status=409,
        )
```

(`Response`、`action`、`status` 均已在文件顶部 import;`date`/`Sum` 若因此不再被其它代码使用无需处理——仅移除 pay 体内引用即可,勿动其它 action。)

- [ ] **Step 4: 运行测试,确认通过**

`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ContractPayRetiredTest --noinput -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/purchase/contract_execution.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(purchase): 退役合同付款 pay() 直接标记,统一走银行流水核销(返回 409)"
```

---

### Task 3:存量回填管理命令 `backfill_contract_payables`

**Files:**
- Create: `backend/apps/finance/management/commands/backfill_contract_payables.py`
- Test: `backend/apps/finance/tests/test_payable_ledger.py`(追加 `ContractBackfillTest`)

**Interfaces:**
- Consumes: `register_payable(obj, 'contract_payment')`、`PaymentRecord`
- Produces: `backfill_contract_payables` 命令 —— 对 `status='APPROVED'` 的 `PaymentRecord` 登记台账;`PAID`/`PENDING`/`CANCELLED` 跳过。

- [ ] **Step 1: 写失败测试**(追加到 `test_payable_ledger.py` 末尾)

```python
@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractBackfillTest(TestCase):
    def _make_pr(self, no, status, code):
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        sup = Supplier.objects.create(code=code, name=f'外协{code}')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no=f'PC{code}',
                                                   title='c', contract_date='2026-06-01', total_amount=Decimal('3000'))
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))
        return PaymentRecord.objects.create(execution=ex, payment_no=no, planned_date='2026-07-10',
                                            amount=Decimal('1000.00'), status=status)

    def test_backfill_registers_only_approved(self):
        from django.core.management import call_command
        approved = self._make_pr('BF1', 'APPROVED', 'BFA')
        paid = self._make_pr('BF2', 'PAID', 'BFP')
        # 清掉信号在 create 时可能登记的项,模拟"存量未登记"
        PayableItem.objects.all().delete()
        call_command('backfill_contract_payables')
        self.assertTrue(PayableItem.objects.filter(source_type='contract_payment', source_id=approved.pk).exists())
        self.assertFalse(PayableItem.objects.filter(source_type='contract_payment', source_id=paid.pk).exists())

    def test_backfill_is_idempotent(self):
        from django.core.management import call_command
        approved = self._make_pr('BF3', 'APPROVED', 'BFI')
        PayableItem.objects.all().delete()
        call_command('backfill_contract_payables')
        call_command('backfill_contract_payables')
        self.assertEqual(
            PayableItem.objects.filter(source_type='contract_payment', source_id=approved.pk).count(), 1)
```

- [ ] **Step 2: 运行,确认失败**

`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ContractBackfillTest --noinput -v2`
Expected: FAIL(`Unknown command: 'backfill_contract_payables'`)

- [ ] **Step 3: 写实现**

```python
# backend/apps/finance/management/commands/backfill_contract_payables.py
"""把存量已审批(未付)的合同付款回填到统一待付款项台账。

收口 pay() 后新审批的合同付款经 post_save 信号自动登记;本命令用于登记
收口前已处于 APPROVED 的存量记录。历史 PAID 记录跳过(已付、无需核销)。
幂等:register_payable 走 update_or_create。
"""

from django.core.management.base import BaseCommand

from apps.finance.payable_adapters import register_payable
from apps.purchase.contract_execution import PaymentRecord


class Command(BaseCommand):
    help = '把已审批未付的合同付款(PaymentRecord status=APPROVED)回填到待付款项台账'

    def handle(self, *args, **options):
        qs = PaymentRecord.objects.filter(status='APPROVED')
        count = 0
        for pr in qs:
            register_payable(pr, 'contract_payment')
            count += 1
        self.stdout.write(self.style.SUCCESS(f'回填 {count} 条合同付款到台账'))
```

- [ ] **Step 4: 运行测试,确认通过**

`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger.ContractBackfillTest --noinput -v2`
Expected: PASS(2 tests)

- [ ] **Step 5: 全量回归 + Commit**

`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test apps.finance.tests.test_payable_ledger apps.finance.tests.test_bank_match --noinput`
Expected: 全部 PASS(台账 29 = 既有 22 + Task1 的 4 + Task2 的 1 + Task3 的 2;银行匹配 4)

```bash
git add backend/apps/finance/management/commands/backfill_contract_payables.py backend/apps/finance/tests/test_payable_ledger.py
git commit -m "feat(finance): backfill_contract_payables 命令(存量已审批合同付款回填台账)"
```

---

## Self-Review 记录

- **Spec 覆盖**:§4.1 登记信号→Task 1;§4.2 pay() 退役→Task 2;§4.3 存量回填→Task 3;§5 单一事实来源(pay 不再写 paid_amount)→Task 2 断言;§6 测试策略六类用例分布于 Task 1(信号三路径+CANCELLED+approve 端到端)、Task 2(pay 停用无副作用)、Task 3(回填仅 APPROVED/幂等)、各 Task 回归步。§7 工作流 save/update →Task 0 已确认为 `.save()`。
- **占位符**:无 TBD/TODO;各步含完整测试与实现代码、精确命令与预期。
- **类型一致**:`register_payable(obj,'contract_payment')`/`cancel_payable` 全程一致;信号 sender=`PaymentRecord`;URL `/api/purchase/payment-records/{pk}/{pay,approve}/` 与路由 basename 一致;命令名 `backfill_contract_payables` 前后一致。
- **范围**:仅合同付款收口;不动 AP 旧路径、不动前端(按 spec 非目标)。
