# B 专项:对照运行中的旧 Django 做业务逻辑对账

> 方法:用本地镜像把旧 Django 跑起来当**裁判**,对深度业务逻辑逐条核对 Go 移植"算得对不对"。
> 这类正确性(财务过账/库存账实/选流)无法靠读代码确认,必须有可运行的权威实现 diff。

## 裁判环境(可复用)

```bash
# 起旧 Django(本地镜像,跳过 ES/celery/nginx;backend 自动迁移+bootstrap)
IMAGE_TAG=local docker compose up -d postgres redis backend
# 等健康
until [ "$(docker inspect -f '{{.State.Health.Status}}' erp-backend)" = healthy ]; do :; done
# 跑裁判脚本(stdin 喂 Django shell)
docker exec -i erp-backend python manage.py shell < oracle.py
```
注意:创建被 ES 索引的模型(Item/Customer/Supplier)会触发 django-elasticsearch-dsl 实时索引,
ES 未起会报错——用 `Model.objects.bulk_create([...])` 绕过 post_save 信号。

## ✅ inventory — 移动加权平均成本(已验证一致)

权威:`apps.inventory.cost_accounting.CostCalculationService`(append-only `inventory_item_cost_record` 账本)。
- 入库:`new_unit = (prev_cost + qty×unit) / (prev_qty+qty)`,量化 4dp HALF_UP。
- 出库:`out_total = (qty × balance_unit_cost)` **先量化 2dp 再从结存金额扣减**(关键细节)。

裁判算例(入 10@100、10@200、2@13;出 5):
`bal_qty=17.0000  bal_cost=2338.27  bal_unit=137.5453`

Go 实现:`server/internal/inventory/cost/`(shopspring/decimal,禁 float64),
单测 `TestWeightedAverageMatchesDjangoOracle` 断言同一序列得到**完全相同数字**,PASS。

**库存移动 confirm → Stock 端到端**(独立于上面的成本账本,对齐 `StockMove._update_stock`):
`CompleteMove`/`CreateMove(COMPLETED)` → `applyMoveToStock`(IN/OUT/TRANSFER/ADJUSTMENT)→
`stockIn`(加权平均,行锁)/`stockOut`(库存不足报错)。裁判算例(IN 10@100、5@130、3@121.50、OUT 4):
Stock `qty=14.00 avg=111.92`;Go 集成测试 `TestStockMoveConfirmMatchesDjango` 断言一致,PASS。
并把 `stockIn` 的加权平均除法由 float64 改 decimal,消除分位四舍五入边界与 Django 的潜在偏差。

## ✅ workflow — 选流算法(已验证一致)

权威:`WorkflowService.get_workflow_for_business`:
`filter(business_type, is_active).order_by('-amount_threshold')`;给定金额时返回**首个**
`threshold is None or amount >= threshold` 者,否则首个。

关键细节:PG 对 `ORDER BY amount_threshold DESC` 为 **NULLS FIRST**,故**含 NULL 阈值的流程对任何金额都胜出**。
裁判:含 NULL → 全选 nothr;无 NULL → 5000/20000/100000 各选 low/mid/high。

Go 实现:`server/internal/workflow/repo.go: SelectForBusiness`——同 `Order("amount_threshold DESC")`(同 PG → 同 NULLS FIRST),算法逐行一致。
集成测试 `select_integration_test.go`(真库,因 NULLS 排序是 DB 行为)断言两场景与裁判一致,PASS。

## ✅ workflow — 跳步 / 会签(已对账并补齐)

**跳步**(`skip_amount_threshold`):Django `if step.skip_amount_threshold and instance.amount: if amount < threshold: continue`。
对账发现 Go 与之有真实差异——Go 只判 `!= nil`,而 Django 用 Python 真值(**0 视为假**),故 `amount=0` + 正阈值时
Go 会误跳、Django 不跳。**✅ 已修**:Go 改为"阈值与金额皆非 nil 且非 0 才比较"。裁判:`amount 0→step1`、
`3000→step2`、`8000→step1`、`None→step1`;Go 集成测试断言一致,PASS。

