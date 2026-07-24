# 应付账款(AP)Payment.ap 旧付款路径收口 · 设计

- 日期:2026-07-07
- 状态:第一批(登记 + 只读守卫 + 双记 bug 修复)已实现;**是否退役三条旧付款入口待用户拍板**
- 范围:后端(Django/DRF)。前端改造(若走"退役"方案)是独立 follow-up。
- 关联:
  - [银行流水统一核销·待付款项台账 设计](2026-07-02-payment-reconciliation-ledger-design.md)(一期后端已落地)
  - [合同付款 pay() 收口 · 统一走核销台账 设计](2026-07-07-contract-payment-pay-consolidation-design.md)(同批姊妹任务,已完成退役;本文档多处对照该文档的"已验证可行"的收口手法)

## 1. 背景与问题

一期建成了"统一待付款项台账 `PayableItem` + 银行流水核销(settle/unsettle)",AP(`AccountPayable`)也已有来源适配器 `APPayableSource`(`backend/apps/finance/payable_adapters.py:48-66`),且 `backfill_payables` 管理命令已把存量未结清 AP 一次性回填进台账。

但 AP 的 `amount_paid`/`status` **实际存在两条(严格说是四条)互不相知的写路径**,并存在一个真实的双记 bug:

1. **`Payment.save()` 的 F() 自增分支**(`backend/apps/finance/models.py:443-459`):任何 `Payment(payment_type='AP', ap=<AccountPayable>)` 一旦被创建(`is_new`),都会 `AccountPayable.objects.filter(pk=self.ap_id).update(amount_paid=F('amount_paid') + self.amount)`。**注意这里用的是 `.update()` 而非 `.save()`**——`AccountPayable.save()` 里"按 amount_paid/amount_due 推导 status"的逻辑(`models.py:342-350`)完全不会被触发,调用方必须自己手动重算并保存 status。这是所有下游"手动重算 status"代码存在的原因。
2. **`AccountPayableViewSet.record_payment` action**(`views.py:374-422`)——创建 `Payment(payment_type='AP', ...)`(触发 ①),再手动重算+保存 status。**前端在用**:`APList.vue:530` 的"付款"按钮(`recordPayablePayment()`)。
3. **`BankStatementViewSet.match` → `_apply_statement_payment` 的 AP 分支**(`bank_statement_views.py:676-793`,AP 分支在 771-793)——银行流水"手动匹配"时,命中 AP 就创建 `Payment(payment_type='AP', ...)`(触发 ①),用 `notes` 里的 `[BS#id]` marker 做幂等去重,再手动重算+保存 status。**前端在用**:`APList.vue:639`、`ARList.vue:683`、`BankStatementList.vue` 的"匹配"按钮(`matchBankStatement()`)。**这是银行流水匹配 AP 的"老机制"**,与一期设计的"核销工作台"(`payable-reconcile/settle`)是同一问题两套实现——老机制直接改 `Payment.ap`,新机制走 `PayableItem`/`PayableSettlement`,两者互不感知。
4. **`PaymentRequestViewSet.pay` action**(`views.py:2217-2263`,现已修复)——"付款申请"(`PaymentRequest`,有自己独立的 `WorkflowEnforcementMixin` 审批流,`business_type='PAYMENT'`)批准后执行付款,创建 `Payment(payment_type='AP', ...)`(触发 ①,已完成一次 F() 自增),**随后又对同一笔付款额外手动 `AccountPayable.objects.filter(...).update(amount_paid=F('amount_paid') + payment_req.amount)` 了一次**(旧代码 `views.py:2247-2251`)——**同一笔付款把 `amount_paid` 双记了**。已在本批修复(见第 4.4 节),与是否退役该入口无关,是纯粹的正确性 bug。
5. **通用 `PaymentViewSet`**(`views.py:108-119`)——普通 `ModelViewSet`,`payments/` 未做任何限制。`POST /api/finance/payments/ {payment_type:'AP', ap:<id>, amount:...}` 会直接触发 ①,且**不会**触发 ②③④里"手动重算 status"的动作,`AccountPayable.status` 会彻底停留在旧值——比①②③更隐蔽的一个洞。已在本批堵住(见第 4.3 节)。

此外:
- 新台账没有创建期自动登记钩子——只有一次性的 `backfill_payables` 命令覆盖"当前存量"。`purchase/views.py:987`(PO 收货/确认自动建 AP)、`purchase/outsource_views.py:65`(外协单确认自动建 AP)之后新产生的 AP,在下次有人手动重跑 `backfill_payables` 之前,**在核销工作台里不可见**。
- `AccountPayableSerializer.amount_paid` 早已只读(`serializers.py:184` 原值),但 **`status` 不是只读**——`PATCH /api/finance/payables/{id}/ {status:'PAID'}` 能在不动 amount_paid 的情况下直接把 status 拍成 PAID,状态与实付金额脱节。这与合同付款收口时修的 `PaymentRecordSerializer.status`/`ContractExecutionSerializer.paid_amount` 只读洞是同一类问题。

