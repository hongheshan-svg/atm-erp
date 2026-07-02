# 银行流水统一核销 · 待付款项台账 设计

- 日期:2026-07-02
- 状态:设计已确认,待评审
- 范围:后端(Django/DRF)+ 前端(Vue3)新增单独核销页面

## 1. 背景与问题

当前银行流水(`BankStatement`)的付款核销只能挂到 **应付账款 `AccountPayable`(AP)** 和 **采购付款计划 `PurchasePaymentSchedule`** 上。系统里其它"要付钱出去"的费用单据(费用报销、采购合同付款、委外、缴税、公共费用、付款申请等)**各走各的、字段各异**,银行付款流水无法与它们对应,导致:

- 大量付款流水在"银行流水(收入/支出)"里无法核销,状态与实际脱节;
- 各费用单据的"已付/未付"靠人工维护,与银行实际付款对不上;
- 无法统一对账:一笔银行付款到底付的是哪张单、哪个部门/项目的费用,查不清。

目标是让**所有费用请款**都能被银行流水覆盖核销,且核销即完成记账联动。

## 2. 目标 / 非目标

### 目标
- 建立一个**统一的待付款项台账**,把各模块异构费用单据(审批通过后)统一登记进来。
- 提供一个**单独的核销工作台页面**:未核销银行流水 ↔ 待付台账,自动给候选、人工一键确认核销。
- 核销为**完整记账联动**:生成 `Payment`、回填台账已付金额+状态、回写源单据的已付/状态。
- 支持**部分核销、合并付款(一笔流水核销多单)、分期(一单多次)** 与**反核销**。
- **周全覆盖**所有对外付款费用单据(分期上线,最终全覆盖)。

### 非目标
- 不新建各模块的请款单据——**用各模块现有单据分头录入审批**(已与用户确认)。
- 不做工资/薪酬付款(系统当前无薪酬付款模块)。
- 本期不改造收款侧(应收 `AccountReceivable`)核销,沿用现状,后续可并入台账收款侧。
- 不改各费用单据现有的录入与审批流程,只在"审批通过"这一时点挂登记钩子。

## 3. 术语

- **待付款项(PayableItem)**:台账中的一条,表示"某源单据产生的一笔应付款,待/已被银行流水核销"。
- **来源单据(source)**:产生应付的业务单据,如费用报销 `Expense`、应付账款 `AccountPayable`。
- **核销(settle)**:把一笔/多笔银行流水与一条/多条待付款项对应,并记账、回写。
- **来源适配器(adapter)**:封装某种源单据差异的轻量对象,提供统一取数与回写接口。

## 4. 覆盖的费用单据(全景)

| 单据 | 用途 | 金额字段 | 已付/状态现状 | 分期 |
|---|---|---|---|---|
| `AccountPayable` | 采购/供应商应付 | amount_due | amount_paid / status ✅ | 一期 |
| `Expense` | 差旅/餐饮/办公/培训报销 | amount | 仅 PAID(缺已付额) | 一期 |
| 采购合同付款 `PaymentRecord` | 合同分期付款 | amount | PAID + actual_date | 一期 |
| `OutsourceOrder` | 外协加工费 | total_with_tax | 仅 status | 二期 |
| `TaxDeclaration` | 缴税 | payable_amount | paid_amount + PAID | 二期 |
| `SharedExpense` | 行政/公共费用 | amount | 仅 status | 二期 |
| `PaymentRequest` | 财务付款申请(降级为其中一类) | amount | PAID + paid_at + payment | 二期 |
| `AssetMaintenance` / `VehicleMaintenance` | 资产/车辆维护费 | cost | 仅 status | 三期 |

注:`PurchasePaymentSchedule` 已被现有逻辑覆盖,纳入台账后统一;`Invoice`/`TaxInvoice` 是开票/票据非付款单据,不纳入。

## 5. 整体架构(三层)

```
① 登记层:各费用单据审批通过 → register_payable(源单据) → 生成/更新 PayableItem
② 核销层:银行流水 ↔ PayableItem 核销 → 生成 Payment、回填台账、回写源单据
③ 展示层:核销工作台(未核销流水 ↔ 待付台账,自动候选 + 一键确认)
```