**会签**(`COUNTERSIGN`):Django **声明未实现**(每步单 task、单签即推进)——Go 新增能力。已实现:
`action_type=COUNTERSIGN` 时一步为全部审批人各生成一条 task,**全部 APPROVED 才推进**(任一拒绝整单驳回)。
集成测试(无 Django 裁判,验意图语义):2 审批人,签 1 实例仍 PENDING、签 2 实例 APPROVED,PASS。

## ✅ finance — 回款核销级联(已移植并验证)

权威:`apps.finance.collection_models.CollectionRecord.save()` 三级汇总:
1. 节点 `collected_amount = SUM(records.amount)`;状态:`>= planned → COLLECTED`(补 actual_date),`>0 → PARTIAL`。
2. 计划 `collected_amount = SUM(plan 下所有 records)`;状态:`>= total → COMPLETED`,`DRAFT → IN_PROGRESS`(否则不变)。
3. `plan.remaining_amount = total_amount - collected_amount`。

Go 实现:`server/internal/finance/collection/`(CollectionPlan/Milestone/Record 三级模型 +
`AddRecord` 事务级联 + 纯状态函数 `MilestoneStatus`/`PlanStatus`,decimal)。
裁判算例(计划 10w;m1 预付 3w、m2 尾款 7w):`m1+1w→PARTIAL/计划 IN_PROGRESS`;`m1+2w→COLLECTED`;
`m2+7w→计划 COMPLETED`;`remaining=0`。纯状态单测(默认)+ 级联集成测试(真库)均与裁判一致,PASS。

## 🐞 对账发现的真实 bug(共库阻断,待修)

**masterdata.Item 业务主键字段名不符**:Django `item` 表用 **`sku`**(必填),Go 移植用了 `code` 列。
A 波用 AutoMigrate 从 Go 模型建表,掩盖了与真实 Django schema 的不匹配。
**✅ 已修**:item 模型按真实列对齐(`sku`/`specification`/`category_id` FK/`standard_cost`/`purchase_price`/
`sale_price`,去掉不存在的 `code`/`price`/`spec`/`category`),连带 dto/repo/handler 与前端 api/视图/类型;
经真库 `\d item` 核对一致,前端 vue-tsc 通过。
提示:其它模块也应逐一用真库 schema 校验字段名(本轮发现并修了 item;建议下一波对每模块跑 `\d <table>` diff)。

## 🔍 全模块真库 schema diff(已完成)

用真库全表列(dump 494 表 / 8666 列到 `/tmp/real_schema.tsv`)对 10 个模块逐表 diff Go 模型列名。结论:

- **唯一系统性偏差:审计列命名**。真库审计外键列是 `created_by_id`/`updated_by_id`(Django FK 加 `_id`),
  而共享 `platform/model.Base` 的 gorm 标签写成 `created_by`/`updated_by`,且各模块 `iam.ApplyScope(…, "created_by")`
  把列名直接拼进 WHERE → 对真库 `column "created_by" does not exist`(非超管 self/dept 范围查询必失败)。
  **✅ 已修**:`Base` 标签改为 `created_by_id`/`updated_by_id`、`BeforeDelete` 同步 `updated_by_id`、
  全仓 22 处 ApplyScope ownerCol 统一为 `created_by_id`;build/test/vet 全绿,masterdata 集成测试真库 PASS。
- **其余模块业务列名全部匹配真库**(sales/purchase/inventory/projects/production/finance/oa/accounts/workflow):
  生成 agent 当初读了 Django models.py,列名基本正确;item 是早期手写切片,故唯一列名错(已先修)。
- 次要信息(无碍,未改):`project_drawing.file`(Django FileField)Go 未映射;`reference_id` integer vs Go `*int64`;
  `transaction_date` date vs Go `time.Time`——语义一致。

## 下一步

1. finance 回款核销接 REST 路由 + 前端;前端各业务表按真库 schema 校验字段名。
2. workflow:抄送(cc_users/cc_roles)、超时升级、PROJECT_MANAGER/SUPERIOR 真实 resolver 接入。
3. inventory 成本账本(ItemCostRecord)与 Stock 移动联动(目前 Stock 走 weighted_avg_cost,
   ItemCostRecord 账本由其它流程喂);若需两者统一,需评估 Django 侧实际喂账本的入口。