**关键差异(相对合同付款收口)**:合同付款收口后(`pay()` 退役)时,`PaymentRecordViewSet` 已没有任何"直接标付款"的替代 UI 入口——因为合同付款本来就不是"通过 UI 手动付一笔钱"的场景,是"审批完等着被核销"。**AP 不同**:`record_payment`("付款"按钮)与 `match`("匹配"银行流水按钮)都是**当前 APList.vue 里唯一能完成 AP 付款登记的 UI**,而新台账的核销工作台(`payable-items`/`payable-reconcile/settle/unsettle`)**目前没有任何前端页面**(全仓库 grep 找不到任何调用)。若照搬合同付款的做法直接退役 ②③,AP 模块会从"能付款但记两次账"退化成"完全不能从 UI 付款",直到前端补上核销工作台页面。这是本设计**必须请用户拍板**的核心原因。

## 2. 目标 / 非目标

### 目标(本设计范围内全部完成)
- AP **创建即自动登记**到 `PayableItem` 台账(不再依赖手动重跑 backfill),取消联动作废台账项。
- 关掉 `AccountPayableSerializer.status` 的 PATCH 直改旁路(`amount_paid` 已经是只读,一并回归测试)。
- 关掉通用 `PaymentViewSet` 直接创建 `payment_type='AP'` 付款记录的旁路(防御性收口,已确认零前端调用方)。
- 修复 `PaymentRequestViewSet.pay()` 的 `amount_paid` 双记 bug。
- **不改**是否退役 `record_payment`/`match`(AP 分支)——留待用户决策(见第 5 节)。

### 非目标
- 不动 AR(`AccountReceivable`)一侧的对应路径(`record_payment`(AR)、`match` 的 AR 分支、`Payment.ar` F() 自增)——不在本次任务范围,后续如有需要应作为独立评估。
- 不新建核销工作台前端页面(`payable-items`/`payable-reconcile`)——这是让方案 A(见第 5 节)成立的前置条件,但落地属独立前端任务。
- 不改 `PaymentRequest` 自身的审批流程(`submit`/`approve`/工作流引擎)逻辑,只改它 `pay()` 里落到 AP 的那一段。

## 3. 现状梳理:AP 所有"改 amount_paid / status"的写入点

| # | 位置 | 触发方式 | 前端是否在用 | 说明 |
|---|------|---------|------------|------|
| ① | `Payment.save()`(`models.py:443-459`) | 任何 `Payment(payment_type='AP', ap=X)` 被创建 | 间接(被②③④调用) | F() 自增 amount_paid;**不触发** `AccountPayable.save()` 的 status 推导(用的是 `.update()`) |
| ② | `AccountPayableViewSet.record_payment`(`views.py:374-422`) | `POST /api/finance/payables/{id}/record_payment/` | **是**:`APList.vue:530` "付款"按钮 | 触发① + 手动重算 status |
| ③ | `BankStatementViewSet.match` AP 分支(`bank_statement_views.py:676-793`) | `POST /api/finance/bank-statements/{id}/match/` | **是**:`APList.vue:639`、`ARList.vue:683`、`BankStatementList.vue` "匹配"按钮 | 触发① + 手动重算 status;`notes` marker 防重复匹配重复记账 |
| ④ | `PaymentRequestViewSet.pay`(`views.py:2217-2263`) | `POST /api/finance/payment-requests/{id}/pay/` | **否**:全仓库(`frontend/`、`miniprogram/`)找不到任何 `payment-requests` 调用 | 触发① + **曾经又手动 F() 一次(双记 bug,本批已修)** |
| ⑤ | 通用 `PaymentViewSet`(`views.py:108-119`) | `POST /api/finance/payments/ {payment_type:'AP', ap:X}` | 否(全仓库无调用) | 触发①,且不触发任何 status 重算——AP.status 会停留旧值。**本批已在序列化器层堵住** |
| ⑥ | `PayableReconcileViewSet.settle`(`payable_views.py:45-68`,一期已实现) | `POST /api/finance/payable-reconcile/settle/` | 否(前端暂无页面,后端 API 已就绪) | 走 `PayableItem`→`APPayableSource.write_back`,**是新台账的唯一"正确"入口**,不经①的 F() 分支(用 `payment_type='PAYABLE'`) |
| ⑦ | `AccountPayableSerializer` 的通用 PATCH(`serializers.py`) | `PATCH /api/finance/payables/{id}/ {status:...}` | 否(`updatePayable` 在 `frontend/src/api/finance.ts:42` 定义但全仓库无调用) | `amount_paid` 早已只读;**`status` 本批前不是只读** |