各费用单据"各走各的录入"不变;审批通过后由系统统一登记到台账,出纳只在一个工作台面对"银行流水 + 待付台账"。

## 6. 数据模型

### 6.1 新增 `PayableItem`(待付款项台账)
- `source_type`(CharField,来源单据类型标识,如 `expense`/`ap`/`contract_payment`)
- `source_id`(源单据主键)
- `source_no`(冗余来源单号,便于展示/搜索)
- `category`(费用大类:采购/报销/委外/税费/行政/合同…)
- `payee_name`(收款方名,冗余)、`supplier`(可空 FK → masterdata.Supplier)
- `amount_due`(应付)、`amount_paid`(已付,默认 0)、`currency`(可空 FK)
- `status`(PENDING 待付 / PARTIAL 部分 / PAID 已付 / CANCELLED 已取消)
- `due_date`(应付日期,可空)、`project`(可空 FK)
- 计算属性 `remaining = amount_due - amount_paid`
- 约束:`unique(source_type, source_id)` 防重复登记;索引 `(status, supplier, due_date)`

### 6.2 扩展 `Payment`(付款记录)
- 新增 `payable_item`(可空 FK → PayableItem);`PAYMENT_TYPE_CHOICES` 增加 `PAYABLE`(通用应付)。
- `save()` 沿用现有 AP/AR 回填模式:当 `payable_item_id` 存在时 `PayableItem.amount_paid += amount`。

### 6.3 新增 `PayableSettlement`(核销记录)
- `bank_statement`(FK)、`payable_item`(FK)、`amount`(本次核销额)、`payment`(FK)、`created_by`
- 支持一笔流水核销多项(多条记录同 bank_statement)、一项多次核销(多条记录同 payable_item)。
- 反核销 = 删除该核销记录并回退关联 Payment / 台账 / 源单据。

### 6.4 `BankStatement`
- 不新增每类单据的外键;核销关系统一经 `PayableSettlement` 反查。
- 新增/复用 `status` 值:`PARTIAL`(部分核销)以支持一笔流水分次核销多单。

## 7. 登记层(来源适配器)

定义一个适配器接口(每种源单据实现一个),注册到一个 registry(以 `source_type` 为键):

```
class PayableSource:
    source_type: str
    def to_payable(self, obj) -> dict:   # 取:payee_name/supplier/amount_due/due_date/category/source_no/project
    def write_back(self, obj, paid_delta, is_fully_paid) -> None  # 回写源单据 已付/状态
```

- 触发:各单据在**审批通过/确认应付**时调用 `register_payable(obj)`;实现方式优先在既有审批服务/状态流转处调用,必要时用 `post_save` 信号兜底(需判状态)。
- 幂等:按 `unique(source_type, source_id)` 更新而非重复插入;金额/收款方变化时同步更新台账(未核销部分)。
- 取消/驳回:源单据取消 → 台账项若 `amount_paid=0` 置 `CANCELLED`,否则保留并告警。

## 8. 核销流程(工作台核心)

1. **候选匹配**:对未核销/部分核销的付款流水(转出),按「供应商/收款方名规范化匹配 + 金额(等于剩余或全额) + 日期临近」对台账项打分,返回候选列表(复用已修复的全半角规范化匹配)。
2. **人工确认**:出纳选中流水 → 候选置顶 → 勾选一或多项 → 一键核销;也可手动搜索台账项。
3. **部分/合并**:每次核销写一条 `PayableSettlement`(本次金额),支持一笔流水核销多项、一项多次;金额校验:本次核销 ≤ 流水剩余可核销额,且 ≤ 台账项剩余。
4. **记账**:生成 `Payment`(payment_type=PAYABLE,amount=本次核销额,payable_item=该项)→ 触发台账 `amount_paid` 回填 → 重算台账 `status`。
5. **回写源单据**:经适配器 `write_back` 回写源单据(如 `Expense.status=PAID`、`AccountPayable.amount_paid+=`、`TaxDeclaration.paid_amount+=`、合同 `PaymentRecord.status=PAID`)。
6. **反核销**:删除 `PayableSettlement` → 删除对应 `Payment` → 台账 `amount_paid` 回退 → 适配器回退源单据(幂等,用核销记录做标记)。

