# 合同付款 pay() 收口 · 统一走核销台账 设计

- 日期:2026-07-07
- 状态:设计已确认,待评审
- 范围:后端(Django/DRF)。前端"付款"按钮改造属独立 follow-up,不在本次。
- 关联:[银行流水统一核销·待付款项台账 设计](2026-07-02-payment-reconciliation-ledger-design.md)(一期后端已落地,分支 `feat/payment-reconciliation-ledger`)

## 1. 背景与问题

一期已建成"统一待付款项台账 `PayableItem` + 银行流水核销(settle/unsettle)"框架,合同付款 `PaymentRecord` 也已有来源适配器 `ContractPaymentSource`。但采购合同执行里遗留的 `PaymentRecordViewSet.pay()`(`backend/apps/purchase/contract_execution.py:664-681`)仍是**独立写路径**:审批通过后点"付款"直接把 `PaymentRecord.status` 置 `PAID` 并重算 `execution.paid_amount`,**完全绕过银行流水核销台账**。

这与一期设计文档第 10/13 节明确的目标冲突:「付款侧收敛到台账核销、**禁止绕过台账直接改付款**、避免两套并存」。当前虽因 `execution.paid_amount` 两边都用「按 PAID 记录重算」+ `write_back` 幂等守卫(`obj.status != 'PAID'`)而**不会双记金额**,但两套写路径互不感知:`pay()` 标 `PAID` 时台账 `PayableItem` 仍停在 `PENDING`,该付款会错误地继续出现在核销工作台候选里,台账「已付/未付」与源单据 status 会漂移。

目标:**退役 `pay()` 的直接标记付款能力**,让合同付款只能由银行流水核销完成,台账成为唯一事实来源。

## 2. 目标 / 非目标

### 目标
- 合同付款 `PaymentRecord` **审批通过即自动登记**到 `PayableItem` 台账(候选可见)。
- **退役 `pay()`**:不再直接改 `status`/`execution.paid_amount`;合同付款 →`PAID` 只能由 `settle → ContractPaymentSource.write_back` 驱动。
- `execution.paid_amount` **单一写入者**:只由 `write_back` 按 `PAID` 付款记录重算。
- 存量 `APPROVED`(未付)合同付款一次性回填进台账。

### 非目标
- **不改** AP 的 `Payment.ap` 旧付款路径(单独评估,本次不动)。
- **不改** 前端:"付款"按钮改"去核销"属前端 follow-up(与核销工作台页面同批)。
- **不改** 现有审批流(`submit`/`approve`/工作流引擎)本身的逻辑。
- **不回填** 历史 `PAID` 合同付款(已付、无需核销;为其造台账项反而会污染候选)。

## 3. 现状(关键事实)

`PaymentRecordViewSet`(`WorkflowEnforcementMixin` + `PermissionMixin` + …)三段式:

- `submit`:`start_workflow_or_auto_approve`;小额/无工作流时**自动通过**(直接置 `APPROVED`);否则**启动工作流**(status 仍 `PENDING`,最终由工作流引擎置 `APPROVED`,**不经 ViewSet action**)。
- `approve`:仅在无活跃工作流时允许,直接置 `APPROVED`。
- `pay`:要求 `status=='APPROVED'`,置 `PAID` + `actual_date`,重算 `execution.paid_amount`。← **本次退役对象**

合同付款的「审批通过」因此有**三条到达路径**:直接 `approve()`、`submit` 自动通过、**工作流引擎驱动**。只钩某个 action 会漏掉工作流那条(设计文档 13 节点名的「登记钩子遗漏」风险)。

`ContractPaymentSource.write_back`(已实现,幂等):`item.status==PAID && obj.status!='PAID'` → 置 `PAID`+`actual_date`;反向 → 退回 `APPROVED`+清 `actual_date`;`execution.paid_amount` 恒按该执行下全部 `status='PAID'` 的 `PaymentRecord` 求和重算。

## 4. 方案(三个机制)

### 4.1 登记 —— `post_save` 信号(catch-all)

用 `PaymentRecord` 的 `post_save` 信号按状态兜底,一举覆盖三条审批路径:

- `instance.status == 'APPROVED'` → `register_payable(instance, 'contract_payment')`(幂等 `update_or_create`)。
- `instance.status == 'CANCELLED'` → `cancel_payable(instance, 'contract_payment')`(台账项若 `amount_paid==0` 置 `CANCELLED`)。
- 其它状态(`PENDING`/`PAID`)不动作。