## 4. 本批已实现(无争议部分)

### 4.1 AP 创建/变更即自动登记台账(`post_save` 信号)

新增 `backend/apps/finance/signals.py`,在 `AccountPayable` 的 `post_save` 上兜底:

```python
@receiver(post_save, sender=AccountPayable)
def register_ap_payable(sender, instance, **kwargs):
    if instance.status in ('PENDING', 'PARTIAL', 'OVERDUE'):
        register_payable(instance, 'ap')
    elif instance.status == 'CANCELLED':
        cancel_payable(instance, 'ap')
```

`FinanceConfig.ready()` 里 `import signals`(与 `apps.purchase.apps.PurchaseConfig.ready()` 里 `import signals` 完全同构)。

要点(与合同付款收口时的判断一致):
- 过滤口径与 `backfill_payables` 命令一致(`PENDING`/`PARTIAL`/`OVERDUE` 才登记;`PAID` 不登记——已结清无需核销,避免污染候选)。
- `register_payable` 走 `update_or_create`,`defaults` 不含 `amount_paid`/`status`(`payable_adapters.py:29-34` 的不变量),因此本信号可以安全地在 AP 的每次 `save()`——包括 `APPayableSource.write_back` 触发的重入 `save()`——上重复触发,只刷新供应商/金额/日期等静态字段,不会覆盖已由核销/反核销维护的核销进度。
- `cancel_payable` 内部已守卫:仅 `amount_paid==0` 的台账项才会被置 `CANCELLED`,已核销过的不会被误伤。
- `backfill_payables` 命令继续保留,作为"信号上线前已存在的存量 AP"的一次性补登记手段;信号只覆盖信号上线后的新建/变更。

### 4.2 关闭 `AccountPayableSerializer.status` 的 PATCH 旁路

`status` 加入 `read_only_fields`(`amount_paid` 已经在里面)。状态只应由 `AccountPayable.save()` 的派生逻辑(基于 amount_paid/amount_due)或 `write_back`/`check_overdue_payables` 定时任务(用 `.update()`,不经序列化器)产生,不应允许通用 PATCH 直改。已确认 `updatePayable`(对应的前端 PUT 封装)在整个前端代码库里没有任何调用点,回归风险为零。

### 4.3 关闭通用 `PaymentViewSet` 直接创建 `payment_type='AP'` 的旁路

`PaymentSerializer` 加 `validate()`:

```python
def validate(self, attrs):
    payment_type = attrs.get('payment_type') or (self.instance.payment_type if self.instance else None)
    if payment_type == 'AP':
        raise serializers.ValidationError({'payment_type': '应付账款付款已收口到待付款项核销台账,请通过...'})
    return attrs
```

已确认①settle()(台账内部核销)②③④(record_payment/match/pay)都是通过 `Payment.objects.create()` **直连 ORM**、不经 `PaymentSerializer.is_valid()`,因此这条校验**不影响**②③④现有行为(无论后续是否退役它们),纯粹是把"完全没有防护"的第⑤个洞堵上。

### 4.4 修复 `PaymentRequestViewSet.pay()` 的双记 bug

删掉 `views.py` 里紧跟在 `Payment.objects.create(payment_type='AP', ...)` 后面的第二次 `AccountPayable.objects.filter(...).update(amount_paid=F(...) + ...)`,只保留"刷新 + 重算 status + save"。这是纯正确性修复,与是否退役该入口的决策无关——不管将来退不退役,不应该让它继续把同一笔付款计两次。

### 4.5 测试(`backend/apps/finance/tests/test_payable_ledger.py` 末尾追加)

- `APPayableSignalTest`:创建即登记;已结清(PAID)不登记;取消联动台账作废;重入 save 幂等且不覆盖已有核销进度。
- `APStatusPatchBypassTest`:PATCH 不能改 status / amount_paid。
- `PaymentApDirectCreateBlockedTest`:通用付款接口拒绝 `payment_type='AP'`,且不误伤 `payment_type='PAYABLE'` 的正常创建。
- `PaymentRequestPayNoDoubleCountTest`:回归验证双记 bug 已修(400 金额只增一次)。

## 5. 待用户拍板:是否退役 `record_payment` / `match`(AP 分支)/ `PaymentRequest.pay`

这是本次设计里**唯一有实质分歧、影响面大**的问题,原因见第 1 节末尾:**新台账的核销工作台目前没有任何前端页面**,而 `record_payment`("付款"按钮)与 `match`("匹配"按钮)是当前 APList.vue 里唯一能完成 AP 付款登记的 UI。列三个选项:

### 方案 A——立即全量收口(照搬合同付款的做法)
`record_payment` 与 `match` 的 AP 分支都改成受控 409(参照 `contract_execution.py:664-681` 的写法与文案),AP 付款自此只能经 `payable-reconcile/settle` 完成。
- 优点:与合同付款完全对称,彻底消灭双轨,`PayableItem` 成为唯一事实来源,立等可用(后端已全部就绪)。
- 缺点:**在核销工作台前端页面上线之前,AP 模块从 UI 上完全不能付款/匹配银行流水**——需要财务人员改用 Postman/admin 或等前端 fast-follow。`match` 的 AP 分支退役后,`BankStatementList.vue`/`ARList.vue` 里同一个"匹配"按钮对 AR 仍然可用、对 AP 会报错,用户体验不一致(除非同时也决定不退役 AR,这个本来就不在本次范围)。

### 方案 B——先不退役,把旧入口内部改造成"经台账落账"(桥接,不砍 UI)
`record_payment`/`match` 的 AP 分支保留、UI 不变,但内部不再直接 `Payment.objects.create(payment_type='AP', ...)`,而是改走 `PayableItem`/`PayableSettlement`(即调用一个新的"手动核销,不依赖银行流水"的服务函数)。
- 优点:UI 零改动、零功能损失,但底层数据模型统一到台账,`amount_paid`/`status` 由 `write_back` 单点计算,双轨问题从根上消失。
- 缺点:需要新设计能力——现有 `payable_service.settle()` 强绑定一条真实 `BankStatement`(`PayableSettlement.bank_statement` 是必填 `PROTECT` 外键),而 `record_payment` 是"财务手动记一笔付款"(不一定对应已导入的银行流水)。要支持它,要么①造一条"虚拟/手工"`BankStatement` 记录(会污染银行对账报表对"真实流水"的语义),要么②把 `bank_statement` 字段改成可空、新增一个不依赖流水的核销路径。这是需要重新讨论台账模型的设计改动,工作量明显大于方案 A/C。

### 方案 C——本次只做无争议部分,退役与否留到下一批(推荐的默认落点)
保留 `record_payment`/`match`(AP 分支)现状不动,先让本批"信号登记 + PATCH 收口 + 双记修复 + 通用接口收口"上线(已完成),AP 的 `amount_paid` 双轨问题从"两套都在写、互相打架、还有真 bug"降级为"两套都在写,但至少各自正确、且台账那一套已经能通过 `backfill_payables`/信号观察到全部存量+增量的 AP",退役决策留给用户结合前端排期一起定。
- 优点:零 UI 回归风险,已消灭本次发现的唯一双记正确性 bug 与两个"完全无防护"的洞。
- 缺点:双轨本身仍然存在——`record_payment`/`match` 产生的付款,台账那条线（`PayableItem.amount_paid`）不会跟着更新（`APPayableSource.write_back` 只在 `settle`/`unsettle` 时被调用,`record_payment`/`match` 不会触发它),会导致核销工作台候选列表里,一笔已经被"付款"按钮付掉的 AP，看起来仍然"待付/部分待付"、可以被再核销一次——**这是本设计遗留的已知不一致**,只有等方案 A 或 B 落地才能消除。

**我倾向的选择**:方案 C 是这次的稳妥落点(已实现),但方案 A 是"正确终态"、工作量最小(后端已 100%就绪,只是要接受前端暂时的功能空档)。方案 B 理论最优但需要额外设计核销台账"无银行流水手工核销"的语义,建议作为独立评估、不卡在本次任务里。

**请用户明确**:是否现在就执行方案 A(退役 `record_payment` 与 `match` 的 AP 分支,返回 409,财务通过 API/待建的核销工作台页面操作),或维持方案 C 现状、把退役工作留到核销工作台前端页面排期后再做?

## 6. 单一事实来源(本批收口后的不变式,退役与否不影响)

- `AccountPayable.status`:只能由 `AccountPayable.save()`(基于 amount_paid/amount_due 派生)或 `write_back`(核销驱动)或 `check_overdue_payables` 定时任务(仅 `PENDING`/`PARTIAL`→`OVERDUE`)产生,不再能被通用 PATCH 直改。
- `AccountPayable.amount_paid`:只能经①的 F() 自增(由②③④触发)或 `write_back`(绝对赋值 `item.amount_paid`)写入,不再能被通用 PATCH 或通用 `PaymentViewSet` 创建触发。
- `PayableItem`(`source_type='ap'`):AP 一旦存在(状态非 PAID/CANCELLED)即登记,不必依赖人工重跑 `backfill_payables`。