## 9. 核销工作台(单独页面,前端)

- 路由:`/erp/finance/payment-reconciliation`(菜单:财务 → 付款核销工作台),权限限出纳/财务角色。
- 布局:左「未核销银行流水」列表(转出),右「待付款项台账」列表(可筛选:模块/供应商/金额区间/日期/状态)。
- 交互:选中一笔流水 → 右侧按匹配分数高亮并置顶候选 → 勾选一或多项 → 确认核销弹窗(显示本次核销额、各项剩余、生成的付款单号)。
- 可视:台账项状态标签(待付/部分/已付);流水标签(未核销/部分/已核销);已核销可展开看 `PayableSettlement` 明细并支持反核销。
- 前端遵循项目规范:API 走 `src/api/finance.ts`、`src/utils/request.ts`;权限三件套一致;TypeScript。

## 10. 与现有系统的衔接与迁移

- 现有"银行流水直连 AP + `auto_match_*` + 采购付款计划"的**付款侧**逻辑收敛到台账核销,避免两套并存;`AccountPayable` 作为台账来源之一登记,核销经台账回写 AP。
- 银行流水导入与供应商自动匹配(`auto_match_supplier`,含已修复的全半角规范化)**保留**,用于候选打分。
- 存量数据:一期上线时,对已有未结清的 AP 生成台账项(数据迁移脚本);其它单据在其状态本就"待付"时补登记。
- 收款侧(AR)本期不动。

## 11. 分期计划

- **一期(本 spec 落地目标)**:`PayableItem` + `PayableSettlement` + `Payment` 扩展 + 核销服务 + 工作台页面 + 接入 **AP、费用报销 `Expense`、采购合同付款 `PaymentRecord`**;AP 存量台账迁移。
- **二期**:委外 `OutsourceOrder`、缴税 `TaxDeclaration`、公共费用 `SharedExpense`、付款申请 `PaymentRequest`。
- **三期**:资产/车辆维护等小额。
- 每期只新增对应适配器 + 迁移,核销框架不变。

## 12. 测试策略(TDD)

- **模型/服务单测**:
  - `register_payable` 幂等(重复登记只更新)、取消置 CANCELLED。
  - 核销:全额/部分/合并/分期的金额校验与状态流转(PENDING→PARTIAL→PAID)。
  - 记账:生成 Payment 且台账 `amount_paid` 正确回填;回写源单据字段正确。
  - 反核销:金额与状态幂等回退。
  - 候选匹配:供应商全半角规范化命中、金额/日期打分排序。
- **接口测**:工作台候选、核销、反核销 API 的权限与边界(超额核销拒绝)。
- ES 信号:测试用 `@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)` 隔离(沿用既有约定)。
- 测试在容器内运行(本机无 venv):`docker compose run --rm --no-deps -e RUN_BOOTSTRAP=0 -v "$PWD/backend:/app" app python manage.py test ... --noinput`。

## 13. 风险与权衡

- **双台账风险**:AP 已有自己的 `amount_paid`,台账也有——通过"台账为核销唯一入口、核销时回写 AP"保证单一事实来源,禁止绕过台账直接改 AP 付款。
- **登记钩子遗漏**:某些单据审批路径分散,可能漏调 `register_payable`;用 `post_save` 信号按状态兜底 + 一次性回填脚本。
- **异构回写**:各单据字段不一,集中在适配器 `write_back`,新增单据只写一个适配器,降低扩散。
- **GenericFK 取舍**:用 `source_type(char)+source_id` 而非 Django GenericForeignKey,避免 contenttype 复杂度与跨表查询;台账为独立单表,列表/分页/统计性能好。
- **并发**:核销走事务 + `select_for_update` 锁台账项,防超额/重复核销(沿用现有 `_apply_statement_payment` 的加锁思路)。