要点:
- 信号处理器放在 purchase 应用(`backend/apps/purchase/signals.py`),在 `PurchaseConfig.ready()` 里 `import`;`register_payable`/`cancel_payable` 在处理器内**惰性 import** finance,避免 app 加载期循环依赖。
- `register_payable` 的 `to_payable` 在 `APPROVED` 时读 `obj.execution.contract.supplier`/`obj.amount`/`obj.planned_date`,均已就绪。
- 与 `write_back` 的交互安全:`write_back` 把 `PaymentRecord` 存为 `PAID` 时信号不登记(状态非 `APPROVED`);反核销把它存回 `APPROVED` 时信号会 `update_or_create` 同一台账项(defaults 不含 `amount_paid`/`status`,不覆盖已由 `unsettle` 回退的已付额)——幂等、无污染。
- 不设置 `update_fields` 无关性问题:信号无论 `update_fields` 都会触发,靠状态判断收敛。

### 4.2 pay() 退役

`pay()` 改为**受控停用**,不再触碰付款状态与金额:

```python
@action(detail=True, methods=['post'])
def pay(self, request, pk=None):
    return Response(
        {'error': '合同付款已统一由银行流水核销完成:请在「付款核销工作台」核销对应银行流水。此接口已停用。'},
        status=409,
    )
```

- 保留路由(返回受控 `409`,而非删除致前端 `404`/`500`),前端按钮改造前仍得到清晰提示。
- 合同付款 →`PAID` 自此只有一条路:`settle → write_back`。

### 4.3 存量回填

新增管理命令 `backfill_contract_payables`:把现有 `status='APPROVED'` 的 `PaymentRecord`(未付、开放)登记进台账,使存量可在工作台核销。幂等(`register_payable` upsert)。历史 `PAID` 记录跳过。

```
docker compose run --rm ... app python manage.py backfill_contract_payables
```

## 5. 单一事实来源(收口后不变式)

- `PaymentRecord.status` 的 `PAID`:仅经 `settle → write_back` 产生;`unsettle → write_back` 可退回 `APPROVED`。
- `execution.paid_amount`:仅由 `write_back` 重算写入(pay() 不再写)。
- `PayableItem`:合同付款审批通过即存在,核销即回填——与源单据 status 不再漂移。

## 6. 测试策略(TDD)

均加 `@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)`,容器内运行。

1. **信号登记 · 直接 approve**:创建 `PENDING` 记录 → 调 `approve` action → 断言生成 `PayableItem`(source_type='contract_payment', amount_due 正确)。
2. **信号登记 · submit 自动通过**:小额/无工作流 → `submit` 自动置 `APPROVED` → 断言台账项生成。
3. **信号登记 · 直接置状态兜底**:`PaymentRecord.objects.create(status='APPROVED')` 保存即触发信号 → 台账项存在(覆盖"工作流引擎直接改状态"这类不经 action 的路径)。
4. **CANCELLED 联动**:已登记且 `amount_paid==0` 的记录置 `CANCELLED` 保存 → 台账项 `status=CANCELLED`。
5. **pay() 停用**:`APPROVED` 记录调 `pay` → `409`,且 `status` 仍 `APPROVED`、`execution.paid_amount` 不变。
6. **回填**:存量 `APPROVED` 记录 → `call_command('backfill_contract_payables')` → 台账项生成;`PAID` 历史记录不生成。
7. **回归**:既有 `test_payable_ledger`(含 `ContractPaymentAdapterTest`/`ContractUnsettleTest`)与 `test_bank_match` 全绿——确认信号不破坏它们(手动 `register_payable` 与信号 `update_or_create` 幂等一致)。

## 7. 风险与权衡

- **信号在测试/批量场景多触发**:靠状态判断 + `update_or_create` 幂等收敛;`register_payable` defaults 不含 `amount_paid`/`status`,不会覆盖核销进度。
- **循环依赖**:purchase 信号处理器惰性 import finance;信号注册在 `ready()`,不在模块顶层。
- **既有 PAID 历史无台账**:有意为之(已付无需核销);若日后需完整可追溯,可另出"为历史 PAID 造带虚拟核销记录的台账项"迁移,不在本次。
- **前端暂时按钮失效**:`pay()` 返回 409 是过渡态;前端 follow-up 把按钮改为跳转核销工作台后闭合。
- **驳回态更细联动**:信号已含 `CANCELLED`→`cancel_payable`;工作流"驳回"若落到其它状态值,后续按实际状态补分支。
- **【实现期必验】工作流置 APPROVED 的写法**:`post_save` 信号只在 Django `Model.save()` 上触发,若工作流引擎用 `QuerySet.update()` 批量改 `status` 会**绕过信号**。实现第一步先定位工作流审批完成的落状态代码,确认走 `.save()`。若走 `.update()`,则在 `submit` 自动通过分支与 `approve` action 里**显式补调** `register_payable`(信号仍保留作 `create`/直接改状态的兜底),并强调 `backfill_contract_payables` 作为存量与遗漏的最终兜底。此校验结果记入实现计划 Task 0。
